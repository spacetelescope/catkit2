from catkit2.testbed.service import Service

import thorlabs_apt as apt
import numpy as np


class ThorlabsCubeMotor(Service):
    """
    Service for controlling a Thorlabs cube motor.

    This service has been tested with the TDC001 and KDC101 cube motor controllers.
    """

    def __init__(self):
        super().__init__('thorlabs_cube_motor')

        self.cube_serial_number = self.config['serial_number']

        self.command = self.make_data_stream('command', 'float64', [1], 20)
        self.current_position = self.make_data_stream('current_position', 'float64', [1], 20)

        self.motor = None
        self.cube_model = None
        self.motor_unit = None
        self.motor_max = None
        self.motor_min = None

    def open(self):
        """
        Open connection to the motor.

        This will also check if the configured characteristics are matching the one the cube have.
        """
        self.motor = apt.Motor(self.cube_serial_number)

        # Retrieve the min, max, unit and model from the connected device.
        min = self.motor.get_stage_axis_info()[0]
        max = self.motor.get_stage_axis_info()[1]
        unit = None
        model = self.motor.hardware_info[0][2:-1]
        if self.motor.get_stage_axis_info()[2] == 1:
            unit = 'mm'
        if self.motor.get_stage_axis_info()[2] == 2:
            unit = 'deg'

        # Read min, max, unit and model from service configuration.
        self.min_pos = self.config['motor_min_pos']
        self.max_pos = self.config['motor_max_pos']
        self.unit = self.config['motor_unit']
        self.cube_model = self.config['cube_model']

        # Compare the device parameters to the service configuration.
        if not (self.min_pos == min and self.max_pos == max and self.unit == unit and self.cube_model == model):
            raise ValueError("Device parameters don't match configuration parameters.")

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
        apt._cleanup()

    def set_current_position(self, position):
        """
        Set the motor's current position.

        The unit is given in real-life units (mm if translation, deg if rotation).
        """
        self.motor.move_to(position, blocking=True)
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
