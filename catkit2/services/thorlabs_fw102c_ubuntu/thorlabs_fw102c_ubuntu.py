"""
Thorlabs FW102C filter wheel service.

This service controls a Thorlabs FW102C six-position motorized filter wheel using PyVISA.
"""

import numpy as np
import pyvisa
import re
from catkit2.testbed.service import Service


class ThorlabsFW102C(Service):
    """
    Service for controlling a Thorlabs FW102C filter wheel.

    This service provides an interface to control the position of the filter wheel
    and monitor its current state.
    """

    def __init__(self):
        super().__init__('thorlabs_fw102c_ubuntu')

    def open(self):
        """
        Open the service and connect to the filter wheel.
        """
        # Create data streams first (always needed)
        self.position_stream = self.make_data_stream('position', 'int32', [1], 20)
        self.current_position_stream = self.make_data_stream('current_position', 'int32', [1], 20)

        try:
            # Get VISA ID from config
            visa_id = self.config['visa_id']

            # Open PyVISA connection
            self.rm = pyvisa.ResourceManager()
            self.connection = self.rm.open_resource(visa_id)

            # Configure the connection for FW102C
            self.connection.baud_rate = 115200
            self.connection.timeout = 2000  # Increase timeout
            self.connection.read_termination = '\r'
            self.connection.write_termination = '\r'

            # Test connection and get device info
            device_info = self._query('*idn?')
            self.log.info(f"Connected to filter wheel: {device_info}")

            # Get initial position
            initial_position = self._query('pos?')
            self.log.info(f"Initial position: {initial_position}")

            # Create properties and commands
            self.make_property('position', self.get_position, self.set_position)
            self.make_command('home', self.home)
            self.make_command('get_info', self.get_device_info)
            self.make_command('set_position', self.set_position)
            self.make_command('get_position', self.get_position)

            # Submit initial position to data streams
            pos = int(initial_position)
            self.position_stream.submit_data(np.array([pos], dtype='int32'))
            self.current_position_stream.submit_data(np.array([pos], dtype='int32'))

            self.log.info("Filter wheel service opened successfully")

        except Exception as e:
            self.log.warning(f"Could not connect to filter wheel: {e}")
            self.log.warning("Filter wheel will run in simulation mode.")

            # Submit default position for simulation mode
            self.position_stream.submit_data(np.array([1], dtype='int32'))
            self.current_position_stream.submit_data(np.array([1], dtype='int32'))

            self.connection = None

    def close(self):
        """
        Close the service and disconnect from the filter wheel.
        """
        if hasattr(self, 'connection') and self.connection is not None:
            try:
                self.connection.close()
                self.rm.close()
                self.log.info("Filter wheel connection closed")
            except Exception as e:
                self.log.error(f"Error closing filter wheel: {e}")

    def _query(self, command):
        """
        Send a query command and return the response.

        The FW102C echoes commands, so we need to handle this properly.

        Parameters
        ----------
        command : str
            The command to send

        Returns
        -------
        str
            The device response (without echo)
        """
        if self.connection is None:
            return "0"  # Simulation mode

        try:
            # Clear input buffer multiple times to ensure it's clean
            for _ in range(3):
                try:
                    self.connection.read_raw()
                except pyvisa.VisaIOError:
                    break  # Buffer is clear

            # Send command
            self.connection.write(command)

            # Give device time to respond
            import time
            time.sleep(0.1)

            # Read response - try multiple approaches
            try:
                # First, try to read all available data
                raw_data = b''
                while True:
                    try:
                        chunk = self.connection.read_raw()
                        raw_data += chunk
                    except pyvisa.VisaIOError:
                        break  # No more data

                if raw_data:
                    response_text = raw_data.decode('ascii', errors='ignore')
                    lines = response_text.replace('\r', '\n').split('\n')

                    # Look for a line that's not the command echo and not empty
                    for line in lines:
                        line = line.strip()
                        if line and line != command and not line.startswith('>') and line != '':
                            # Check if it looks like a valid response
                            if command == 'pos?' and line.isdigit():
                                return line
                            elif command == '*idn?' and 'THORLABS' in line.upper():
                                return line
                            elif not any(char in line for char in ['?', '>', '<']):
                                return line

                # If we got here, try a different approach
                self.connection.write(command)
                time.sleep(0.2)
                response = self.connection.read()
                return response.strip()

            except Exception as read_error:
                self.log.debug(f"Read error for '{command}': {read_error}")
                return ""

        except Exception as e:
            self.log.error(f"Query error for command '{command}': {e}")
            return ""

    def _command(self, command):
        """
        Send a command and check for errors.

        Parameters
        ----------
        command : str
            The command to send

        Returns
        -------
        str
            The response or error message
        """
        if self.connection is None:
            return "OK"  # Simulation mode

        try:
            # Clear input buffer
            try:
                self.connection.read_raw()
            except pyvisa.VisaIOError:
                pass

            # Send command
            self.connection.write(command)

            # Read response and check for errors
            try:
                raw_response = self.connection.read_raw().decode('ascii')
                lines = raw_response.strip().split('\n')

                # Check for command errors
                for line in lines:
                    if "Command error" in line:
                        self.log.error(f"Command error: {line.strip()}")
                        return line.strip()

                # If it's a set command, query the result to confirm
                if '=' in command:
                    query_cmd = command.split('=')[0] + '?'
                    return self._query(query_cmd)

                return "OK"

            except pyvisa.VisaIOError:
                # No response is sometimes OK for commands
                return "OK"

        except Exception as e:
            self.log.error(f"Command error for '{command}': {e}")
            return f"Error: {e}"

    def get_position(self):
        """
        Get the current position of the filter wheel.

        Returns
        -------
        int
            The current position (1-6)
        """
        response = self._query('pos?')
        try:
            position = int(response)
            # Update data streams
            self.position_stream.submit_data(np.array([position], dtype='int32'))
            self.current_position_stream.submit_data(np.array([position], dtype='int32'))
            return position
        except ValueError:
            self.log.error(f"Invalid position response: '{response}'")
            return 1

    def set_position(self, position):
        """
        Set the position of the filter wheel.

        Parameters
        ----------
        position : int
            The target position (1-6)
        """
        if not (1 <= position <= 6):
            self.log.error(f"Invalid position {position}. Must be 1-6.")
            return

        response = self._command(f'pos={position}')
        self.log.info(f"Moving to position {position}: {response}")

        # Update data streams with new position
        self.position_stream.submit_data(np.array([position], dtype='int32'))
        self.current_position_stream.submit_data(np.array([position], dtype='int32'))

    def home(self):
        """
        Home the filter wheel (move to position 1).
        """
        self.log.info("Homing filter wheel")
        self.set_position(1)

    def get_device_info(self):
        """
        Get device information.

        Returns
        -------
        str
            Device identification string
        """
        return self._query('*idn?')

    def get_filter_count(self):
        """
        Get the number of filter positions.

        Returns
        -------
        int
            Number of positions (6 or 12)
        """
        response = self._query('pcount?')
        try:
            return int(response)
        except ValueError:
            return 6  # Default

    def set_speed(self, speed):
        """
        Set the movement speed.

        Parameters
        ----------
        speed : int
            0 for slow, 1 for fast
        """
        if speed not in [0, 1]:
            self.log.error("Speed must be 0 (slow) or 1 (fast)")
            return
        self._command(f'speed={speed}')

    def main(self):
        """
        Main service loop.
        """
        while not self.should_shut_down:
            # Periodically update position (every 5 seconds)
            if hasattr(self, 'connection') and self.connection is not None:
                try:
                    current_pos = self.get_position()
                    self.log.debug(f"Current position: {current_pos}")
                except Exception as e:
                    self.log.error(f"Error reading position: {e}")

            self.sleep(5.0)


if __name__ == '__main__':
    service = ThorlabsFW102C()
    service.run()