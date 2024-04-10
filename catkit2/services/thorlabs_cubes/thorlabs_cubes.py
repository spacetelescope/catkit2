from catkit2.testbed.service import Service

import thorlabs_apt as apt
import numpy as np


class ThorlabsCubes(Service):

    def __init__(self):
        super().__init__('thorlabs_cubes')

        self.cube_serial_number = self.config['serial_number']

        self.command = self.make_data_stream('command', 'float64', [1], 20)
        self.current_position = self.make_data_stream('current_position', 'float64', [1], 20)

        #Initialization of the parameters
        self.motor = None
        self.cube_model = None
        self.motor_unit = None
        self.motor_max = None
        self.motor_min = None

    def open(self):
        """
            Open the motor and cube.

            This will also check if the configured characteristics are matching the one the cube have.
        """
        self.motor = apt.Motor(self.serial_number)

        #Retrieve min, max, unit and model of the motor and cube
        min = self.motor.get_stage_axis_info()[0]
        max = self.motor.get_stage_axis_info()[1]
        unit = ''
        model = self.motor.hardware_info[0]
        if self.motor.get_stage_axis_info()[2] == 1:
            unit = 'mm'
        if self.motor.get_stage_axis_info()[2] == 2:
            unit = 'deg'

        #Config min, max, unit and model of the motor and cube
        self.min_pos = self.config['motor_min_pos']
        self.max_pos = self.config['motor_max_pos']
        self.unit = self.config['motor_unit']
        self.cube_model = self.config['cube_model']

        #Compare
        try :
            self.min_pos == min
            self.max_pos == max
            self.unit == unit
            self.cube_model == model
        except Exception:
            raise

    def main(self):
        while not self.should_shut_down:
            try:
                # Get an update for the motor position.
                frame = self.command.get_next_frame(10)
            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue
            self.set_current_position(frame.data[0])

    def close(self):
        self.motor._cleanup()

    def set_current_position(self, position):
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
    service = ThorlabsCubes()
    service.run()
