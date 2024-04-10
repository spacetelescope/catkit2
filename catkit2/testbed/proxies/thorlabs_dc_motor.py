from ..service_proxy import ServiceProxy

import numpy as np


@ServiceProxy.register_service_interface('thorlabs_dc_motor')
class ThorlabsDCMotorProxy(ServiceProxy):
    def move_to(self, position):
        position = self.resolve_position(position)
        self.command.submit_data(np.array([position], dtype='float64'))

    def move_by(self, distance):
        current_position = self.current_position.get()[0]
        new_position = current_position + distance
        self.move_absolute(new_position)

    def resolve_position(self, position_name):
        if type(position_name) == str:
            # The position is a named position.
            position = self.positions[position_name]
            # The position may still be a named position, so try to resolve deeper.
            return self.resolve_position(position)
        else:
            return position_name

    def positions(self):
        return self.config['positions']
