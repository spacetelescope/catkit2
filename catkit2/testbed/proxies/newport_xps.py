from ..service_proxy import ServiceProxy

import time
import numpy as np


class NewportXpsQ8Proxy(ServiceProxy):
    def move_absolute(self, motor_id, position, timeout=None):
        """Move to a numeric or named position, using the service's tolerance.

        A positive timeout limits waiting in seconds (with 1 ms frame waits).
        None waits indefinitely; zero or negative values submit without waiting.
        TimeoutError stops waiting, but does not abort controller motion.
        """
        command_stream = getattr(self, motor_id.lower() + '_command')
        current_position_stream = getattr(self, motor_id.lower() + '_current_position')

        position = self.resolve_position(motor_id.lower(), position)

        # Set new position.
        command_stream.submit_data(np.array([position], dtype='float64'))

        # Wait until actuator reaches new position.
        if timeout is None or timeout > 0:
            deadline = None if timeout is None else time.monotonic() + timeout
            atol = self._get_motor_atol(motor_id)
            current_position = None
            while True:
                try:
                    current_position = current_position_stream.get_next_frame(1).data[0]
                except RuntimeError:
                    # A frame timeout does not reset the overall move deadline.
                    pass

                last_readback = 'unavailable' if current_position is None else f'{current_position} mm'
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError(f'Timed out waiting for {motor_id} to reach {position} mm. '
                                       f'Last readback: {last_readback}.')

                # Check for replacement commands even when telemetry keeps arriving.
                current_command = command_stream.get()
                if not np.allclose(current_command, position, atol=atol):
                    raise RuntimeError(f'Absolute move interrupted or something went wrong when moving {motor_id} to {position} mm. '
                                       f'Last readback: {last_readback}; current command: {current_command[0]} mm.')

                # Match the service's inclusive comparison and default relative tolerance.
                if current_position is not None and np.isclose(current_position, position, atol=atol):
                    break

    def move_relative(self, motor_id, distance, timeout=None):
        # Get current position.
        stream = getattr(self, motor_id.lower() + '_current_position')
        current_position = stream.get()[0]

        new_position = current_position + distance

        self.move_absolute(motor_id.lower(), new_position, timeout=timeout)

    def resolve_position(self, motor_id, position_name):
        if type(position_name) == str:
            # The position is a named position.
            position = self.positions[motor_id.lower()][position_name]

            # The position may still be a named position, so try to resolve deeper.
            return self.resolve_position(motor_id.lower(), position)
        else:
            return position_name

    @property
    def positions(self):
        return {key.lower(): value for key, value in self.config['motors'].items()}

    def _get_motor_atol(self, motor_id):
        motor_id = next(motor for motor in self.config['motors'] if motor.lower() == motor_id.lower())
        return self.config['atol'].get(motor_id, self.config['atol']['default'])

    @property
    def motors(self):
        return [motor.lower() for motor in self.config['motors'].keys()]
