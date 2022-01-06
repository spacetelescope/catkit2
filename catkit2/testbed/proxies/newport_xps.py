import time

from ..service_proxy import ServiceProxy

@ServiceProxy.register_service_interface('newport_xps_q8')
class NewportXpsQ8Proxy(ServiceProxy):
    def move_absolute(self, motor_id, position, timeout=None):
        command_stream = getattr(self, motor_id.lower() + '_command')
        current_position_stream = getattr(self, motor_id.lower() + '_current_position')

        position = self.resolve_position(motor_id, position)

        # Set new position.
        frame = command_stream.request_new_frame()
        frame.data[:] = position
        command_stream.submit_frame(frame.id)

        # Wait until actuator reaches new position.
        waiting_start = time.time()

        if timeout is None or timeout > 0:
            while True:
                try:
                    wait_time_ms = None if timeout is None else int((timeout - (time.time() - waiting_start)) * 1000)
                    if wait_time_ms is not None and wait_time_ms <= 0:
                        break

                    frame = current_position_stream.get_next_frame(wait_time_ms)

                    if abs(frame.data[0] - position) < self.atol:
                        break
                except RuntimeError:
                    # Timed out. This is to facilitate wait time checking.
                    continue

    def move_relative(self, motor_id, distance, timeout=None):
        # Get current position.
        stream = getattr(self, motor_id.lower() + '_current_position')
        current_position = stream.get()

        new_position = current_position + distance

        self.move_absolute(motor_id, new_position, timeout=timeout)

    def resolve_position(self, motor_id, position_name):
        if type(position_name) == str:
            # The position is a named position.
            position = self.positions[motor_id][position_name]

            # The position may still be a named position, so try to resolve deeper.
            return self.resolve_position(motor_id, position)
        else:
            return position_name

    @property
    def positions(self):
        return {key.lower(): value for key, value in self.configuration['motors'].items()}

    @property
    def atol(self):
        return self.configuration['atol']
