from catkit2.testbed.service import Service

import thorlabs_apt as apt
import thorlabs_apt.core as apt_core
import numpy as np


class ThorlabsCubeMotor(Service):
    """
    Service for controlling a Thorlabs cube motor.

    This service has been tested with the TDC001 and KDC101 cube motor controllers.
    """

    def __init__(self):
        super().__init__('thorlabs_cube_motor')

        self.serial_number = self.config['serial_number']
        self.motor = None

        self.cube_model = None
        self.unit = None
        self.min_position_device = None
        self.max_position_device = None
        self.min_position_config = None
        self.max_position_config = None

    def open(self):
        """
        Open connection to the motor.

        This will also check if the configured characteristics are matching the one the cube have.
        """
        self.motor = apt.Motor(self.serial_number)

        # Retrieve the min, max, unit and model from the connected device.
        self.min_position_device = self.motor.get_stage_axis_info()[0]
        self.max_position_device = self.motor.get_stage_axis_info()[1]

        self.cube_model = self.motor.hardware_info[0].decode('utf-8')
        if self.motor.get_stage_axis_info()[2] == 1:
            self.unit = 'mm'
        if self.motor.get_stage_axis_info()[2] == 2:
            self.unit = 'deg'

        # Read min, max, unit and model from service configuration.
        self.min_position_config = self.config['min_position']
        self.max_position_config = self.config['max_position']
        unit_config = self.config['unit']
        cube_model_config = self.config['cube_model']

        # Compare the device parameters to the service configuration.
        if not (self.min_position_device >= self.min_position_config and self.max_position_device <= self.max_position_config and self.unit == unit_config and self.cube_model == cube_model_config):
            raise ValueError("Device parameters don't match configuration parameters.")

        self.command = self.make_data_stream('command', 'float64', [1], 20)
        self.current_position = self.make_data_stream('current_position', 'float64', [1], 20)

        self.make_command('home', self.home)
        self.make_command('stop', self.stop)
        self.make_command('is_in_motion', self.is_in_motion)

    def main(self):
        while not self.should_shut_down:
            try:
                # Get an update for the motor position.
                frame = self.command.get_next_frame(10)
                # Set the current position if a new command has arrived.
                self.set_current_position(frame.data[0])
            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def close(self):
        self.motor = None
        apt_core._cleanup()

    def set_current_position(self, position):
        """
        Set the motor's current position.

        The unit is given in real-life units (mm if translation, deg if rotation).
        """
        if self.min_position_config <= position <= self.max_position_config:
            self.motor.move_to(position, blocking=True)
        else:
            self.log.warning(f'Motor not moving since commanded position is outside of configured range.')
            self.log.warning(f'Position limits: {self.min_position_config} {self.unit} <= position <= {self.max_position_config} {self.unit}.')

        # Update the current position data stream.
        self.get_current_position()

    def get_current_position(self):
        current_position = self.motor.position()
        self.current_position.submit_data(np.array([current_position], dtype='float64'))

    def home(self):
        """
        Home the motor.

        This will block until the motor has finished homing.
        """
        self.motor.move_home(blocking=True)

        while not self.motor.has_homing_been_completed():
            self.sleep(0.1)

        # Update the current position data stream.
        self.get_current_position()

    def stop(self):
        """Stop any current movement of the motor."""
        self.motor.stop_profiled()

        while self.is_in_motion():
            self.sleep(0.1)
        # Update the current position data stream.
        self.get_current_position()

    def is_in_motion(self):
        """Check if the motor is currently moving."""
        return self.motor.is_in_motion()


if __name__ == '__main__':
    service = ThorlabsCubeMotor()
    service.run()
