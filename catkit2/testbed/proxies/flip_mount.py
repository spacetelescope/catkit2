from ..service_proxy import ServiceProxy

import numpy as np
import time

@ServiceProxy.register_service_interface('flip_mount')
class FlipMountProxy(ServiceProxy):
    def move_to(self, position, wait=True):
        position = self.resolve_position(position)

        self.commanded_position.submit_data(np.array([position], dtype='int8'))

        if wait:
            while self.current_position.get()[0] != position:
                try:
                    frame = self.current_position.get_next_frame(10)
                    if frame.data[0] == position:
                        break
                except Exception:
                    # Timed out. No problem.
                    pass

    def move_in_beam(self, wait=True):
        self.move_to('in_beam', wait)

    def move_out_of_beam(self, wait=True):
        self.move_to('out_of_beam', wait)

    def resolve_position(self, position):
        if isinstance(position, str):
            # The position is a named position.
            position = self.positions[position]

            # The position may still be a named position, so try to resolve deeper.
            return self.resolve_position(position)
        else:
            return position

    @property
    def positions(self):
        return self.configuration['positions']
