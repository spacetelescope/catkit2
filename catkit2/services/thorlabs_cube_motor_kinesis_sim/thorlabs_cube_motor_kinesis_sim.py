import time
import numpy as np

from catkit2.testbed.service import Service


class ThorlabsCubeMotorKinesisSim(Service):
    """Simulated service for controlling a Thorlabs cube motor."""

    def __init__(self):
        super().__init__('thorlabs_cube_motor_kinesis_sim')

        self.cube_model = self.config['cube_model']
        self.stage_model = self.config['stage_model']
        self.motor_type = 0
        self.serial_number = str(self.config['serial_number']).encode("UTF-8")

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

        self.make_command('home', self.home)

    def main(self):
        while not self.should_shut_down:
            try:
                # Get an update for the motor position.
                frame = self.command.get_next_frame(10)
                # Set the current position if a new command has arrived.
                self.set_current_position(frame.data[0])
            except RuntimeError:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def close(self):
        pass

    def set_current_position(self, position):
        """
        Set the motor's current position.

        The unit is given in real-life units (mm if translation, deg if rotation).
        """
        if self.min_position_config <= position <= self.max_position_config:
            self.testbed.simulator.move_stage(stage_id=self.id,
                                              old_position=self.get_current_position(),
                                              new_position=position)
        else:
            self.log.warning('Motor not moving since commanded position is outside of configured range.')
            self.log.warning('Position limits: %f %s <= position <= %f %s.',
                             self.min_position_config, self.unit, self.max_position_config, self.unit)

    def get_current_position(self):
        position = self.current_position.get()[0]
        self.log.debug("Current position: %f %s", position, self.unit)
        return position

    def wait_for_completion(self):
        # wait for completion
        time.sleep(1)

    def home(self):
        """
        Home the motor.

        This will just sleep for a moment since there is no reason to home a simulated device.
        """
        # No reason to home simulated motor
        self.log.info("Homing motor %s...", self.serial_number)
        self.wait_for_completion()
        self.log.info("Homed - motor %s", self.serial_number)


if __name__ == '__main__':
    service = ThorlabsCubeMotorKinesisSim()
    service.run()
