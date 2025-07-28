from catkit2.testbed.service import Service
import serial
import time
import numpy as np
import math 
import threading 

class ConexAxis:
    def __init__(self, port, baudrate, service=None):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self._is_moving = False 
        self.service = service 

    def open(self):
        self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=0.5)
        time.sleep(0.1)
        self._flush()

    def _write(self, cmd):
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port not open.")
        self.ser.write((cmd + '\r\n').encode())
        time.sleep(0.05)

    def _read(self):
        return self.ser.readline().decode().strip()

    def _flush(self):
        if self.ser.in_waiting:
            self.ser.read(self.ser.in_waiting)

    def home(self):
        self._write('1OR')
        self._wait_until_done()
        self._write('1MM1')

    def move_to_position(self, position_mm):
        if self.service and self.service.should_shut_down:
            self._is_moving = False
            return
        self._is_moving = True
        try:
            self._write(f'1PA{position_mm}')
            start_time = time.time()
            while time.time() - start_time < 60:
                if self.service and self.service.should_shut_down:
                    self._write('1ST')
                    break
                self._write('1TS')
                status = self._read()
                if status.endswith(('32', '33', '34')):
                    break
                time.sleep(0.1)
        finally:
            self._is_moving = False 

    def get_current_position(self):
        self._write('1TP')
        reply = self._read()
        try:
            return float(reply[3:])
        except Exception:
            return float('nan')

    def _wait_until_done(self):
        timeout = time.time() + 60
        while time.time() < timeout:
            if self.service and self.service.should_shut_down:
                self._write('1ST')
                self._is_moving = False
                return
            self._write('1TS')
            status = self._read()
            if status.endswith(('32', '33', '34')):
                return
            time.sleep(0.1)

    def stop_movement(self):
        if self.ser and self.ser.is_open:
            self._write('1ST')
            self._is_moving = False 

    def is_moving(self):
        return self._is_moving 


class ConexFPM(Service):
    def __init__(self):
        super().__init__('conex')
        self.hor = None
        self.ver = None
        self.foc = None

        self.command_stream = None
        self.position_stream = None

        self.make_command('get_all_position', self.get_all_position)
        self.make_command('move_all_position', self.move_all_position)

        self.make_property('is_moving', lambda: self.any_axis_moving(), 'bool')

        self.make_property('hor_position', lambda: self.hor.get_current_position() if self.hor else float('nan'), 'float64')
        self.make_property('ver_position', lambda: self.ver.get_current_position() if self.ver else float('nan'), 'float64')
        self.make_property('foc_position', lambda: self.foc.get_current_position() if self.foc else float('nan'), 'float64')

        self.VBOUND = 26.5
        self.HBOUND_lower = 3
        self.HBOUND_upper = 26.5
        self.FBOUND = 26.5

    def any_axis_moving(self):
        return any([
            self.hor and self.hor.is_moving(),
            self.ver and self.ver.is_moving(),
            self.foc and self.foc.is_moving()
        ])

    def check_positions(self, pos):
        if not isinstance(pos, (list, tuple, np.ndarray)) or len(pos) != 3:
            raise ValueError("Position must be a vector of length 3")
        h, v, f = pos
        if not math.isnan(v) and v > self.VBOUND:
            self.log.warning(f"Vertical position {v} exceeds max bound {self.VBOUND}. Changing to {self.VBOUND}")
            v = self.VBOUND
        if not math.isnan(h):
            if h > self.HBOUND_upper:
                self.log.warning(f"Horizontal position {h} exceeds max bound {self.HBOUND_upper}. Changing to {self.HBOUND_upper}")
                h = self.HBOUND_upper
            elif h < self.HBOUND_lower:
                self.log.warning(f"Horizontal position {h} is below min bound {self.HBOUND_lower}. Changing to {self.HBOUND_lower}")
                h = self.HBOUND_lower
        if not math.isnan(f) and f > self.FBOUND:
            self.log.warning(f"Focus position {f} exceeds max bound {self.FBOUND}. Changing to {self.FBOUND}")
            f = self.FBOUND

        return [h, v, f]

    def open(self):
        self.hor = ConexAxis(self.config['port_hor'], self.config.get('baudrate', 921600), service=self)
        self.ver = ConexAxis(self.config['port_ver'], self.config.get('baudrate', 921600), service=self)
        self.foc = ConexAxis(self.config['port_foc'], self.config.get('baudrate', 921600), service=self)

        for axis in [self.hor, self.ver, self.foc]:
            axis.open()
            axis.home()

        self.command_stream = self.make_data_stream('move_command', 'float64', [3], 20)
        self.position_stream = self.make_data_stream('current_position', 'float64', [3], 20)

        self.log.info("Conex FPM axes connected and homed.")

    def stop_all_axes(self):
        self.log.info("Stopping movement on all axes immediately.")
        for axis in [self.hor, self.ver, self.foc]:
            try:
                if axis and axis.ser and axis.ser.is_open:
                    axis.stop_movement()
                    self.log.info(f"Sent stop command on {axis.port}")
            except Exception as e:
                self.log.warning(f"Failed to stop axis {axis.port}: {e}")

    def main(self):
        while not self.should_shut_down:
            try:
                frame = self.command_stream.get_next_frame(5)
                h, v, f = frame.data
                self.hor.move_to_position(h)
                self.ver.move_to_position(v)
                self.foc.move_to_position(f)

                pos = np.array([
                    self.hor.get_current_position(),
                    self.ver.get_current_position(),
                    self.foc.get_current_position()
                ])
                self.position_stream.submit_data(pos)
            except Exception:
                continue
            self.sleep(0.1)
        self.stop_all_axes()

    def get_all_position(self):
        return [
            self.hor.get_current_position(),
            self.ver.get_current_position(),
            self.foc.get_current_position()
        ]

    def move_all_position(self, pos):
        pos = self.check_positions(pos)
        h, v, f = pos
        threads = []
        if not math.isnan(h):
            threads.append(threading.Thread(target=self.hor.move_to_position, args=(h,)))
        if not math.isnan(v):
            threads.append(threading.Thread(target=self.ver.move_to_position, args=(v,)))
        if not math.isnan(f):
            threads.append(threading.Thread(target=self.foc.move_to_position, args=(f,)))
            
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def close(self):
        self.log.info("Closing service: stopping movement on all axes immediately.")
        self.stop_all_axes()
        for axis in [self.hor, self.ver, self.foc]:
            if axis and axis.ser:
                try:
                    axis.ser.close()
                except Exception as e:
                    self.log.error(f"Failed to close serial port: {e}")
        self.log.info("Closed Conex serial connections.")


if __name__ == '__main__':
    service = ConexFPM()
    service.run()



