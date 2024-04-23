from ..testbed.service import Service

import threading
import numpy as np
from astropy.io import fits


class DeformableMirrorService(Service):
    def __init__(self, service_type):
        super().__init__(service_type)

        self.startup_maps = self.config.get('startup_maps', {})
        self._discretized_voltages = None

        dm_shape = tuple(self.config['dm_shape'])
        fname = self.config.get('controlled_actuator_mask_fname', None)

        if fname is not None:
            self.controlled_actuator_mask = fits.getdata(fname).astype('bool')
        else:
            self.controlled_actuator_mask = np.ones(dm_shape, dtype='bool')

        # Check if shapes from mask and DM shape from config match.
        assert np.allclose(self.controlled_actuator_mask.shape, dm_shape)

        self.num_actuators = np.sum(self.controlled_actuator_mask)

        self.lock = threading.Lock()

        self.channels = {}
        self.channel_threads = {}
        for channel in self.config['channels']:
            self.add_channel(channel)

        channel_names = list(channel.lower() for channel in self.config['channels'])
        self.make_property('channels', lambda: channel_names)

        self.total_voltage = self.make_data_stream('total_voltage', 'float64', [self.num_actuators], 20)
        self.total_surface = self.make_data_stream('total_surface', 'float64', [self.num_actuators], 20)

    def add_channel(self, channel_name):
        self.channels[channel_name] = self.make_data_stream(channel_name.lower(), 'float64', [self.num_actuators], 20)

        # Get the right default flat map.
        if channel_name in self.startup_maps:
            startup_map = fits.getdata(self.startup_maps[channel_name]).astype('float64')
        else:
            startup_map = np.zeros(self.num_actuators)

        self.channels[channel_name].submit_data(startup_map)

    def open(self):
        self.channel_threads = {}

        # Start channel monitoring threads
        for channel_name in self.channels.keys():
            thread = threading.Thread(target=self.monitor_channel, args=(channel_name,))
            thread.start()

            self.channel_threads[channel_name] = thread

    def main(self):
        while not self.should_shut_down:
            self.sleep(0.1)

    def close(self):
        for thread in self.channel_threads.values():
            thread.join()

        self.channel_threads = {}

    def monitor_channel(self, channel_name):
        while not self.should_shut_down:
            try:
                self.channels[channel_name].get_next_frame(10)
            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            self.update_dm()

    def update_dm(self):
        # Add up all channels to get the total surface.
        total_surface = 0
        for stream in self.channels.values():
            total_surface += stream.get()  # TODO: Or: stream.get_latest_frame().data ?

        # Apply the command on the DM.
        self.send_surface(total_surface)

    def send_surface(self, total_surface):
        # Submit this surface to the total surface data stream.
        self.total_surface.submit_data(total_surface)

        # Submit the discretized voltages to the total voltage data stream.
        self.total_voltage.submit_data(self.discretized_voltages)

    @property
    def discretized_voltages(self):
        return self._discretized_voltages

    @discretized_voltages.setter
    def discretized_voltages(self, voltages):
        dac_bit_depth = self.config['dac_bit_depth']

        value = voltages
        if dac_bit_depth is not None:
            value = (np.floor(voltages * (2**dac_bit_depth))) / (2**dac_bit_depth)
        self._discretized_voltages = value