from catkit2.testbed.service import Service

import pyvisa


class ThorlabsCLD101X(Service):
    _GET_CURRENT = "source1:current:level:amplitude?"
    _SET_CURRENT = "source1:current:level:amplitude "

    def __init__(self):
        super().__init__('thorlabs_cld101x')

        self.visa_id = self.config['visa_id']

        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)

    def open(self):
        self.manager = pyvisa.ResourceManager()
        self.connection = self.manager.open_resource(self.visa_id)

        # Reset device.
        self.connection.write('*RST')

        # Set to constant current mode.
        self.connection.write('source1:function:mode current')

        # Turn laser on and set current setpoint to 0.0
        self.connection.write("output1:state on")
        self.connection.write(f"{self._SET_CURRENT}0.0")

        # Read max current setpoint.
        self.max_current = float(self.connection.query(self._GET_CURRENT))  # in Ampere

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        self.connection.write(f"{self._SET_CURRENT}0.0")
        self.connection.write("output1:state off")
        self.connection.close()
        self.connection = None

        self.manager.close()

    def set_current_setpoint(self, current_percent):
        """
        Set the current setpoint of the laser, controlled as percent of its max current setpoint.

        Parameters
        ----------
        current_percent : int
            Limited to range 0-100, in percent of the max current setpoint in Ampere.
        """
        if current_percent < 0 or current_percent > 100:
            raise ValueError("Current_percent must be between 0 and 100.")

        current_setpoint = current_percent / 100 * self.max_current

        try:
            if current_setpoint == float(self.connection.query(self._GET_CURRENT)):
                return
        except Exception:
            # Cannot read current setpoint, so just continue.
            pass

        self.connection.write(f"{self._SET_CURRENT}{current_setpoint}")

        self.current_setpoint.submit_data(current_setpoint)


if __name__ == '__main__':
    service = ThorlabsCLD101X()
    service.run()
