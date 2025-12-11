"""
Simulated Physik Instrumente Stage Controller Service

This simulated service provides the same interface as the real PhysikStageController
but doesn't require actual hardware. Useful for testing and development.
"""

import numpy as np
import threading
from catkit2.testbed.service import Service
import time


class PhysikStageControllerSim(Service):
    """Simulated service for controlling Physik Instrumente (PI) stages."""

    def __init__(self):
        super().__init__('physik_stage_controller_sim')

        # Create lock for simulated device access
        self.mutex = threading.Lock()

        # Store current and target positions
        self.current_positions = {}
        self.target_positions = {}

        # Simulation parameters
        self.motion_speed = self.config.get('motion_speed', 10.0)  # units per second
        self.position_tolerance = self.config.get('position_tolerance', 0.001)  # tolerance for "on target"
        self.update_rate = self.config.get('update_rate', 100.0)  # Hz for position updates

        # Motion state
        self.is_moving = False
        self.motion_start_time = None

    def open(self):
        """Initialize the simulated PI device."""

        # Map axis names to numbers (configurable)
        self.axis_map = self.config.get('axis_map', {
            'x': 1,
            'y': 2
        })

        # Get initial positions from config
        initial_pos = self.config.get('initial_position', None)

        # only initialized positions when asked, otherwise keep last settings
        if initial_pos:
            # Initialize current positions
            for name, axis_num in self.axis_map.items():
                self.current_positions[axis_num] = initial_pos.get(name, 0.0)

            self.log.info(f'Initial positions: {self.current_positions}')
            self.target_positions = self.current_positions

        # Create data streams for telemetry
        num_axes = len(self.axis_map)
        self.log.info(f'num_axis={num_axes}, axis_map={self.axis_map}')
        self.positions = self.make_data_stream('positions', 'float64', [num_axes], 20)
        self.target_positions_stream = self.make_data_stream('target_positions', 'float64', [num_axes], 20)
        self.is_moving_stream = self.make_data_stream('is_moving', 'int8', [1], 20)

        # Submit initial state
        self._submit_positions()
        self.is_moving_stream.submit_data(np.array([0], dtype='int8'))

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
        pos_array = np.array([self.current_positions[i] for i in sorted(self.current_positions.keys())],
                             dtype='float64')
        self.positions.submit_data(pos_array)

        target_array = np.array([self.target_positions[i] for i in sorted(self.target_positions.keys())],
                                 dtype='float64')
        self.log.info(f'submitting {target_array}')
        self.target_positions_stream.submit_data(target_array)

    def _update_simulated_motion(self):
        """Update positions to simulate smooth motion towards targets."""
        with self.mutex:
            dt = 1.0 / self.update_rate
            max_step = self.motion_speed * dt

            any_moving = False

            for axis_num in self.current_positions.keys():
                current = self.current_positions[axis_num]
                target = self.target_positions[axis_num]
                error = target - current

                if abs(error) > self.position_tolerance:
                    any_moving = True
                    # Move towards target with limited speed
                    step = np.clip(error, -max_step, max_step)
                    self.current_positions[axis_num] = current + step

            self.is_moving = any_moving

        return any_moving

    def main(self):
        """Main loop - simulate motion and update positions."""
        sleep_time = 1.0 / self.update_rate

        while not self.should_shut_down:
            # Update simulated motion
            is_moving = self._update_simulated_motion()

            # Submit telemetry
            self._submit_positions()
            self.is_moving_stream.submit_data(np.array([1 if is_moving else 0], dtype='int8'))

            self.sleep(sleep_time)

    def close(self):
        """Close the simulated device connection."""
        self.log.info("Simulated PI device connection closed")

    def move_to(self, positions):
        """
        Move to absolute positions.

        Parameters
        ----------
        positions : dict
            Dictionary with axis names (e.g., {'x': 10.0, 'y': 20.0})
        """
        # Convert named axes to axis numbers
        with self.mutex:
            for name, value in positions.items():
                if name in self.axis_map:
                    axis_num = self.axis_map[name]
                    self.target_positions[axis_num] = float(value)
                    self.log.info(f"Moving axis {name} to {value}")
                else:
                    self.log.warning(f"Unknown axis name: {name}")

            self.is_moving = True
            self.motion_start_time = time.time()

    def move_relative(self, deltas):
        """
        Move relative to current positions.

        Parameters
        ----------
        deltas : dict
            Dictionary with axis names and relative movements (e.g., {'x': 1.0, 'y': -0.5})
        """
        # Convert to absolute positions
        absolute_positions = {}
        with self.mutex:
            for name, delta in deltas.items():
                if name in self.axis_map:
                    axis_num = self.axis_map[name]
                    # Use target position, not current, to avoid drift during motion
                    absolute_positions[name] = self.target_positions[axis_num] + float(delta)
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
            positions = {}
            for name, axis_num in self.axis_map.items():
                positions[name] = self.current_positions[axis_num]
        return positions

    def stop_motion(self):
        """Stop all motion immediately by setting targets to current positions."""
        with self.mutex:
            for axis_num in self.current_positions.keys():
                self.target_positions[axis_num] = self.current_positions[axis_num]
            self.is_moving = False
        self.log.info("Motion stopped (simulated)")

    def wait_on_target(self, timeout=None):
        """
        Wait for all axes to reach their target positions.

        Parameters
        ----------
        timeout : float, optional
            Maximum time to wait in seconds
        """
        start_time = time.time()

        while self.is_moving:
            if timeout is not None and (time.time() - start_time) > timeout:
                self.log.warning("Wait on target timed out")
                return False
            time.sleep(0.01)

        return True


if __name__ == '__main__':
    service = PhysikStageControllerSim()
    service.run()
