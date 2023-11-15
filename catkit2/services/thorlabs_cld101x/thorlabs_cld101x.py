from catkit2.testbed.service import Service

import pyvisa


class ThorlabsCLD101X(Service):
    def __int__(self):
        super().__init__('thorlabs_cld101x')

        self.visa_id = self.config['visa_id']

        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)

    def open(self):
        manager = pyvisa.ResourceManager()

        self.connection = manager.open_resource(self.visa_id)

        # *IDN? query

        # reset device

        # set to constant current mode

        # turn laser on and set current setpoint to 0.0

        # read max current setpoint

    def main(self):
        while not self.should_shut_down:
            # read current setpoint

            # update current setpoint data stream

            # wait for 1 second
            pass

    def close(self):
        self.connection.close()
        self.connection = None

    def set_current_setpoint(self, current_setpoint):
        # set current setpoint - scale to 0-100% of max current setpoint

        # update current setpoint data stream
        pass


if __name__ == '__main__':
    service = ThorlabsCLD101X()
    service.run()
