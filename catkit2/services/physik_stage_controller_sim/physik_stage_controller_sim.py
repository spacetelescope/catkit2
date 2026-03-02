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
        self.is_moving = False
        self.move_event = threading.Event()
        self.mutex = threading.Lock()
        self.hardware_positions = {}

    def open(self):
        """Initialize the simulated PI device."""
        # Map axis names to numbers (configurable)
        self.axis_map = self.config.get('axis_map', {'x': 1, 'y': 2})

        # Initialize positions
        initial_pos = self.config.get('initial_position', {})
        with self.mutex:
            for name, axis_num in self.axis_map.items():
                self.hardware_positions[axis_num] = float(initial_pos.get(name, 0.0))
        if initial_pos:
            self.log.info(f'Initial positions: {initial_pos}')

        # Create data streams
        num_axes = len(self.axis_map)
        self.positions = self.make_data_stream('positions', 'float64', [num_axes], 20)
        self.target_positions = self.make_data_stream('target_positions', 'float64', [num_axes], 20)

        # Precompute reverse map
        self.axis_num_to_name = {num: name for name, num in self.axis_map.items()}

        # Start worker threads
        threading.Thread(target=self._target_positions_worker, daemon=True).start()
        self.log.info("Worker Target Positions started")

        # Submit initial positions
        self._submit_positions()

        # Create properties for each axis
        for name, axis_num in self.axis_map.items():
            self._make_axis_property(name, axis_num)

        # Create commands
        self.make_command('move_to', self.move_to_wrapper)
        self.make_command('move_and_wait', self.move_and_wait)
        self.make_command('move_relative', self.move_relative)
        self.make_command('move_relative_and_wait', self.move_relative_and_wait)
        self.make_command('get_positions', self.get_positions)
        self.make_command('stop_motion', self.stop_motion)

        self.is_initialized = True

    def _make_axis_property(self, name, axis_num):
        """Create a property for an axis."""
        def getter():
            return self.hardware_positions[axis_num]

        def setter(value):
            self.move_to({name: float(value)})

        self.make_property(f'position_{name}', getter, setter)

    def _submit_positions(self):
        """Submit current positions to telemetry."""
        with self.mutex:
            pos_array = np.array(
                [self.hardware_positions[i] for i in sorted(self.hardware_positions.keys())],
                dtype=np.float64
            )
        self.positions.submit_data(pos_array)

    def _target_positions_worker(self):
        """Worker thread for move_to data stream."""
        while not self.should_shut_down:
            try:
                frame = self.target_positions.get_next_frame(wait_time_in_ms=250)
                data = frame.data
                positions = {
                    self.axis_num_to_name[num]: float(data[idx])
                    for idx, num in enumerate(sorted(self.axis_map.values()))
                }
                self.move_to(positions)
                self.sleep(0)
            except RuntimeError:
                pass

    def main(self):
        """Main loop - in sim moves are instantaneous so is_moving is always immediately false."""
        while not self.should_shut_down:
            if self.is_moving:
                # In sim moves are instantaneous so we can immediately mark as complete
                self.is_moving = False
                self.move_event.clear()
                self._submit_positions()
            self.sleep(0)

    def close(self):
        """Close the simulated device connection."""
        self.stop_motion()
        self.is_initialized = False
        self.log.info("Simulated PI device connection closed")

    def move_to_wrapper(self, positions):
        """Wrapper for move_to command to submit target positions to the data stream."""
        target_move = np.array([positions[name] for name in sorted(self.axis_map.keys())], dtype=np.float64)
        self.target_positions.submit_data(target_move)

    def move_to(self, positions):
        """Move to absolute positions (instantaneous)."""
        if not self.is_initialized:
            raise RuntimeError("Controller not initialized")
        axis_positions = {self.axis_map[name]: float(value) for name, value in positions.items() if name in self.axis_map}
        if axis_positions:
            with self.mutex:
                self.hardware_positions.update(axis_positions)
            self.is_moving = True
            self.move_event.set()

    def move_and_wait(self, positions):
        """Move to absolute positions and wait (instantaneous)."""
        self.move_to(positions)
        self._submit_positions()

    def move_relative(self, deltas):
        """Move relative to current positions (instantaneous)."""
        if not self.is_initialized:
            raise RuntimeError("Controller not initialized")
        with self.mutex:
            absolute_positions = {
                name: self.hardware_positions[self.axis_map[name]] + float(delta)
                for name, delta in deltas.items() if name in self.axis_map
            }
        if absolute_positions:
            self.move_to_wrapper(absolute_positions)

    def move_relative_and_wait(self, deltas):
        """Move relative to current positions and wait (instantaneous)."""
        with self.mutex:
            absolute_positions = {
                name: self.hardware_positions[self.axis_map[name]] + float(delta)
                for name, delta in deltas.items() if name in self.axis_map
            }
        if absolute_positions:
            self.move_and_wait(absolute_positions)

    def get_positions(self):
        """Return current hardware positions."""
        with self.mutex:
            return {name: self.hardware_positions[axis_num] for name, axis_num in self.axis_map.items()}

    def stop_motion(self):
        """No-op (sim moves are instantaneous)."""
        self.is_moving = False
        self.move_event.clear()
        self.log.info("Motion stopped (simulated no-op)")

    def wait_on_target(self, timeout=None):
        """Sim moves are instantaneous, so return immediately."""
        pass


if __name__ == '__main__':
    service = PhysikStageControllerSim()
    service.run()
