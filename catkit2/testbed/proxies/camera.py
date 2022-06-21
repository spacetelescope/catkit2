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
            # Ignore first two frames to ensure the frames were taken _after_ the
            # call to this function. This is not necessary if the acquisition just
            # started.
            first_frame_id += 2

        try:
            i = 0
            num_exposures_remaining = num_exposures

            while num_exposures_remaining >= 1:
                try:
                    frame = self.images.get_frame(first_frame_id + i, 100000)
                except RuntimeError:
                    # The frame wasn't available anymore because we were waiting too long.
                    continue
                finally:
                    i += 1

                yield frame.data.copy()
                num_exposures_remaining -= 1
        finally:
            if not was_acquiring:
                self.stop_acquisition()

    def take_exposures(self, *args, **kwargs):
        warnings.warn('Please use camera.take_raw_exposures() instead.', DeprecationWarning)
        yield from self.take_raw_exposures(*args, **kwargs)
