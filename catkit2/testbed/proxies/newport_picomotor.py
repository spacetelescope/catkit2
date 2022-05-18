from ..service_proxy import ServiceProxy
import numpy as np
import time


@ServiceProxy.register_service_interface('newport_picomotor')
class NewportPicomotor(ServiceProxy):

    def move_relative(self, axis_name, distance, timeout=None):
        # Get current position.
        stream = getattr(self, axis_name.lower() + '_current_position')
        current_position = stream.get()

        new_position = current_position + distance

        self.move_absolute(axis_name, new_position, timeout=timeout)

    def move_absolute(self, axis_name, position, timeout=None):
        command_stream = getattr(self, axis_name.lower() + '_command')
        current_position_stream = getattr(self, axis_name.lower() + '_current_position')

        # Set new position.
        command_stream.submit_data(np.array([position], dtype='int32'))
