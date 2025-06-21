"""
Linux version of Thorlabs cube motor control using pyKDC101 library.
This replaces the Windows Kinesis DLL-based implementation with direct serial communication.
"""
import threading
import time
import numpy as np
import sys
import os
import traceback

# Get pyKDC101 path from environment variable (similar to THORLABS_KINESIS_DLL_PATH)
default_pykdc_path = os.environ.get('PYKDC101_PATH')
if default_pykdc_path is not None:
    sys.path.insert(0, default_pykdc_path)
    print(f"[DEBUG] Added PYKDC101_PATH to sys.path: {default_pykdc_path}")
else:
    raise ValueError(
        'To use Thorlabs cube motors with pyKDC101, you need to set the PYKDC101_PATH environment variable.')

try:
    from core import KDC

    print("[DEBUG] Successfully imported core.KDC")
except ImportError as e:
    print(f"[ERROR] Failed to import core.KDC: {e}")
    print(f"[ERROR] PYKDC101_PATH: {default_pykdc_path}")
    print(f"[ERROR] sys.path: {sys.path}")
    raise ImportError(
        f"Failed to import core.KDC. Make sure PYKDC101_PATH points to the correct directory. Current path: {default_pykdc_path}. Error: {e}")

from catkit2.testbed.service import Service


