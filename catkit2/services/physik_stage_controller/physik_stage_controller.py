import numpy as np
import threading
from catkit2.testbed.service import Service
from pipython import GCSDevice, pitools


class PhysikStageController(Service):
    """Service for controlling Physik Instrumente (PI) stages."""

    def __init__(self):
        super().__init__('physik_stage_controller')

        self.pidevice = None
        self.is_initialized = False
        self.is_moving = False
        self.move_event = threading.Event()

        # Create lock for device access
        self.mutex = threading.Lock()

    def open(self):
        """Initialize the PI device and connect."""
        controller_name = self.config.get('controller_name', 'E-727.3SDA')
        serialnum = self.config.get('SN', None)

        if serialnum is None:
            raise Exception('Must have controller serial number in config to find controller')

        # Map axis names to numbers (configurable)
        self.axis_map = self.config.get('axis_map', {
            'x': 1,
            'y': 2
        })

        # Connect to device
        self.pidevice = GCSDevice(controller_name)
        device_found = False

        for device in self.pidevice.EnumerateUSB():
            if serialnum in device:
                self.pidevice.ConnectUSB(serialnum=device)
                self.log.info(f'Connected: {self.pidevice.qIDN().strip()}')
                device_found = True
                break

        if not device_found:
            raise Exception(f'Controller with serial number {serialnum} not found')

        # Initialize stages
        pitools.startup(self.pidevice)

        # Get initial positions from config
        initial_pos = self.config.get('initial_position', None)

        # Move to initial positions (if provided)
        if initial_pos:
            axis_positions = {
                self.axis_map[name]: float(value)
                for name, value in initial_pos.items()
                if name in self.axis_map
            }

            if axis_positions:
                with self.mutex:
                    self.pidevice.MOV(axis_positions)
                    pitools.waitontarget(self.pidevice)

            self.log.info(f'Initial positions: {initial_pos}')

        # Create data streams
        num_axes = len(self.axis_map)
        self.positions = self.make_data_stream('positions', 'float64', [num_axes], 20)
        self.target_positions = self.make_data_stream('target_positions', 'float64', [num_axes], 20)
        # self.target_positions_wait = self.make_data_stream('target_positions_wait', 'float64', [num_axes], 20)

        # Precompute reverse map for speed
        self.axis_num_to_name = {num: name for name, num in self.axis_map.items()}

        # Start the worker threads
        threading.Thread(target=self._target_positions_worker, daemon=True).start()
        self.log.info("Worker Target Positions started with 250ms timeout")

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
            with self.mutex:
                return self.pidevice.qPOS()[axis_num]

        def setter(value):
            self.move_to({name: float(value)})

        self.make_property(f'position_{name}', getter, setter)

    def _submit_positions(self):
        """Submit current hardware positions to telemetry stream."""
        with self.mutex:
            actual = self.pidevice.qPOS()
        pos_array = np.array(
            [actual[num] for num in sorted(self.axis_map.values())],
            dtype='float64'
        )
        self.positions.submit_data(pos_array)

    def _target_positions_worker(self):
        """Worker thread to handle move_to commands from the target_positions data stream."""
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
        """Main loop - polls for move completion and updates telemetry when motion stops."""
        while not self.should_shut_down:
            if self.is_moving:
                with self.mutex:
                    on_target = all(self.pidevice.qONT().values())
                if on_target:
                    self.is_moving = False
                    self.move_event.clear()
                    self._submit_positions()
            self.sleep(0)

    def close(self):
        """Close the PI device connection."""
        if self.pidevice is not None:
            try:
                with self.mutex:
                    self.pidevice.STP()
                    self.pidevice.CloseConnection()
                self.log.info("PI device connection closed")
            except Exception as e:
                self.log.error(f"Error closing PI device: {e}")
            finally:
                self.pidevice = None
                self.is_initialized = False

    def move_to_wrapper(self, positions):
        """Wrapper for move_to command to submit target positions to the data stream."""
        target_move = np.array([positions[name] for name in sorted(self.axis_map.keys())], dtype=np.float64)
        self.target_positions.submit_data(target_move)

    def move_to(self, positions):
        """
        Move to absolute positions without waiting for completion.
        Telemetry is updated asynchronously by the main loop once the stage reaches target.

        Keep in mind telemetry will update only when movement has stopped.

        Parameters
        ----------
        positions : dict
            Dictionary with axis names (e.g., {'x': 10.0, 'y': 20.0})
        """
        if not self.is_initialized:
            raise RuntimeError("Controller not initialized")

        axis_positions = {}
        for name, value in positions.items():
            if name in self.axis_map:
                axis_num = self.axis_map[name]
                axis_positions[axis_num] = float(value)
            else:
                self.log.warning(f"Unknown axis name: {name}")

        if not axis_positions:
            return

        with self.mutex:
            self.pidevice.MOV(axis_positions)

        self.is_moving = True
        self.move_event.set()


    def move_and_wait(self, positions):
        """
        Move to absolute positions and wait for completion.
        Telemetry is updated synchronously before returning.

        Parameters
        ----------
        positions : dict
            Dictionary with axis names (e.g., {'x': 10.0, 'y': 20.0})
        """
        if not self.is_initialized:
            raise RuntimeError("Controller not initialized")

        axis_positions = {}
        for name, value in positions.items():
            if name in self.axis_map:
                axis_num = self.axis_map[name]
                axis_positions[axis_num] = float(value)
            else:
                self.log.warning(f"Unknown axis name: {name}")

        if not axis_positions:
            return

        with self.mutex:
            self.pidevice.MOV(axis_positions)

        self.wait_on_target(timeout=5)
        self._submit_positions()

    def move_relative(self, deltas):
        """
        Move relative to current positions without waiting for completion.
        Queries actual hardware position as the reference point for the relative move.
        Telemetry is updated asynchronously by the main loop once the stage reaches target.

        Keep in mind telemetry will update only when movement has stopped.

        Parameters
        ----------
        deltas : dict
            Dictionary with axis names and relative movements (e.g., {'x': 1.0, 'y': -0.5})
        """
        if not self.is_initialized:
            raise RuntimeError("Controller not initialized")

        absolute_positions = {}

        with self.mutex:
            actual_positions = self.pidevice.qPOS()

        for name, delta in deltas.items():
            if name in self.axis_map:
                axis_num = self.axis_map[name]
                absolute_positions[name] = actual_positions[axis_num] + float(delta)
            else:
                self.log.warning(f"Unknown axis name: {name}")

        if absolute_positions:
            target_move = np.array([absolute_positions[name] for name in sorted(self.axis_map.keys())], dtype=np.float64)
            self.target_positions.submit_data(target_move)

    def move_relative_and_wait(self, deltas):
        """
        Move relative to current positions and wait for completion.
        Queries actual hardware position as the reference point for the relative move.
        Telemetry is updated synchronously before returning.

        Parameters
        ----------
        deltas : dict
            Dictionary with axis names and relative movements (e.g., {'x': 1.0, 'y': -0.5})
        """
        if not self.is_initialized:
            raise RuntimeError("Controller not initialized")

        absolute_positions = {}

        with self.mutex:
            actual_positions = self.pidevice.qPOS()

        for name, delta in deltas.items():
            if name in self.axis_map:
                axis_num = self.axis_map[name]
                absolute_positions[name] = actual_positions[axis_num] + float(delta)
            else:
                self.log.warning(f"Unknown axis name: {name}")

        if absolute_positions:
            self.move_and_wait(absolute_positions)

    def get_positions(self):
        """
        Get current positions from hardware.

        Returns
        -------
        positions : dict
            Dictionary with axis names and actual hardware positions
        """
        if not self.is_initialized:
            raise RuntimeError("Controller not initialized")

        with self.mutex:
            actual = self.pidevice.qPOS()

        return {
            name: actual[axis_num]
            for name, axis_num in self.axis_map.items()
        }

    def stop_motion(self):
        """Stop all motion immediately."""
        if not self.is_initialized:
            return

        try:
            with self.mutex:
                self.pidevice.STP()
            self.is_moving = False
            self.move_event.clear()
            self.log.info("Motion stopped")
        except Exception as e:
            self.log.error(f"Error stopping motion: {e}")

    def wait_on_target(self, timeout=5):
        """
        Wait for all axes to reach their target positions.
        Default timeout is 5 seconds to prevent hanging indefinitely if something goes wrong.

        Parameters
        ----------
        timeout : float, optional
            Maximum time to wait in seconds
        """
        if not self.is_initialized:
            return

        if timeout is not None:
            pitools.waitontarget(self.pidevice, timeout=timeout)
        else:
            pitools.waitontarget(self.pidevice)


if __name__ == '__main__':
    service = PhysikStageController()
    service.run()
