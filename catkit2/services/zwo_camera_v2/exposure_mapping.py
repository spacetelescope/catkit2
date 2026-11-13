"""Convert between reachable calibrated durations and integer ASI exposure settings."""
from collections.abc import Mapping
from math import floor, isfinite
from numbers import Integral


def integer(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f'{name} must be an integer.')
    return int(value)


class ExposureMapping:
    """A bounded monotone command grid with a measured floor and per-command index corrections."""

    def __init__(self, config, sdk_min, sdk_max):
        if not isinstance(config, Mapping):
            raise ValueError('exposure_calibration must be a mapping, null or false.')
        low, high = (integer(c, 'command_range_us bound') for c in config['command_range_us'])
        self.low, self.high = max(low, sdk_min), min(high, sdk_max)
        if low < 0 or self.low > self.high:
            raise ValueError('Calibrated command range must overlap the ASI exposure control limits.')
        verified = config.get('sdk_readback_verified_command_range_us')
        full = config.get('sdk_readback_same_stair_verified')
        if verified is None:
            if full is not True:
                raise ValueError('Verify that SDK readbacks map to the commanded stairs before enabling exposure calibration.')
        else:
            if not isinstance(verified, (list, tuple)) or len(verified) != 2:
                raise ValueError('sdk_readback_verified_command_range_us requires two integer bounds.')
            start, stop = (integer(c, 'Verified range bound') for c in verified)
            if not low <= start <= stop <= high or stop < self.low or start > self.high:
                raise ValueError('Verified range must be inside the model range and overlap the ASI control limits.')
            if 'sdk_readback_same_stair_verified' in config and (full is not True or (start, stop) != (low, high)):
                raise ValueError('Conflicting full-domain and explicit-range SDK readback declarations.')
        self.first = float(config['first_boundary_us'])
        self.step = float(config['step_commands_us'])
        self.floor_index = integer(config['floor_index'], 'floor_index')
        self.zero = float(config['k0'])
        self.scale = float(config['duration_scale_us'])
        if not all(map(isfinite, (self.first, self.step, self.zero, self.scale))) or self.step <= 0 or self.scale <= 0:
            raise ValueError('Exposure grid and duration parameters must be finite with positive step and scale.')

        self.corrections = {}
        for key, delta in config.get('index_corrections', {}).items():
            command = int(key) if isinstance(key, str) else integer(key, 'Correction command')
            if not low <= command <= high or command in self.corrections:
                raise ValueError(f'Duplicate or out-of-range exposure correction at {command} us.')
            self.corrections[command] = integer(delta, 'Index correction')
        # The uncorrected grid is monotone. Only adjacent pairs touching a correction can reverse.
        for command in self.corrections:
            for left in (command - 1, command):
                if low <= left < high and self._index(left) > self._index(left + 1):
                    raise ValueError(f'Exposure grid reverses at command {left + 1} us.')
        self.minimum = self.duration(self.low)
        self.maximum = self.duration(self.high)
        if not 0 < self.minimum <= self.maximum or not isfinite(self.maximum):
            raise ValueError('Reachable calibrated durations must be finite and positive.')

    def _index(self, command):
        nominal = floor((command - self.first) / self.step)
        return max(self.floor_index, nominal + self.corrections.get(command, 0))

    def duration(self, readback):
        command = integer(readback, 'SDK exposure readback')
        if not self.low <= command <= self.high:
            raise ValueError(f'SDK exposure readback {command} us is outside [{self.low}, {self.high}] us.')
        return self.scale * (self._index(command) - self.zero)

    def _first_at_least(self, duration):
        low, high = self.low, self.high
        while low < high:
            middle = (low + high) // 2
            if self.duration(middle) < duration:
                low = middle + 1
            else:
                high = middle
        return low

    def command(self, requested):
        """Select the first legal command on the nearest reachable stair. Ties select shorter."""
        if requested == 0:
            return self.low
        if not self.minimum <= requested <= self.maximum:
            raise ValueError(f'Request {requested} us is outside [{self.minimum}, {self.maximum}] calibrated us.')
        upper = self._first_at_least(requested)
        if upper > self.low:
            shorter, longer = self.duration(upper - 1), self.duration(upper)
            if requested <= shorter + (longer - shorter) / 2:
                return self._first_at_least(shorter)
        return upper
