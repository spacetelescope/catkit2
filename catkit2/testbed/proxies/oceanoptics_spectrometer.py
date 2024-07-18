from ..service_proxy import ServiceProxy

@ServiceProxy.register_service_interface('oceanoptics_spectrometer')
class OceanopticsSpectroProxy(ServiceProxy):

    def take_raw_exposures(self, num_exposures):
        first_frame_id = self.spectra.newest_available_frame_id

        i = 0
        num_exposures_remaining = num_exposures

        while num_exposures_remaining >= 1:
            try:
                frame = self.spectra.get_frame(first_frame_id + i, 1000)
            except RuntimeError:
                # The frame wasn't available anymore because we were waiting too long.
                continue
            finally:
                i += 1

            yield frame.data.copy()
            num_exposures_remaining -= 1
