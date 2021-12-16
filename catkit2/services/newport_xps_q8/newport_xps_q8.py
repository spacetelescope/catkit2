from catkit2.protocol.service import Service, parse_service_args

import time
import sys
import threading
import numpy as np

library_path = os.environ.get('CATKIT_NEWPORT_LIB_PATH')
if library_path:
    sys.path.append(library_path)
import XPS_Q8_drivers

class NewportXpsQ8(Service):
    _OK_STATES = (7, 11, 12, 42)

    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'newport_xps_q8', testbed_port)

        config = self.configuration

        self.ip_address = config['ip_address']
        self.port = config['port']
        self.timeout = config['timeout']
        self.motor_positions = config['motors']
        self.update_interval = config['update_interval']
        self.motor_ids = list(config['motors'].keys())
        self.atol = config['atol']

        self.shutdown_flag = threading.Event()

        self.motor_commands = {}
        self.motor_current_positions = {}
        self.motor_threads = {}

        for motor_id in self.motor_ids:
            self.add_motor(motor_id)

        self.socket_get = {}
        self.socket_set = {}

    def add_motor(self, motor_id):
        self.motor_commands[motor_id] = self.make_data_stream(motor_id.lower() + '_command', 'float64', [1], 20)
        self.motor_current_positions[motor_id] = self.make_data_stream(motor_id.lower() + '_current_position', 'float64', [1], 20)

    def set_current_position(self, motor_id, position):
        socket_id, lock = self.socket_set[motor_id]
        positioner = motor_id + '.Pos'

        current_position = self.get_current_position(motor_id)

        if not np.isclose(current_position, position, atol=self.atol):
            # Move the actuator.
            with lock:
                error_code, return_string = self.device.GroupMoveAbsolute(socket_id, positioner, [position])
                self._raise_on_error(error_code, 'GroupMoveAbsolute')

            # Update current position data stream.
            self.get_current_position(motor_id)

    def get_current_position(self, motor_id):
        socket_id, lock = self.socket_get[motor_id]
        positioner = motor_id + '.Pos'

        with lock:
            error_code, current_position = self.device.GroupPositionCurrentGet(socket_id, positioner, 1)
            self._raise_on_error(error_code, 'GroupPositionCurrentGet')

        # Update current position data stream.
        stream = self.motor_current_positions[motor_id]
        stream.submit_data(np.array([current_position]))

        return current_position

    def _ensure_initialized(self, motor_id):
        socket_id, lock = self.socket_set[motor_id]

        with lock:
            error_code, current_status = self.device.GroupStatusGet(socket_id, motor_id)
            self._raise_on_error(error_code, 'GroupStatusGet')

            # Kill motor if it is not in a known good state.
            if current_status not in self._OK_STATES:
                error_code, return_string = self.device.GroupKill(socket_id, motor_id)
                self._raise_on_error(error_code, 'GroupKill')

                # Update the status.
                error_code, current_status = self.device.GroupStatusGet(socket_id, motor_id)
                self._raise_on_error(error_code, 'GroupStatusGet')

            # Initialize from killed state.
            if current_status == 7:
                # Initialize the group
                error_code, return_string = self.device.GroupInitialize(socket_id, motor_id)
                self._raise_on_error(error_code, 'GroupInitialize')

                # Update the status
                error_code, current_status = self.device.GroupStatusGet(socket_id, motor_id)
                self._raise_on_error(error_code, 'GroupStatusGet')

            # Home search
            if current_status == 42:
                error_code, return_string = self.device.GroupHomeSearch(socket_id, motor_id)
                self._raise_on_error(error_code, 'GroupHomeSearch')

    def _raise_on_error(self, error_code, api_name):
        if error_code == 0:
            return

        if error_code == -2:
            raise RuntimeError(f"{api_name}: TCP timeout")
        elif error_code == -108:
            raise RuntimeError(f"{api_name}: The TCP/IP connection was closed by an administrator")
        else:
            error_code2, error_string = self.instrument.ErrorStringGet(self.socket_id, error_code)
            if error_code2 != 0:
                raise RuntimeError(f"{api_name}: ERROR '{error_code}'")
            else:
                raise RuntimeError(f"{api_name}: '{error_string}'")

    def monitor_motor(self, motor_id):
        # Initialize motor if not already initialized.
        self._ensure_initialized(motor_id)

        command_stream = self.motor_commands[motor_id]

        while not self.shutdown_flag.is_set():
            # Set the current position if a new command has arrived.
            try:
                frame = command_stream.get_next_frame(10)
            except:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            self.set_current_position(motor_id, frame.data[0])

    def open(self):
        self.shutdown_flag.clear()

        # Start the device
        self.device = XPS_Q8_drivers.XPS()

        # Start two socket connections to the driver for each motor.
        try:
            self.socket_get = {}
            self.socket_set = {}

            for motor_id in self.motor_ids:
                socket_id_get = self.device.TCP_ConnectToServer(self.host, self.port, self.timeout)

                if socket_id_get == -1:
                    raise RuntimeError('Connection to XPS failed, check IP & port (invalid socket)')

                self.socket_get[motor_id] = (socket_id_get, threading.Lock())

                socket_id_set = self.device.TCP_ConnectToServer(self.host, self.port, self.timeout)
                if socket_id_set == -1:
                    raise RuntimeError('Connection to XPS failed, check IP & port (invalid socket)')

                self.socket_set[motor_id] = (socket_id_set, threading.Lock())
        except RuntimeError:
            # Close the already opened sockets.
            for socket_id, lock in self.socket_get.values():
                self.device.TCP_CloseSocket(socket_id)

            for socket_id, lock in self.socket_set.values():
                self.device.TCP_CloseSocket(socket_id)

        # Start the motor threads
        for motor_id in self.motor_ids:
            thread = threading.Thread(target=self.monitor_motor, args=(motor_id,))
            thread.start()

            self.motor_threads[motor_id] = thread

    def main(self):
        while not self.shutdown_flag.is_set():
            for motor_id in self.motor_ids:
                self.get_current_position(motor_id)

            self.shutdown_flag.wait(self.update_interval)

    def close(self):
        # Stop the motor threads
        self.shut_down()

        for thread in self.motor_threads.values():
            thread.join()

        self.motor_threads = {}

        # Close the socket to the driver.
        if self.socket_id is not None:
            try:
                self.device.TCP_CloseSocket(self.socket_id)
            finally:
                self.socket_id = None

    def shut_down(self):
        self.shutdown_flag.set()

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = NewportXpsQ8(service_name, testbed_port)
    service.run()
