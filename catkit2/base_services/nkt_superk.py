"""Base class for NKT SuperK white light sources.

This module provides a common base class for both hardware and simulation
NKT SuperK devices, eliminating code duplication between all services.
"""

from catkit2.testbed.service import Service

import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading
from enum import Enum
import os
import sys
from abc import ABC, abstractmethod


# Try to import NKT SDK - this will only succeed for hardware services
try:
    sdk_path = os.path.join(os.environ.get('NKTP_SDK_PATH'), 'Examples', 'DLL_Example_Python')
    if sdk_path is not None:
        sys.path.append(sdk_path)

    from NKTP_DLL import *
    NKT_SDK_AVAILABLE = True
except ImportError:
    NKT_SDK_AVAILABLE = False


class Varia(Enum):
    """Registers for the NKT SuperK VARIA device."""
    DEVICE_ID = 16

    # SuperK VARIA registers
    REG_MONITOR_INPUT = 0x13

    REG_ND_SETPOINT = 0x32
    REG_SWP_SETPOINT = 0x33
    REG_LWP_SETPOINT = 0x34

    REG_STATUS_BITS = 0x66


def read_register(read_func, register, *, ratio=1, index=-1):
    """Helper function to create register read methods."""
    def getter(self):
        device_id = register.__class__.DEVICE_ID

        future = self.pool.submit(read_func, self.port, device_id.value, register.value, index)
        result, value = future.result()

        self.check_result(result)

        return value * ratio

    return getter


def write_register(write_func, register, *, ratio=1, index=-1):
    """Helper function to create register write methods."""
    def setter(self, value):
        device_id = register.__class__.DEVICE_ID

        # Convert the value to the register value. This assumes integer types.
        register_value = int(value / ratio)

        self.log.debug(f'Writing value {register_value} to {register}.')

        future = self.pool.submit(write_func, self.port, device_id.value, register.value, register_value, index)
        result = future.result()

        self.check_result(result)

    return setter


