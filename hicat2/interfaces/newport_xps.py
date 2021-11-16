import time

from ..protocol.service_proxy import ServiceProxy, register_service_interface

@register_service_interface('newport_xps_q8')
class NewportXpsQ8Proxy(ServiceProxy):
    def move_absolute(self, motor_id, position, timeout=float('inf')):
        command_stream = getattr(self, motor_id.lower())
        current_position_stream = getattr(self, motor_id.lower() + '_current_position')

        position = self.resolve_position(motor_id, position)

        # Set new position.
        frame = command_stream.request_new_frame()
        frame.data[:] = distance
        command_stream.submit_frame(frame.id)

        # Wait until actuator reaches new position.
        waiting_start = time.time()

        if timeout > 0:
            while True:
                try:
                    wait_time_ms = int((time.time() - waiting_start - timeout) * 1000)
                    if wait_time_ms <= 0:
                        break

                    frame = current_position_stream.get_next_frame(wait_time_ms)
                except RuntimeError:
                    # Timed out. This is to facilitate wait time checking.
                    continue

    def move_relative(self, motor_id, distance, timeout=float('inf')):
        # Get current position.
        stream = getattr(self, motor_id.lower() + '_current_position')
        current_position = stream.get_latest_frame().data[0]

        new_position = current_position + distance

        self.move_absolute(motor_id, new_position, timeout=timeout)

    def resolve_position(self, motor_id, position_name):
        if type(position) == str:
            # The position is a named position.
            position = self.motor_positions[motor_id][position_name]

            # The position may still be a named position, so try to resolve deeper.
            return self.get_named_position(motor_id, position)
        else:
            return position
