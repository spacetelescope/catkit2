import time
import threading
import numpy as np
from catkit2.testbed.service import Service


class ThorlabsCubeMotorKinesisSim(Service):
    """Simulated service for controlling a Thorlabs cube motor."""

    def __init__(self):
        super().__init__('thorlabs_cube_motor_kinesis_sim')

        self.cube_model = self.config['cube_model']
        self.stage_model = self.config['stage_model']
        self.motor_positions = self.config['positions']
        self.motor_type = 0
        self.serial_number = str(self.config['serial_number']).encode("UTF-8")
        self.update_interval = self.config['update_interval']

        if self.cube_model == 'KDC101':
            self.motor_type = 27
        elif self.cube_model == 'TDC001':
            self.motor_type = 83
        else:
            raise ValueError(f"Motor type {self.motor_type} not supported.")

        self.unit = None
        self.min_position_config = None
        self.max_position_config = None

        self.command = None
        self.current_position = None

    def open(self):
        """Open connection to the motor."""
        self.log.debug("Serial number: %s", self.serial_number)

        # Read min, max, unit and model from service configuration.
        self.min_position_config = self.config['min_position']
        self.max_position_config = self.config['max_position']
        self.unit = self.config['unit']
        self.log.debug("Config parameters: min=%f, max=%f, unit=%s", self.min_position_config, self.max_position_config,
                       self.unit)

        self.command = self.make_data_stream('command', 'float64', [1], 20)
        self.current_position = self.make_data_stream('current_position', 'float64', [1], 20)

        nominal_position = self.resolve_position('nominal')
        self.current_position.submit_data(np.array([nominal_position], dtype='float64'))

        self.make_command('home', self.home)

        self.motor_thread = threading.Thread(target=self.monitor_motor)
        self.motor_thread.start()

    def monitor_motor(self):
        while not self.should_shut_down:
            try:
                # Get an update for the motor position.
                frame = self.command.get_next_frame(10)
                # Set the current position if a new command has arrived.
                self.set_current_position(frame.data[0])
            except RuntimeError:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def main(self):
        while not self.should_shut_down:
            self.get_current_position()
            self.sleep(self.update_interval)

    def close(self):
        self.motor_thread.join()

    def set_current_position(self, position):
        """
        Set the motor's current position.

        The unit is given in real-life units (mm if translation, deg if rotation).
        """
        if self.min_position_config <= position <= self.max_position_config:
            self.log.info("Setting new position: %f %s", position, self.unit)
            self.testbed.simulator.move_stage(stage_id=self.id,
                                              old_position=self.get_current_position(),
                                              new_position=position)
        else:
            self.log.warning('Motor not moving since commanded position is outside of configured range.')
            self.log.warning('Position limits: %f %s <= position <= %f %s.',
                             self.min_position_config, self.unit, self.max_position_config, self.unit)

    def get_current_position(self):
        position = self.current_position.get()[0]
        return position

    def resolve_position(self, position):
        if not isinstance(position, str):
            return position

        return self.resolve_position(self.motor_positions[position])

    def wait_for_completion(self):
        time.sleep(1)

    def home(self):
        """
        Home the motor.
        """
        # Home the motor
        self.set_current_position(0)

        # Wait for completion
        self.log.info("Homing motor %s...", self.serial_number)
        self.wait_for_completion()
        self.log.info("Homed - motor %s", self.serial_number)

        # Update the current position data stream
        self.current_position.submit_data(np.array([0], dtype='float64'))


if __name__ == '__main__':
    service = ThorlabsCubeMotorKinesisSim()
    service.run()
