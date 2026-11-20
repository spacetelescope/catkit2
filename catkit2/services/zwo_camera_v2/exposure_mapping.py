"""Convert between reachable calibrated durations and integer ASI exposure settings."""
from collections.abc import Mapping
from bisect import bisect_right
from math import floor, isfinite
from numbers import Integral


def integer(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f'{name} must be an integer.')
    return int(value)


class ExposureMapping:
    """A bounded monotone command grid with linear or tabulated stair durations."""

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
        if not all(map(isfinite, (self.first, self.step))) or self.step <= 0:
            raise ValueError('Exposure grid parameters must be finite with positive step.')
        self.knots = None
        if 'duration_knots' in config:
            if 'k0' in config or 'duration_scale_us' in config:
                raise ValueError('duration_knots cannot be combined with k0 or duration_scale_us.')
            self._load_knots(config)
        else:
            if 'supported_stair_ranges' in config:
                raise ValueError('supported_stair_ranges requires duration_knots.')
            self.zero = float(config['k0'])
            self.scale = float(config['duration_scale_us'])
            if not all(map(isfinite, (self.zero, self.scale))) or self.scale <= 0:
                raise ValueError('Duration parameters must be finite with positive scale.')

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
        self.command_ranges = [(self.low, self.high)]
        if self.knots is not None:
            self.command_ranges = []
            for start, stop in self.supported_ranges:
                first = self._first_index_at_least(start)
                last = self._first_index_at_least(stop + 1) - 1
                if first <= last:
                    self.command_ranges.append((first, last))
            if not self.command_ranges:
                raise ValueError('No supported calibrated stairs overlap the ASI exposure control limits.')
        self.minimum = self.duration(self.command_ranges[0][0])
        self.maximum = self.duration(self.command_ranges[-1][1])
        if not 0 < self.minimum <= self.maximum or not isfinite(self.maximum):
            raise ValueError('Reachable calibrated durations must be finite and positive.')

    def _load_knots(self, config):
        knots = config['duration_knots']
        if not isinstance(knots, (list, tuple)) or len(knots) < 2:
            raise ValueError('duration_knots requires at least two [integer stair, duration_us] pairs.')
        self.knots, self.durations = [], []
        for pair in knots:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError('Each duration knot must be an [integer stair, duration_us] pair.')
            stair = integer(pair[0], 'Duration knot stair')
            try:
                duration = float(pair[1])
            except (TypeError, ValueError) as error:
                raise ValueError('Duration knots must have finite positive durations.') from error
            if not isfinite(duration) or duration <= 0:
                raise ValueError('Duration knots must have finite positive durations.')
            if self.knots and (stair <= self.knots[-1] or duration <= self.durations[-1]):
                raise ValueError('Duration knot stairs and durations must be strictly increasing.')
            self.knots.append(stair)
            self.durations.append(duration)
        ranges = config.get('supported_stair_ranges')
        if not isinstance(ranges, (list, tuple)) or not ranges:
            raise ValueError('supported_stair_ranges requires one or more [first stair, last stair] pairs.')
        self.supported_ranges = []
        for pair in ranges:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError('Each supported stair range requires two integer bounds.')
            start, stop = (integer(value, 'Supported stair bound') for value in pair)
            if not self.knots[0] <= start <= stop <= self.knots[-1]:
                raise ValueError('Supported stair ranges must lie within the duration knot domain.')
            if self.supported_ranges and start <= self.supported_ranges[-1][1]:
                raise ValueError('Supported stair ranges must be ordered and disjoint.')
            if self.supported_ranges and start == self.supported_ranges[-1][1] + 1:
                self.supported_ranges[-1] = (self.supported_ranges[-1][0], stop)
            else:
                self.supported_ranges.append((start, stop))

    def _first_index_at_least(self, index):
        low, high = self.low, self.high + 1
        while low < high:
            middle = (low + high) // 2
            if self._index(middle) < index:
                low = middle + 1
            else:
                high = middle
        return low

    def _index(self, command):
        nominal = floor((command - self.first) / self.step)
        return max(self.floor_index, nominal + self.corrections.get(command, 0))

    def duration(self, readback):
        command = integer(readback, 'SDK exposure readback')
        if not self.low <= command <= self.high:
            raise ValueError(f'SDK exposure readback {command} us is outside [{self.low}, {self.high}] us.')
        index = self._index(command)
        if self.knots is None:
            return self.scale * (index - self.zero)
        if not any(start <= index <= stop for start, stop in self.supported_ranges):
            raise ValueError(f'SDK exposure readback {command} us is on unsupported calibrated stair {index}.')
        position = min(bisect_right(self.knots, index), len(self.knots) - 1)
        if index == self.knots[position]:
            return self.durations[position]
        left, right = self.knots[position - 1], self.knots[position]
        shorter, longer = self.durations[position - 1], self.durations[position]
        return shorter + (longer - shorter) * ((index - left) / (right - left))

    def _first_at_least(self, duration, low, high):
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
            return self.command_ranges[0][0]
        if not self.minimum <= requested <= self.maximum:
            raise ValueError(f'Request {requested} us is outside [{self.minimum}, {self.maximum}] calibrated us.')
        for low, high in self.command_ranges:
            if self.duration(low) <= requested <= self.duration(high):
                break
        else:
            raise ValueError(f'Request {requested} us lies in an unsupported calibrated duration gap.')
        upper = self._first_at_least(requested, low, high)
        if upper > low:
            shorter, longer = self.duration(upper - 1), self.duration(upper)
            if requested <= shorter + (longer - shorter) / 2:
                return self._first_at_least(shorter, low, high)
        return upper
