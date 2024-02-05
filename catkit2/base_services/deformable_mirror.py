from ..testbed.service import Service

import threading
import numpy as np
from astropy.io import fits


class DeformableMirrorService(Service):
    def __init__(self, service_type):
        super().__init__(service_type)

        self.startup_maps = self.config.get('startup_maps', {})

        self.lock = threading.Lock()

        self.channels = {}
        self.channel_threads = {}
        for channel in self.config['channels']:
            self.add_channel(channel)

        channel_names = list(channel.lower() for channel in self.config['channels'])
        self.make_property('channels', lambda: channel_names)

        self.total_voltage = self.make_data_stream('total_voltage', 'float64', [self.command_length], 20)
        self.total_surface = self.make_data_stream('total_surface', 'float64', [self.command_length], 20)

    def add_channel(self, channel_name):
        self.channels[channel_name] = self.make_data_stream(channel_name.lower(), 'float64', [self.command_length], 20)

        # Get the right default flat map.
        if channel_name in self.startup_maps:
            flatmap = fits.getdata(self.startup_maps[channel_name]).astype('float64')
        else:
            flatmap = np.zeros(self.command_length)

        self.channels[channel_name].submit_data(flatmap)

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
            total_surface += stream.get_latest_frame().data

        # Apply the command on the DM.
        self.send_surface(total_surface)

    def send_surface(self, total_surface):
        raise NotImplementedError()