class ThorlabsCubeMotorKinesis(Service):
    """
    Service for controlling a Thorlabs cube motor using pyKDC101.
    """

    def __init__(self):
        print("[DEBUG] Initializing ThorlabsCubeMotorKinesis service")
        super().__init__('thorlabs_cube_motor_kinesis')

        print(f"[DEBUG] Service config: {self.config}")
        print(f"[DEBUG] Available config keys: {list(self.config.keys())}")

        try:
            self.cube_model = self.config.get('cube_model', 'KDC101')
            self.stage_model = self.config.get('stage_model', 'MTS50-Z8')
            self.motor_positions = self.config.get('positions', {})
            self.serial_number = str(self.config.get('serial_number', '27000001'))
            self.update_interval = self.config.get('update_interval', 1.0)

            print(
                f"[DEBUG] Configuration loaded: cube={self.cube_model}, stage={self.stage_model}, SN={self.serial_number}")

            # Validate supported models
            if self.cube_model not in ['KDC101', 'KDC001']:
                raise ValueError(f"Cube model {self.cube_model} not supported. Only KDC101 and KDC001 are supported.")

            if self.stage_model not in ['MTS25-Z8', 'MTS50-Z8', 'Z825B', 'Z806', 'Z812']:
                raise ValueError(f"Stage model {self.stage_model} not supported.")

            # Read configuration parameters with defaults
            self.min_position_config = self.config.get('min_position', -25.0)
            self.max_position_config = self.config.get('max_position', 25.0)
            self.unit_config = self.config.get('unit', 'mm')

            print(
                f"[DEBUG] Position limits: {self.min_position_config} to {self.max_position_config} {self.unit_config}")

            # Initialize variables
            self.kdc = None
            self.command = None
            self.current_position = None
            self.motor_thread = None
            self._shutdown_flag = False
            self._shutdown_event = threading.Event()  # Better shutdown signaling
            self._is_moving = False  # Track if motor is currently moving

            print("[DEBUG] ThorlabsCubeMotorKinesis initialization complete")

        except Exception as e:
            print(f"[ERROR] Failed during service initialization: {e}")
            print(
                f"[ERROR] Config keys available: {list(self.config.keys()) if hasattr(self, 'config') else 'No config'}")
            traceback.print_exc()
            raise

    def open(self):
        """
        Open connection to the motor.
        """
        print(f"[DEBUG] Opening connection to motor with SN: {self.serial_number}")

        try:
            # Initialize KDC controller with serial number
            print(f"[DEBUG] Creating KDC instance...")
            self.kdc = KDC(SN=self.serial_number, DEBUG=True)  # Enable debug for more info

            if self.kdc.ser is None:
                print(f"[ERROR] KDC serial connection is None")
                raise RuntimeError(
                    f"Failed to connect to KDC101 with serial number {self.serial_number} - serial connection is None")

            if not self.kdc.ser.is_open:
                print(f"[ERROR] KDC serial port is not open")
                raise RuntimeError(
                    f"Failed to connect to KDC101 with serial number {self.serial_number} - serial port not open")

            print(f"[DEBUG] Successfully connected to KDC101 on port {self.kdc.ser.port}")

            # Flash the display to indicate connection
            print("[DEBUG] Flashing display...")
            self.kdc.identify()

            # Log device information
            self.log.info("Successfully connected to KDC101")
            try:
                print("[DEBUG] Getting device info...")
                self.kdc.get_info()
            except Exception as e:
                self.log.warning(f"Could not get device info: {e}")
                print(f"[WARNING] Could not get device info: {e}")

            # Validate unit configuration based on stage model
            if self.stage_model in ['MTS25-Z8', 'MTS50-Z8']:
                expected_unit = 'mm'  # Linear stages
            elif self.stage_model in ['Z825B', 'Z806', 'Z812']:
                expected_unit = 'deg'  # Rotation stages
            else:
                expected_unit = self.unit_config

            if self.unit_config != expected_unit:
                self.log.warning(
                    f"Unit mismatch: config has '{self.unit_config}' but stage '{self.stage_model}' typically uses '{expected_unit}'")

            # Create data streams
            print("[DEBUG] Creating data streams...")
            self.command = self.make_data_stream('command', 'float64', [1], 20)
            self.current_position = self.make_data_stream('current_position', 'float64', [1], 20)

            # Submit initial motor position
            print("[DEBUG] Getting initial position...")
            self.get_current_position()

            # Create commands
            print("[DEBUG] Creating commands...")
            self.make_command('home', self.home)

            # Create properties to match the original service
            print("[DEBUG] Creating properties...")
            self.make_property('serial_number', lambda: self.serial_number, 'string')
            self.make_property('cube_model', lambda: self.cube_model, 'string')
            self.make_property('stage_model', lambda: self.stage_model, 'string')
            self.make_property('unit', lambda: self.unit_config, 'string')
            self.make_property('min_position', lambda: self.min_position_config, 'float64')
            self.make_property('max_position', lambda: self.max_position_config, 'float64')
            self.make_property('is_moving', lambda: self._is_moving, 'bool')  # Expose movement status

            # Start motor monitoring thread
            print("[DEBUG] Starting motor monitoring thread...")
            self._shutdown_flag = False
            self._shutdown_event.clear()
            self.motor_thread = threading.Thread(target=self.monitor_motor)
            self.motor_thread.daemon = True  # Ensure it dies with main process
            self.motor_thread.start()

            self.log.info("ThorlabsCubeMotorKinesis service opened successfully")
            print("[DEBUG] Service opened successfully")

        except Exception as e:
            error_msg = f"Failed to open motor connection: {e}"
            print(f"[ERROR] {error_msg}")
            traceback.print_exc()
            self.log.error(error_msg)

            if self.kdc and hasattr(self.kdc, 'ser') and self.kdc.ser:
                try:
                    print("[DEBUG] Attempting to close KDC connection after error...")
                    self.kdc.closestage()
                except Exception as close_error:
                    print(f"[ERROR] Failed to close KDC after error: {close_error}")

            # Instead of raising the exception (which crashes the service),
            # let's try to continue without the hardware connection
            self.log.error("Service will continue without hardware connection")
            print("[WARNING] Service will continue without hardware connection")

            # Create minimal data streams so the service doesn't crash
            try:
                self.command = self.make_data_stream('command', 'float64', [1], 20)
                self.current_position = self.make_data_stream('current_position', 'float64', [1], 20)
                self.make_command('home', self.home)

                # Create properties even without hardware
                self.make_property('serial_number', lambda: self.serial_number, 'string')
                self.make_property('cube_model', lambda: self.cube_model, 'string')
                self.make_property('stage_model', lambda: self.stage_model, 'string')
                self.make_property('unit', lambda: self.unit_config, 'string')
                self.make_property('min_position', lambda: self.min_position_config, 'float64')
                self.make_property('max_position', lambda: self.max_position_config, 'float64')

                # Submit a default position
                self.current_position.submit_data(np.array([0.0], dtype='float64'))

                print("[DEBUG] Created minimal service interface")
            except Exception as stream_error:
                print(f"[ERROR] Failed to create minimal interface: {stream_error}")
                raise

    def monitor_motor(self):
        """Monitor for new motor commands and execute them."""
        print("[DEBUG] Motor monitoring thread started")
        while not self._shutdown_flag and not self.should_shut_down and not self._shutdown_event.is_set():
            try:
                # Use shorter timeout and check shutdown more frequently
                frame = self.command.get_next_frame(100)  # 100ms timeout for faster shutdown response
                if self.kdc and self.kdc.port_is_open():
                    self.set_current_position(frame.data[0])
                else:
                    self.log.warning("Motor command received but hardware not connected")
            except RuntimeError:
                # Timeout - check shutdown flags again
                continue
            except Exception as e:
                if not self._shutdown_flag and not self._shutdown_event.is_set():
                    self.log.error(f"Error in motor monitoring thread: {e}")
                time.sleep(0.01)  # Brief pause on error
        print("[DEBUG] Motor monitoring thread stopped")

    def main(self):
        """Main service loop - periodically update position."""
        print("[DEBUG] Main service loop started")
        while not self.should_shut_down:
            try:
                if self.kdc and self.kdc.port_is_open():
                    self.get_current_position()
                else:
                    # Submit a default position if no hardware
                    self.current_position.submit_data(np.array([0.0], dtype='float64'))
                self.sleep(self.update_interval)
            except Exception as e:
                self.log.error(f"Error in main loop: {e}")
                self.sleep(1.0)

    def close(self):
        """Clean up and close the motor connection."""
        print("[DEBUG] Starting close() method...")
        self.log.info("Closing ThorlabsCubeMotorKinesis service")

        # Signal all threads to stop immediately
        print("[DEBUG] Setting shutdown flags...")
        self._shutdown_flag = True
        self._shutdown_event.set()

        # Only try to stop movement if motor is actually moving
        if self.kdc and self._is_moving:
            try:
                print("[DEBUG] Motor is moving - stopping movement...")
                self.kdc.stop_move()
                self._is_moving = False
                print("[DEBUG] Movement stopped")
            except Exception as e:
                print(f"[DEBUG] Error stopping movement (ignored): {e}")

        # Force shutdown the motor thread
        if self.motor_thread and self.motor_thread.is_alive():
            print("[DEBUG] Waiting for motor thread to finish...")
            self.motor_thread.join(timeout=0.2)  # Short timeout - 200ms
            if self.motor_thread.is_alive():
                print("[DEBUG] Motor thread still alive - continuing anyway")
            else:
                print("[DEBUG] Motor thread shut down cleanly")

        # Close hardware connection
        if self.kdc:
            try:
                print("[DEBUG] Closing KDC connection...")
                self.kdc.closestage()
                print("[DEBUG] KDC connection closed")
            except Exception as e:
                print(f"[DEBUG] Error closing KDC (ignored): {e}")

        # Clear the reference
        self.kdc = None

        print("[DEBUG] close() method completed")

    def set_current_position(self, position):
        """Set the motor's current position."""
        if not self.kdc or not self.kdc.port_is_open():
            self.log.error("KDC not connected")
            return

        # Validate position range
        if not (self.min_position_config <= position <= self.max_position_config):
            self.log.warning(
                f'Position {position} outside range [{self.min_position_config}, {self.max_position_config}] {self.unit_config}')
            return

        try:
            self._is_moving = True  # Mark that we're starting a movement
            self._target_position = position  # Store target for completion checking
            self._stable_count = 0  # Reset stability counter
            self.kdc.move_abs(position)
            self.log.info(f"Moving to position: {position} {self.unit_config}")
            print(f"[DEBUG] Started move to {position}, is_moving = {self._is_moving}")
            self.get_current_position()
        except Exception as e:
            self._is_moving = False  # Reset on error
            if hasattr(self, '_target_position'):
                delattr(self, '_target_position')
            self.log.error(f"Error setting position {position}: {e}")

    def get_current_position(self):
        """Get current motor position and update data stream."""
        if not self.kdc or not self.kdc.port_is_open():
            return

        try:
            # Try encoder position first
            current_pos = self.kdc.get_enc_angle()

            # Fallback to position counter
            if current_pos is None or current_pos == '':
                current_pos = self.kdc.get_pos_angle()

            if current_pos is not None and current_pos != '':
                self.current_position.submit_data(np.array([current_pos], dtype='float64'))

                # Check if movement has completed
                if self._is_moving:
                    self._check_movement_completion(current_pos)
            else:
                self.log.warning("Failed to read current position")

        except Exception as e:
            self.log.error(f"Error getting current position: {e}")

    def _check_movement_completion(self, current_pos):
        """Check if movement has completed by monitoring position stability."""
        if not hasattr(self, '_target_position'):
            # No target set, can't check completion
            return

        # Check if we're close to the target position
        position_tolerance = 0.1  # Adjust based on your motor's precision
        if abs(current_pos - self._target_position) <= position_tolerance:
            if not hasattr(self, '_stable_count'):
                self._stable_count = 0
            self._stable_count += 1

            # Consider movement complete after position is stable for a few readings
            if self._stable_count >= 3:
                print("[DEBUG] Movement completed - reached target position")
                self._is_moving = False
                self._stable_count = 0
                if hasattr(self, '_target_position'):
                    delattr(self, '_target_position')
        else:
            # Still moving towards target
            self._stable_count = 0

    def wait_for_completion(self):
        """Wait for motor to complete current movement."""
        if not self.kdc or not self.kdc.port_is_open():
            return

        last_position = None
        stable_count = 0
        timeout_count = 0
        max_timeout = 100  # 10 seconds

        while timeout_count < max_timeout:
            try:
                current_pos = self.kdc.get_enc_angle()

                if current_pos is not None:
                    if last_position is not None:
                        if abs(current_pos - last_position) < 0.01:
                            stable_count += 1
                            if stable_count >= 3:
                                break
                        else:
                            stable_count = 0
                    last_position = current_pos

                time.sleep(0.1)
                timeout_count += 1

            except Exception as e:
                self.log.error(f"Error waiting for completion: {e}")
                break

        if timeout_count >= max_timeout:
            self.log.warning("Timeout waiting for movement completion")

    def home(self):
        """Home the motor."""
        if not self.kdc or not self.kdc.port_is_open():
            self.log.error("KDC not connected - cannot home")
            return

        try:
            self.log.info(f"Homing motor {self.serial_number}...")
            self._is_moving = True  # Mark that we're starting a movement
            self.kdc.move_home_wait()
            self._is_moving = False  # Homing completed
            self.log.info(f"Homed - motor {self.serial_number}")
            self.get_current_position()
        except Exception as e:
            self._is_moving = False  # Reset on error
            self.log.error(f"Error during homing: {e}")


if __name__ == '__main__':
    print("[DEBUG] Starting service main...")
    try:
        service = ThorlabsCubeMotorKinesis()
        service.run()
    except Exception as e:
        print(f"[ERROR] Service failed to start: {e}")
        traceback.print_exc()