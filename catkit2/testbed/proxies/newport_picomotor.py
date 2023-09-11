import time
import numpy as np
from ..service_proxy import ServiceProxy


@ServiceProxy.register_service_interface('newport_picomotor')
class NewportPicomotorProxy(ServiceProxy):

    def move_relative(self, axis_name, distance, timeout=None):
        # Get current position.
        stream = getattr(self, axis_name.lower() + '_current_position')
        current_position = stream.get()[0]

        new_position = current_position + distance

        self.move_absolute(axis_name, new_position, timeout=timeout)

    def move_absolute(self, axis_name, position, timeout=None):
        command_stream = getattr(self, axis_name.lower() + '_command')

        # Set new position.
        command_stream.submit_data(np.array([position], dtype='int32'))

        # Get current position.
        stream = getattr(self, axis_name.lower() + '_current_position')

        # Wait until actuator reaches new position.
        waiting_start = time.time()

        exception_text = 'Moving the picomotor timed out.'
        if timeout is None or timeout > 0:
            while True:
                try:
                    if timeout is None:
                        wait_time_ms = None
                    else:
                        # Wait for 1 sec or the remaining time until timeout, whichever is shortest.
                        wait_time_ms = int((timeout - (time.time() - waiting_start)) * 1000)
                        wait_time_ms = min(1000, wait_time_ms)

                    if wait_time_ms is not None and wait_time_ms <= 0:
                        raise RuntimeError(exception_text)

                    current_position = stream.get()[0]
                    if abs(current_position - position) < self.atol:
                        break
                except RuntimeError as e:
                    if str(e) == exception_text:
                        raise
                    else:
                        # Datastream read timed out. This is to facilitate wait time checking.
                        continue

    @property
    def atol(self):
        return self.config['atol']
