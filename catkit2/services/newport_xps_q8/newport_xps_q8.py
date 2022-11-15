from catkit2.testbed.service import Service

import sys
import os
import threading
import numpy as np
import traceback

try:
    library_path = os.environ.get('CATKIT_NEWPORT_LIB_PATH')
    if library_path:
        sys.path.append(library_path)
    import XPS_Q8_drivers
except ImportError:
    print("To use the Newport XPS-Q8, you need to set the CATKIT_NEWPORT_LIB_PATH environment variable.")
    raise

class NewportXpsQ8(Service):
    _OK_STATES = (7, 11, 12, 42)

    def __init__(self):
        super().__init__('newport_xps_q8')

        self.ip_address = self.config['ip_address']
        self.port = self.config['port']
        self.timeout = self.config['timeout']
        self.motor_positions = self.config['motors']
        self.update_interval = self.config['update_interval']
        self.motor_ids = list(self.config['motors'].keys())
        self.atol = self.config['atol']

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
        stream.submit_data(np.array([current_position], dtype='float64'))

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
        try:
            # Initialize motor if not already initialized.
            pass
            # self._ensure_initialized(motor_id)
        except Exception:
            # Log the error, then reraise.
            self.log.critical(traceback.format_exc())
            raise

        command_stream = self.motor_commands[motor_id]

        while not self.should_shut_down:
            try:
                # Set the current position if a new command has arrived.
                try:
                    frame = command_stream.get_next_frame(10)
                except Exception:
                    # Timed out. This is used to periodically check the shutdown flag.
                    continue

                self.set_current_position(motor_id, frame.data[0])
            except Exception:
                # Do not raise an error, but instead log it.
                self.log.error(traceback.format_exc())

    def open(self):
        # Start the device
        self.device = XPS_Q8_drivers.XPS()

        # Start two socket connections to the driver for each motor.
        try:
            self.socket_get = {}
            self.socket_set = {}

            for motor_id in self.motor_ids:
                socket_id_get = self.device.TCP_ConnectToServer(self.ip_address, self.port, self.timeout)

                if socket_id_get == -1:
                    raise RuntimeError('Connection to XPS failed, check IP & port (invalid socket)')

                self.socket_get[motor_id] = (socket_id_get, threading.Lock())

                socket_id_set = self.device.TCP_ConnectToServer(self.ip_address, self.port, self.timeout)
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
        while not self.should_shut_down:
            for motor_id in self.motor_ids:
                self.get_current_position(motor_id)

            self.sleep(self.update_interval)

    def close(self):
        # Stop the motor threads
        self.shut_down()

        for thread in self.motor_threads.values():
            thread.join()

        self.motor_threads = {}

        # Close the opened sockets.
        for socket_id, lock in self.socket_get.values():
            self.device.TCP_CloseSocket(socket_id)

        for socket_id, lock in self.socket_set.values():
            self.device.TCP_CloseSocket(socket_id)

if __name__ == '__main__':
    service = NewportXpsQ8()
    service.run()
