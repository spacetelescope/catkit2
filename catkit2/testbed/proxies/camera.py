from ..service_proxy import ServiceProxy

import warnings

@ServiceProxy.register_service_interface('camera')
class CameraProxy(ServiceProxy):
    def take_raw_exposures(self, num_exposures):
        was_acquiring = self.is_acquiring

        if not was_acquiring:
            self.start_acquisition()

        first_frame_id = self.images.newest_available_frame_id

        if was_acquiring:
            # Ignore first to frames to ensure the frames were taken _after_ the
            # call to this function. This is not necessary if the acquisition just
            # started.
            first_frame_id += 2

        try:
            for i in range(num_exposures):
                yield self.images.get_frame(first_frame_id + i, 100000).data.copy()
        finally:
            if not was_acquiring:
                self.stop_acquisition()

    def take_exposures(self, *args, **kwargs):
        warnings.warn('Please use camera.take_raw_exposures() instead.', DeprecationWarning)
        yield from self.take_raw_exposures(*args, **kwargs)