class NktSuperk(Service, ABC):
    """Abstract base class for NKT SuperK white light sources.

    This class contains common functionality shared between different
    NKT SuperK devices (both hardware and simulation). Both the SuperK source and
    VARIA are controlled through this service due to the need for a
    single open port to the device (for hardware) or consistent simulation behavior.
    """

    def __init__(self, service_type):
        """Initialize the NKT SuperK service.

        Args:
            service_type: The specific service type (e.g., 'nkt_superk_evo')
        """
        super().__init__(service_type)

        self.threads = {}
        self.port = self.config['port']
        self.is_simulation = 'sim' in service_type

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

        # Initialize hardware communication if not simulation
        if not self.is_simulation:
            if not NKT_SDK_AVAILABLE:
                raise RuntimeError('NKT SDK is required for hardware services but not available. '
                                   'Install the SDK and check the NKTP_SDK_PATH environment variable.')

            # Create a pool with a single worker to perform communication with the device
            self.pool = ThreadPoolExecutor(max_workers=1)

            # Open port
            future = self.pool.submit(openPorts, self.port, autoMode=0, liveMode=0)
            self.check_result(future.result())

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

        # Close hardware resources if not simulation
        if not self.is_simulation:
            # Close port
            future = self.pool.submit(closePorts, self.port)
            self.check_result(future.result())

            # Close pool
            self.pool.shutdown()

    def check_result(self, result):
        """Check if an NKT SDK operation was successful.

        Only used for hardware services.
        """
        if not self.is_simulation and result != 0:
            self.log.error('NKT error: ' + RegisterResultTypes(result))
            raise RuntimeError(RegisterResultTypes(result))

    def update_varia_status(self):
        """Update VARIA status information."""
        if self.is_simulation:
            # Submit simulated results to their respective datastreams
            self.nd_filter_moving.submit_data(np.array([0], dtype='uint8'))
            self.swp_filter_moving.submit_data(np.array([0], dtype='uint8'))
            self.lwp_filter_moving.submit_data(np.array([0], dtype='uint8'))

            self.monitor_input.submit_data(np.array([1], dtype='float32'))
        else:
            # Hardware status update
            status = self.get_varia_status_bits()

            # Extract moving filters from status
            nd_filter_moving = (status & (2 << 12)) > 0
            swp_filter_moving = (status & (2 << 13)) > 0
            lwp_filter_moving = (status & (2 << 14)) > 0

            # Submit results to their respective datastreams
            self.nd_filter_moving.submit_data(np.array([nd_filter_moving], dtype='uint8'))
            self.swp_filter_moving.submit_data(np.array([swp_filter_moving], dtype='uint8'))
            self.lwp_filter_moving.submit_data(np.array([lwp_filter_moving], dtype='uint8'))

            # Update input monitor
            monitor_input = self.get_monitor_input()
            self.monitor_input.submit_data(np.array([monitor_input], dtype='float32'))

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

    # VARIA setpoint methods - different implementation for hardware vs simulation
    def set_nd_setpoint(self, nd_setpoint):
        """Set ND filter setpoint."""
        if self.is_simulation:
            self.testbed.simulator.move_filter(
                filter_wheel_name=self.id + '_nd',
                new_filter_position=nd_setpoint
            )
        else:
            self._set_nd_setpoint_hardware(nd_setpoint)

    def set_swp_setpoint(self, swp_setpoint):
        """Set SWP filter setpoint."""
        if self.is_simulation:
            self.testbed.simulator.move_filter(
                filter_wheel_name=self.id + '_swp',
                new_filter_position=swp_setpoint
            )
        else:
            self._set_swp_setpoint_hardware(swp_setpoint)

    def set_lwp_setpoint(self, lwp_setpoint):
        """Set LWP filter setpoint."""
        if self.is_simulation:
            self.testbed.simulator.move_filter(
                filter_wheel_name=self.id + '_lwp',
                new_filter_position=lwp_setpoint
            )
        else:
            self._set_lwp_setpoint_hardware(lwp_setpoint)

    # Hardware register operations (only used by hardware services)
    def _set_nd_setpoint_hardware(self, nd_setpoint):
        """Set ND filter setpoint using hardware register."""
        device_id = Varia.DEVICE_ID
        register_value = int(nd_setpoint / 0.1)

        self.log.debug(f'Writing value {register_value} to {Varia.REG_ND_SETPOINT}.')

        future = self.pool.submit(registerWriteU16, self.port, device_id.value,
                                  Varia.REG_ND_SETPOINT.value, register_value, -1)
        result = future.result()
        self.check_result(result)

    def _set_swp_setpoint_hardware(self, swp_setpoint):
        """Set SWP filter setpoint using hardware register."""
        device_id = Varia.DEVICE_ID
        register_value = int(swp_setpoint / 0.1)

        self.log.debug(f'Writing value {register_value} to {Varia.REG_SWP_SETPOINT}.')

        future = self.pool.submit(registerWriteU16, self.port, device_id.value,
                                  Varia.REG_SWP_SETPOINT.value, register_value, -1)
        result = future.result()
        self.check_result(result)

    def _set_lwp_setpoint_hardware(self, lwp_setpoint):
        """Set LWP filter setpoint using hardware register."""
        device_id = Varia.DEVICE_ID
        register_value = int(lwp_setpoint / 0.1)

        self.log.debug(f'Writing value {register_value} to {Varia.REG_LWP_SETPOINT}.')

        future = self.pool.submit(registerWriteU16, self.port, device_id.value,
                                  Varia.REG_LWP_SETPOINT.value, register_value, -1)
        result = future.result()
        self.check_result(result)

    # Hardware register read operations (only defined for hardware services)
    def get_monitor_input(self):
        """Get monitor input value from hardware."""
        if self.is_simulation:
            return 1.0  # Return simulated value

        device_id = Varia.DEVICE_ID
        future = self.pool.submit(registerReadU16, self.port, device_id.value,
                                  Varia.REG_MONITOR_INPUT.value, -1)
        result, value = future.result()
        self.check_result(result)
        return value * 0.1

    def get_nd_setpoint(self):
        """Get ND filter setpoint from hardware."""
        if self.is_simulation:
            return self.nd_setpoint.get_last_frame().data[0]

        device_id = Varia.DEVICE_ID
        future = self.pool.submit(registerReadU16, self.port, device_id.value,
                                  Varia.REG_ND_SETPOINT.value, -1)
        result, value = future.result()
        self.check_result(result)
        return value * 0.1

    def get_swp_setpoint(self):
        """Get SWP filter setpoint from hardware."""
        if self.is_simulation:
            return self.swp_setpoint.get_last_frame().data[0]

        device_id = Varia.DEVICE_ID
        future = self.pool.submit(registerReadU16, self.port, device_id.value,
                                  Varia.REG_SWP_SETPOINT.value, -1)
        result, value = future.result()
        self.check_result(result)
        return value * 0.1

    def get_lwp_setpoint(self):
        """Get LWP filter setpoint from hardware."""
        if self.is_simulation:
            return self.lwp_setpoint.get_last_frame().data[0]

        device_id = Varia.DEVICE_ID
        future = self.pool.submit(registerReadU16, self.port, device_id.value,
                                  Varia.REG_LWP_SETPOINT.value, -1)
        result, value = future.result()
        self.check_result(result)
        return value * 0.1

    def get_varia_status_bits(self):
        """Get VARIA status bits from hardware."""
        if self.is_simulation:
            return 0  # Return simulated status

        device_id = Varia.DEVICE_ID
        future = self.pool.submit(registerReadU16, self.port, device_id.value,
                                  Varia.REG_STATUS_BITS.value, -1)
        result, value = future.result()
        self.check_result(result)
        return value

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

    # Abstract register operations that must be implemented by subclasses
    @abstractmethod
    def set_emission(self, emission):
        """Set emission state for the device."""
        pass
