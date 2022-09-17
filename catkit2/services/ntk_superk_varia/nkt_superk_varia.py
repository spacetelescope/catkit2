from catkit2.testbed.service import Service

from NKTP_DLL import *

DEVICE_ID = 16

REG_MONITOR_INPUT = 0x13

REG_ND_SETPOINT = 0x32
REG_SWP_SETPOINT = 0x33
REG_LWP_SETPOINT = 0x34

REG_STATUS_BITS = 0x66

def read_register(read_func, register, *, ratio=1, index=-1):
    def getter(self):
        with self.lock:
            result, value = read_func(self.port, DEVICE_ID, register, index)

        self.check_result(result)

        return value * ratio

    return getter

def write_register(write_func, register, *, ratio=1, index=-1):
    def setter(self, value):
        # Convert the value to the register value. This assumes integer types.
        register_value = int(value / ratio)

        with self.lock:
            result = write_func(self.port, DEVICE_ID, register, register_value, index)

        self.check_result(result)

        # Update filter wheel status.
        self.update_status()

    return setter

class NktSuperkVaria(Service):
    def __init__(self):
        super().__init__('nkt_superk_varia')

        self.lock = threading.Lock()
        self.threads = {}

    def open(self):
        # Open port.
        # Make sure that the device is available (ie. not being used by someone else).
        # This is not strictly necessary according to the SDK, but speeds up reading/writing.

        # Make datastreams.
        self.monitor_input = self.make_data_stream('monitor_input', [1], 'float32', 20)

        self.nd_setpoint = self.make_data_stream('nd_setpoint', [1], 'float32', 20)
        self.swp_setpoint = self.make_data_stream('swp_setpoint', [1], 'float32', 20)
        self.lwp_setpoint = self.make_data_stream('lwp_setpoint', [1], 'float32', 20)

        self.nd_filter_moving = self.make_data_stream('nd_filter_moving', [1], 'uint8', 20)
        self.swp_filter_moving = self.make_data_stream('nd_filter_moving', [1], 'uint8', 20)
        self.lwp_filter_moving = self.make_data_stream('nd_filter_moving', [1], 'uint8', 20)

        # Set current setpoints. These will be actually set on the device
        # once the monitor threads have started.
        self.nd_setpoint.submit_data(np.array([self.config['nd_setpoint']]))
        self.swp_setpoint.submit_data(np.array([self.config['swp_setpoint']]))
        self.lwp_setpoint.submit_data(np.array([self.config['lwp_setpoint']]))

        # Start threads.
        funcs = {
            'nd_setpoint': self.monitor(self.nd_setpoint, self.set_nd_setpoint),
            'swp_setpoint': self.monitor(self.swp_setpoint, self.set_swp_setpoint),
            'lwp_setpoint': self.monitor(self.lwp_setpoint, self.set_lwp_setpoint),
            'monitor_input': self.update_monitor_input
        }

        for key, func in funcs:
            thread = threading.thread(target=func)
            thread.start()

            self.threads[key] = thread

    def main(self):
        # Update status.
        while not self.should_shut_down:
            self.sleep(0.5)

            self.update_status()

    def close(self):
        # Close connection.

        # Join all threads.
        for thread in self.threads:
            thread.join()

    def update_status(self):
        status = self.get_status_bits()

        # Extract moving filters from status.
        nd_filter_moving = (status & (2 << 12)) > 0
        swp_filter_moving = (status & (2 << 13)) > 0
        lwp_filter_moving = (status & (2 << 14)) > 0

        # Submit results to their respective datastreams.
        self.nd_filter_moving.submit_data(np.array([nd_filter_moving], dtype='uint8'))
        self.swp_filter_moving.submit_data(np.array([swp_filter_moving], dtype='uint8'))
        self.lwp_filter_moving.submit_data(np.array([lwp_filter_moving], dtype='uint8'))

    def monitor(self, stream, setter):
        while not self.should_shut_down:
            try:
                frame = stream.get_next_frame(1)
            except Exception:
                continue

            setter(frame.data[0])

    def update_monitor_input(self):
        while not self.should_shut_down:
            monitor_input = self.get_monitor_input()

            self.monitor_input.submit_data(np.array([monitor_input], dtype='float32'))

            self.sleep(1)

    get_monitor_input = read_register(RegisterReadU16, REG_MONITOR_INPUT, ratio=0.1)

    get_nd_setpoint = read_register(RegisterReadU16, REG_ND_SETPOINT, ratio=0.1)
    get_swp_setpoint = read_register(RegisterReadU16, REG_SWP_SETPOINT, ratio=0.1)
    get_lwp_setpoint = read_register(RegisterReadU16, REG_LWP_SETPOINT, ratio=0.1)

    set_nd_setpoint = write_register(RegisterWriteU16, REG_ND_SETPOINT, ratio=0.1)
    set_swp_setpoint = write_register(RegisterWriteU16, REG_SWP_SETPOINT, ratio=0.1)
    set_lwp_setpoint = write_register(RegisterWriteU16, REG_LWP_SETPOINT, ratio=0.1)

    get_status_bits = read_register(RegisterReadU16, REG_STATUS_BITS)
