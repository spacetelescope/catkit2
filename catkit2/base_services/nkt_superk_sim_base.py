"""Base class for NKT SuperK simulated white light sources.

This module provides a common base class for NKT SuperK simulated devices,
eliminating code duplication between EVO and FIANIUM simulation services.
"""

from catkit2.testbed.service import Service

import numpy as np
import threading
from abc import ABC, abstractmethod


class NktSuperkSimBase(Service, ABC):
    """Abstract base class for NKT SuperK simulated white light sources.

    This class contains common functionality shared between different
    NKT SuperK simulated devices like EVO and FIANIUM. Both the SuperK source and
    VARIA simulation are controlled through this service.
    """

    def __init__(self, service_type):
        """Initialize the NKT SuperK simulation base service.

        Args:
            service_type: The specific service type (e.g., 'nkt_superk_evo_sim')
        """
        super().__init__(service_type)

        self.threads = {}
        self.port = self.config['port']

    def open(self):
        """Open the service and initialize data streams."""
        # Common data streams for VARIA
        self.monitor_input = self.make_data_stream('monitor_input', 'float32', [1], 20)

        self.nd_setpoint = self.make_data_stream('nd_setpoint', 'float32', [1], 20)
        self.swp_setpoint = self.make_data_stream('swp_setpoint', 'float32', [1], 20)
        self.lwp_setpoint = self.make_data_stream('lwp_setpoint', 'float32', [1], 20)

        self.nd_filter_moving = self.make_data_stream('nd_filter_moving', 'uint8', [1], 20)
        self.swp_filter_moving = self.make_data_stream('swp_filter_moving', 'uint8', [1], 20)
        self.lwp_filter_moving = self.make_data_stream('lwp_filter_moving', 'uint8', [1], 20)

        # Common data streams for SuperK source
        self.emission = self.make_data_stream('emission', 'uint8', [1], 20)

        # Set initial VARIA setpoints from config
        self.nd_setpoint.submit_data(np.array([self.config['nd_setpoint']], dtype='float32'))
        self.swp_setpoint.submit_data(np.array([self.config['swp_setpoint']], dtype='float32'))
        self.lwp_setpoint.submit_data(np.array([self.config['lwp_setpoint']], dtype='float32'))

        # Set initial emission from config
        self.emission.submit_data(np.array([self.config['emission']], dtype='uint8'))

        # Create device-specific data streams
        self._create_device_specific_streams()

        # Define common thread functions
        common_funcs = {
            'nd_setpoint': self.monitor_func(self.nd_setpoint, self.set_nd_setpoint),
            'swp_setpoint': self.monitor_func(self.swp_setpoint, self.set_swp_setpoint),
            'lwp_setpoint': self.monitor_func(self.lwp_setpoint, self.set_lwp_setpoint),
            'emission': self.monitor_func(self.emission, self.set_emission),
            'varia_status': self.update_func(self.update_varia_status)
        }

        # Get device-specific thread functions and merge
        device_funcs = self._get_device_specific_funcs()
        funcs = {**common_funcs, **device_funcs}

        # Start all threads
        for key, func in funcs.items():
            thread = threading.Thread(target=func)
            thread.start()
            self.threads[key] = thread

    def main(self):
        """Main service loop."""
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        """Close the service and cleanup resources."""
        # Turn off the source
        self.set_emission(0)

        # Device-specific cleanup
        self._device_specific_cleanup()

        # Join all threads
        for thread in self.threads.values():
            thread.join()

    def update_varia_status(self):
        """Update VARIA status information."""
        # Submit simulated results to their respective datastreams
        self.nd_filter_moving.submit_data(np.array([0], dtype='uint8'))
        self.swp_filter_moving.submit_data(np.array([0], dtype='uint8'))
        self.lwp_filter_moving.submit_data(np.array([0], dtype='uint8'))

        self.monitor_input.submit_data(np.array([1], dtype='float32'))

    def monitor_func(self, stream, setter):
        """Create a monitoring function for a data stream."""
        def func():
            while not self.should_shut_down:
                try:
                    frame = stream.get_next_frame(1)
                except Exception:
                    continue

                setter(frame.data[0])

        return func

    def update_func(self, updater):
        """Create an update function that runs periodically."""
        def func():
            while not self.should_shut_down:
                updater()
                self.sleep(1)

        return func

    # Common VARIA simulator operations
    def set_nd_setpoint(self, nd_setpoint):
        """Set ND filter setpoint in simulator."""
        self.testbed.simulator.move_filter(
            filter_wheel_name=self.id + '_nd',
            new_filter_position=nd_setpoint
        )

    def set_swp_setpoint(self, swp_setpoint):
        """Set SWP filter setpoint in simulator."""
        self.testbed.simulator.move_filter(
            filter_wheel_name=self.id + '_swp',
            new_filter_position=swp_setpoint
        )

    def set_lwp_setpoint(self, lwp_setpoint):
        """Set LWP filter setpoint in simulator."""
        self.testbed.simulator.move_filter(
            filter_wheel_name=self.id + '_lwp',
            new_filter_position=lwp_setpoint
        )

    # Abstract methods that must be implemented by subclasses
    @abstractmethod
    def _create_device_specific_streams(self):
        """Create device-specific data streams."""
        pass

    @abstractmethod
    def _get_device_specific_funcs(self):
        """Get device-specific thread functions."""
        pass

    @abstractmethod
    def _device_specific_cleanup(self):
        """Perform device-specific cleanup."""
        pass

    # Abstract method that must be implemented by subclasses
    @abstractmethod
    def set_emission(self, emission):
        """Set emission state for the device in simulator."""
        pass