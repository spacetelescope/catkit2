from catkit2.testbed.service import Service, parse_service_args

import threading
import numpy as np

import urllib
from urllib.parse import urlencode
from http.client import IncompleteRead
from requests.exceptions import HTTPError

def catch_http_exceptions(function):
    """Decorator to catch http/web exceptions."""

    @functools.wraps(function)
    def wrapper(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        except (IncompleteRead, HTTPError) as e:
            raise Exception('Issues connecting to the webpage.') from e

    return wrapper

class NewportPicomotor(Service):
    _commands = {
        'set_home_position': 'DH',
        'exact_move': 'PA',
        'get_current_position': 'TP?',
        'reset': 'RS',
        'get_error_message': 'TB?'
    }

    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'newport_picomotor', testbed_port)

        config = self.configuration

        self.ip = config['ip']
        self.max_step = config['max_step']
        self.timeout = config['timeout']
        self.sleep_per_step = config['sleep_per_step']
        self.sleep_base = config['sleep_base']
        self.daisy = f"{config['daisy']}>" if config['daisy'] > 1 else ''
        self.axes = config['axes']

        self.shutdown_flag = threading.Event()

        self.axis_commands = {}
        self.axis_current_positions = {}
        self.axis_threads = {}

        self.lock_for_setter = threading.Lock()
        self.lock_for_getter = threading.Lock()

        for axis_name in self.axes.keys():
            self.add_axis(axis_name)

    def add_axis(self, axis_name):
        self.axis_commands[axis_name] = self.make_data_stream(axis_name.lower() + '_command', 'int64', [1], 20)
        self.axis_current_positions[axis_name] = self.make_data_stream(axis_name.lower() + '_current_position', 'int64', [1], 20)

    def set_current_position(self, axis_name, position):
        axis = self.axes[axis_name]

        position_before = self.get_current_position(axis_name)

        self.send_command('exact_move', axis, position)

        sleep_time = self.sleep_per_step * abs(position_before - position) + self.sleep_base
        time.sleep(sleep_time)

        position_after = self.get_current_position(axis_name)

        if position_after != position:
            raise RuntimeError('Newport picomotor failed to move to {position}; currently at {position_after}. Try increasing sleep_per_step.')

    def get_current_position(self, axis_name):
        axis = self.axes[axis_name]

        current_position = int(self.send_command('get_current_position', axis))

        # Update current position data stream.
        stream = self.axis_current_positions[axis_name]
        stream..submit_data(np.array([current_position]))

        return current_position

    def monitor_axis(self, axis_name):
        command_stream = self.axis_commands[axis_name]

        while not self.shutdown_flag.test():
            # Set the current position if a new command has arrived.
            try:
                frame = command_stream.get_next_frame(10)
            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            self.set_current_position(axis_name, frame.data[0])

    def open(self):
        self.shutdown_flag.clear()

        # Ping the connection to make sure it works
        try:
            urllib.request.urlopen(f'https://{self.ip}', timeout=self.timeout)
        except Exception as e:
            raise OSError(f'The controller IP address {self.ip} is not responding.') from e

        # Set current position as home.
        for axis in self.axes.values():
            self.send_command('set_home_position', axis, 0)

        # Start the motor threads
        for axis_name in self.axes.keys():
            thread = threading.Thread(target=self.monitor_axis, args=(axis_name,))
            thread.start()

            self.axis_threads[axis_name] = thread

    def main(self):
        self.shutdown_flag.wait()

    def close(self):
        self.shut_down()

        for thread in self.axis_threads.values():
            thread.join()

        self.reset_all_axes()

    def shut_down(self):
        self.shutdown_flag.set()

    def reset_all_axes(self):
        for axis in self.axes.values():
            self.send_command('exact_move', axis, 0)
            self.send_command('set_home_position', axis, 0)

    def reset_controller(self):
        self.send_command('reset')

    def get_error_message(self):
        response = self.send_command('get_error_message')

        # Parse response.
        code, message = response.split(',')
        code = int(code)
        message = message.strip()

        return code, message

    @catch_http_exceptions
    def send_command(self, command_key, axis=None, value=None):
        command_string = self.build_command_string(command_key, axis, value)

        form_data = urlencode({'cmd': command_string, 'submit': 'Send'})

        with self.instrument_lib.urlopen(f'http://{self.ip}/cmd_send.cgi?{form_data}', timeout=self.timeout) as html:
            resp = str(html.read())

        # Pull out the response from the html on the page
        # The output will be nestled between --> and \\r
        response = resp.split('response')[1].split('-->')[1].split('\\r')[0]
        return response

    def build_command_string(self, command_key, axis=None, value=None):
        cmd = self._commands[command_key]

        if value is None:
            value = ''
        else:
            value = int(value)

        if axis is None:
            axis = ''
        else:
            axis = int(axis)

        return f'{self.daisy}{axis}{cmd}{value}'

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = NewportPicomotor(service_name, testbed_port)
    service.run()
