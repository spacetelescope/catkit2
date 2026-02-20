"""
Simulated Physik Instrumente Stage Controller Service

This simulated service provides the same interface as the real PhysikStageController
but without hardware or motion delays. Moves are instantaneous, making it suitable
for measuring non-motion overhead and testing logic without Windows timer granularity issues.
"""

import numpy as np
import threading
from catkit2.testbed.service import Service


class PhysikStageControllerSim(Service):
    """Simulated service for controlling Physik Instrumente (PI) stages."""

    def __init__(self):
        super().__init__('physik_stage_controller_sim')

        self.is_initialized = False

        # Create lock for simulated device access
        self.mutex = threading.Lock()

        # Store current positions
        self.current_positions = {}

    def open(self):
        """Initialize the simulated PI device."""

        # Map axis names to numbers (configurable)
        self.axis_map = self.config.get('axis_map', {
            'x': 1,
            'y': 2
        })

        # If False, the main loop skips position telemetry for maximum move performance
        self.enable_position_telemetry = self.config.get('enable_position_telemetry', True)

        # Get initial positions from config
        initial_pos = self.config.get('initial_position', None)

        # Only initialize positions when asked, otherwise keep last settings
        if initial_pos:
            for name, axis_num in self.axis_map.items():
                self.current_positions[axis_num] = initial_pos.get(name, 0.0)

            self.log.info(f'Initial positions: {initial_pos}')

        # Create data streams
        num_axes = len(self.axis_map)
        self.positions = self.make_data_stream('positions', 'float64', [num_axes], 20)
        self.target_positions = self.make_data_stream('target_positions', 'float64', [num_axes], 20)

        # Precompute reverse map for speed
        self.axis_num_to_name = {num: name for name, num in self.axis_map.items()}

        # Start the worker thread
        threading.Thread(target=self._target_positions_stream_worker, daemon=True).start()
        self.log.info("Worker started with 250ms timeout")

        self.is_initialized = True

        # Submit initial positions
        self._submit_positions()

        # Create properties for each axis
        for name, axis_num in self.axis_map.items():
            self._make_axis_property(name, axis_num)

        # Create commands
        self.make_command('move_to', self.move_to)
        self.make_command('move_relative', self.move_relative)
        self.make_command('get_positions', self.get_positions)
        self.make_command('stop_motion', self.stop_motion)

    def _make_axis_property(self, name, axis_num):
        """Create a property for an axis."""
        def getter():
            return self.current_positions[axis_num]

        def setter(value):
            self.move_to({name: float(value)})

        self.make_property(f'position_{name}', getter, setter)

    def _submit_positions(self):
        """Submit current positions to telemetry stream."""
        with self.mutex:
            pos_array = np.array([self.current_positions[i] for i in sorted(self.current_positions.keys())],
                                 dtype='float64')
        self.positions.submit_data(pos_array)

    def _target_positions_stream_worker(self):
        while not self.should_shut_down:
            try:
                frame = self.target_positions.get_next_frame(wait_time_in_ms=250)
                data = frame.data
                self.log.info("_target_positions_stream_worker received data: " + str(data))

                positions = {
                    self.axis_num_to_name[num]: float(data[idx])
                    for idx, num in enumerate(sorted(self.axis_map.values()))
                }
                self.move_to(positions)

                self.sleep(0)
            except RuntimeError:
                pass

    def main(self):
        """Main loop - monitor positions."""
        while not self.should_shut_down:
            if self.is_initialized and self.enable_position_telemetry:
                try:
                    self._submit_positions()
                except Exception as e:
                    self.log.error(f"Error reading positions: {e}")

                self.sleep(0.1)  # Update at 10 Hz
            else:
                self.sleep(0)

    def close(self):
        """Close the simulated device connection."""
        self.is_initialized = False
        self.log.info("Simulated PI device connection closed")

    def move_to(self, positions):
        """
        Move to absolute positions.

        Parameters
        ----------
        positions : dict
            Dictionary with axis names (e.g., {'x': 10.0, 'y': 20.0})
        """
        if not self.is_initialized:
            self.log.error("Attempted to move before initialization")
            raise RuntimeError("Controller not initialized")

        # Convert named axes to axis numbers
        axis_positions = {}
        for name, value in positions.items():
            if name in self.axis_map:
                axis_num = self.axis_map[name]
                axis_positions[axis_num] = float(value)
            else:
                self.log.warning(f"Unknown axis name: {name}")

        if not axis_positions:
            self.log.error("No valid axis positions to update")
            return

        # Moves are instantaneous in sim - just update stored positions
        with self.mutex:
            self.current_positions.update(axis_positions)
        
        self._submit_positions()

    def move_relative(self, deltas):
        """
        Move relative to current positions.

        Parameters
        ----------
        deltas : dict
            Dictionary with axis names and relative movements (e.g., {'x': 1.0, 'y': -0.5})
        """
        if not self.is_initialized:
            raise RuntimeError("Controller not initialized")

        # Convert to absolute positions under mutex to avoid racing with move_to
        absolute_positions = {}
        with self.mutex:
            for name, delta in deltas.items():
                if name in self.axis_map:
                    axis_num = self.axis_map[name]
                    absolute_positions[name] = self.current_positions[axis_num] + float(delta)
                else:
                    self.log.warning(f"Unknown axis name: {name}")

        if absolute_positions:
            self.move_to(absolute_positions)

    def get_positions(self):
        """
        Get current positions.

        Returns
        -------
        positions : dict
            Dictionary with axis names and positions
        """
        with self.mutex:
            return {name: self.current_positions[axis_num] for name, axis_num in self.axis_map.items()}

    def stop_motion(self):
        """No-op in sim - moves are instantaneous so there is nothing to stop."""
        if not self.is_initialized:
            return

        self.log.info("Motion stopped (simulated no-op)")

    def wait_on_target(self, timeout=None):
        """
        Wait for all axes to reach their target positions.

        In the sim, moves are instantaneous so this always returns immediately.

        Parameters
        ----------
        timeout : float, optional
            Maximum time to wait in seconds (unused in sim)
        """
        if not self.is_initialized:
            return


if __name__ == '__main__':
    service = PhysikStageControllerSim()
    service.run()