from ..service_proxy import ServiceProxy

import numpy as np

@ServiceProxy.register_service_interface('newport_xps_q8')
class NewportXpsQ8Proxy(ServiceProxy):
    def move_absolute(self, motor_id, position, timeout=None):
        command_stream = getattr(self, motor_id.lower() + '_command')
        current_position_stream = getattr(self, motor_id.lower() + '_current_position')

        position = self.resolve_position(motor_id.lower(), position)

        # Set new position.
        command_stream.submit_data(np.array([position], dtype='float64'))

        # Wait until actuator reaches new position.
        if timeout is None or timeout > 0:
            while True:
                try:
                    wait_time_ms = 1  # TODO: implement better waiting scheme.
                    if wait_time_ms is not None and wait_time_ms <= 0:
                        break

                    frame = current_position_stream.get_next_frame(wait_time_ms)

                    if abs(frame.data[0] - position) < self.atol:
                        break
                except RuntimeError:
                    # Timed out. First check if the command is still the same as what we commanded.
                    current_command = command_stream.get()

                    if not np.allclose(current_command, position, atol=self.atol):
                        # Someone else interrupted our move. Raise an exception.
                        raise RuntimeError(f'Absolute move interrupted or something went wrong when moving {motor_id} to {position} mm.')

                    # Otherwise, continue the wait loop.
                    continue

    def move_relative(self, motor_id, distance, timeout=None):
        # Get current position.
        stream = getattr(self, motor_id.lower() + '_current_position')
        current_position = stream.get()

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

    @property
    def atol(self):
        return self.config['atol']

    @property
    def motors(self):
        return self.config['motors']
