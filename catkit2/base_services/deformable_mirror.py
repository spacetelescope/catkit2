from ..testbed.service import Service

import threading
import numpy as np
from astropy.io import fits


class DeformableMirrorService(Service):
    def __init__(self, service_type):
        super().__init__(service_type)

        self.startup_maps = self.config.get('startup_maps', {})
        fname = self.config.get('device_actuator_mask_fname', None)

        if fname is not None:
            self.device_actuator_mask = fits.getdata(fname).astype('bool')
            if self.device_actuator_mask.ndim <= 1:
                raise ValueError(f'The provided device actuator mask needs for {self.service_id} to be at least a 2D array.')
            elif self.device_actuator_mask.ndim == 2:
                self.device_actuator_mask = np.expand_dims(self.device_actuator_mask, axis=0)
        else:
            raise ValueError(f'Need to provide device actuator mask for {self.service_id}')

        self.num_dms = self.device_actuator_mask.shape[0]
        self.dm_shape = self.device_actuator_mask[0].shape
        self.num_actuators = np.sum(self.device_actuator_mask[0])

        self.channels = {}
        self.channel_threads = {}
        for channel in self.config['channels']:
            self.add_channel(channel)

        channel_names = list(channel.lower() for channel in self.config['channels'])
        self.make_property('channels', lambda: channel_names)

        self.total_voltage = self.make_data_stream('total_voltage', 'float64', [self.dm_command_length], 20)
        self.total_surface = self.make_data_stream('total_surface', 'float64', [self.dm_command_length], 20)

    @property
    def dm_command_length(self):
        '''The command length of the DM(s).
        '''
        return self.num_actuators * self.num_dms

    def add_channel(self, channel_name):
        '''Add a channel for this DM.

        This creates the data stream and applies a startup map to the channel.

        Parameters
        ----------
        channel_name : str
            The name of the channel.

        Raises
        ------
        ValueError
            When the provided startup map has the wrong shape.
        '''
        self.channels[channel_name] = self.make_data_stream(channel_name.lower(), 'float64', [self.dm_command_length], 20)

        # Get the right default flat map.
        if channel_name in self.startup_maps:
            with fits.open(self.startup_maps[channel_name]) as f:
                startup_map_command = f['COMMAND'].data.astype('float64')
        else:
            startup_map_command = np.zeros(self.dm_command_length)

        self.channels[channel_name].submit_data(startup_map_command)

    def open(self):
        '''Open the DM.
        '''
        self.channel_threads = {}

        # Start channel monitoring threads
        for channel_name in self.channels.keys():
            thread = threading.Thread(target=self.monitor_channel, args=(channel_name,))
            thread.start()

            self.channel_threads[channel_name] = thread

    def main(self):
        '''Main loop.
        '''
        while not self.should_shut_down:
            self.sleep(0.1)

    def close(self):
        '''Close the DM.
        '''
        for thread in self.channel_threads.values():
            thread.join()

        self.channel_threads = {}

    def monitor_channel(self, channel_name):
        '''Monitors and applies DM commands submitted to a DM channel datastream.

        Parameters
        ----------
        channel_name : str
            The name of the channel.
        '''
        while not self.should_shut_down:
            try:
                self.channels[channel_name].get_next_frame(10)
            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            self.update_dm()

    def update_dm(self):
        '''Update the surface of the DM.

        This co-adds all the DM commands from each channel and applies it to the DM.
        '''
        # Add up all channels to get the total surface.
        total_surface = 0
        for stream in self.channels.values():
            total_surface += stream.get_latest_frame().data

        # Apply the command on the DM.
        self.send_surface(total_surface)

    def send_surface(self, surface):
        '''Send a surface map to the DM(s).

        Parameters
        ----------
        surface : ndarray
            The requested surface of the DM(s).
        '''
        raise NotImplementedError('send_surface() must be implemented by subclasses.')
