import time
import logging

import numpy as np
from ..service_proxy import ServiceProxy


MAX_TIMEOUT_FOR_CHECKING = 1000  # ms
MAX_TIMEOUT_HITS = 3

@ServiceProxy.register_service_interface('newport_picomotor')
class NewportPicomotorProxy(ServiceProxy):
    log = logging.getLogger(__name__)

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

        num_timeout_hits = 0
        # Wait until actuator reaches new position.
        waiting_start = time.time()

        stalling_exception_text = 'Moving the picomotor timed out.'
        if timeout is None or timeout > 0:
            while True:
                try:
                    if timeout is None:
                        wait_time_ms = MAX_TIMEOUT_FOR_CHECKING
                    else:
                        # Wait for MAX_TIMEOUT_FOR_CHECKING ms or the remaining time until timeout, whichever is shortest.
                        wait_time_ms = int((timeout - (time.time() - waiting_start)) * 1000)
                        wait_time_ms = min(MAX_TIMEOUT_FOR_CHECKING, wait_time_ms)

                    if wait_time_ms is not None and wait_time_ms <= 0:
                        # The final timeout was reached. Raise an exception.
                        raise RuntimeError(stalling_exception_text)

                    # Check if we are at our final position, within absolute tolerance.
                    current_position = stream.get_next_frame(wait_time_ms).data[0]
                    if abs(current_position - position) < self.atol:
                        break
                except RuntimeError as e:
                    if str(e) == stalling_exception_text:
                        # The final timeout was reached, so reraise the exception.
                        self.log.info('From timeout', str(e))
                        raise
                    else:
                        # Datastream read timed out. This is to facilitate wait time checking, so this is normal.
                        self.log.warning(str(e))
                        num_timeout_hits += 1
                        if num_timeout_hits >= MAX_TIMEOUT_HITS:
                            raise TimeoutError(stalling_exception_text)

                # Send a log message to indicate we are still waiting.
                current_position = stream.get()[0]
                self.log.info(f'Waiting for stage movement: currently {current_position}, waiting for {position}.')

    @property
    def atol(self):
        return self.config['atol']
