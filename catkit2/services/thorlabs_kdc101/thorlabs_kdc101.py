from catkit2.testbed.service import Service

from thorlabs_apt_device import KDC101
import numpy as np


class ThorlabsKDC101(Service):

    def __init__(self):
        super().__init__('thorlabs_kdc101')

        self.serial_number = self.config['serial_number']

        self.command = self.make_data_stream('command', 'float64', [1], 20)
        self.current_position = self.make_data_stream('current_position', 'float64', [1], 20)
        self.motor = None

    def open(self):
        self.motor = KDC101(serial_number=self.serial_number, home=False)

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
        self.motor.close()

    def set_current_position(self, position):
        self.motor.move_absolute(position)
        # Update the current position data stream.
        self.get_current_position()

    def get_current_position(self):
        current_position = self.motor.status["position"]
        self.current_position.submit_data(np.array([current_position], dtype='float64'))

    def home(self):
        """
        Home the motor.

        This will block until the motor has finished homing.
        """
        self.motor.home()

        while self.motor.status["homing"]:
            self.sleep(0.1)

        # Update the current position data stream.
        self.get_current_position()

    def stop(self):
        """Stop any current movement of the motor."""
        self.motor.stop()
        # Update the current position data stream.
        self.get_current_position()

    def get_status(self):
        return self.motor.status


if __name__ == '__main__':
    service = ThorlabsKDC101()
    service.run()
