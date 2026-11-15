import importlib.util
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from catkit2.testbed.proxies import newport_xps


class FakeReadback:
    def __init__(self, clock, positions):
        self.clock = clock
        self.positions = list(positions)
        self.waits = []
        self.on_read = lambda: None

    def get_next_frame(self, wait_time_ms):
        assert isinstance(wait_time_ms, int) and wait_time_ms > 0
        self.waits.append(wait_time_ms)
        assert len(self.waits) <= 100, 'Move did not terminate'
        self.clock.milliseconds += wait_time_ms
        self.on_read()
        position = self.positions[0]
        if len(self.positions) > 1:
            self.positions.pop(0)
        if position is None:
            raise RuntimeError('No frame available')
        return SimpleNamespace(data=np.array([position]))

    def get(self):
        return np.array([self.positions[0]])


class FakeProxy:
    # Exercise the real proxy methods without constructing a native connection.
    move_absolute = newport_xps.NewportXpsQ8Proxy.move_absolute
    move_relative = newport_xps.NewportXpsQ8Proxy.move_relative
    resolve_position = newport_xps.NewportXpsQ8Proxy.resolve_position
    _get_motor_atol = newport_xps.NewportXpsQ8Proxy._get_motor_atol
    positions = newport_xps.NewportXpsQ8Proxy.positions

    def __init__(self, clock, positions, atol=0.001):
        self.config = {
            'motors': {'Axis': {'nominal': 'target', 'target': 10.00105}},
            'atol': {'default': 1e-6, 'Axis': atol},
        }
        self.axis_current_position = FakeReadback(clock, positions)
        self.axis_command = Mock()
        self.axis_command.submit_data.side_effect = self.set_command

    def set_command(self, data):
        assert data.dtype == np.float64 and data.shape == (1,)
        self.axis_command.get.return_value = data.copy()


@pytest.fixture
def clock(monkeypatch):
    clock = SimpleNamespace(milliseconds=0)
    monkeypatch.setattr(newport_xps, 'time', SimpleNamespace(monotonic=lambda: clock.milliseconds / 1000), raising=False)
    return clock


@pytest.fixture
def service_class(monkeypatch, tmp_path):
    # Import the real service with a fake SDK; never construct or open it.
    monkeypatch.setenv('CATKIT_NEWPORT_LIB_PATH', str(tmp_path))
    monkeypatch.setitem(sys.modules, 'XPS_Q8_drivers', ModuleType('XPS_Q8_drivers'))
    monkeypatch.setattr(sys, 'path', sys.path.copy())
    path = Path(__file__).parents[1] / 'catkit2/services/newport_xps_q8/newport_xps_q8.py'
    spec = importlib.util.spec_from_file_location('xps_service_under_test', str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.NewportXpsQ8


@pytest.mark.parametrize('current,target,atol,accepted', [
    (10.0, 10.00105, 0.001, True),  # Issue #477: service skips, old proxy waits.
    (-10.0, -10.00105, 0.001, True),
    (np.nextafter(0.001, 0), 0, 0.001, True),
    (0.001, 0, 0.001, True),  # Exact absolute boundary is inclusive.
    (np.nextafter(0.001, np.inf), 0, 0.001, False),
    # Choose an exactly representable combined tolerance of 0.125.
    (np.nextafter(1.125, 1), 1, 0.125 - 1e-5, True),
    (1.125, 1, 0.125 - 1e-5, True),
    (np.nextafter(1.125, np.inf), 1, 0.125 - 1e-5, False),
    (1e-5, 0, 0, False),
    (0, 0, 0, True),
])
def test_service_and_proxy_acceptance(clock, service_class, current, target, atol, accepted):
    proxy = FakeProxy(clock, [current], atol)
    service = SimpleNamespace(
        socket_set={'Axis': (1, threading.Lock())},
        motor_atols={'Axis': atol},
        get_current_position=Mock(return_value=current),
        device=SimpleNamespace(GroupMoveAbsolute=Mock(return_value=(0, ''))),
        _raise_on_error=Mock(),
    )
    service_class.set_current_position(service, 'Axis', target)
    assert service.device.GroupMoveAbsolute.call_count == (0 if accepted else 1)

    if accepted:
        proxy.move_absolute('Axis', target, timeout=0.003)
        assert len(proxy.axis_current_position.waits) == 1
    else:
        with pytest.raises(TimeoutError):
            proxy.move_absolute('Axis', target, timeout=0.003)


@pytest.mark.parametrize('timeout', [None, 0.01])
def test_successful_move(clock, timeout):
    proxy = FakeProxy(clock, [None, 0, 0.5, 1])
    proxy.move_absolute('Axis', 1, timeout=timeout)
    assert len(proxy.axis_current_position.waits) == 4
    np.testing.assert_array_equal(proxy.axis_command.get(), [1])


@pytest.mark.parametrize('positions,last_readback', [
    ([0.25], '0.25'),  # Healthy telemetry but stalled motion.
    ([None], 'unavailable'),
    ([0.25, None], '0.25'),  # Retain the last successful readback.
])
def test_overall_timeout(clock, positions, last_readback):
    proxy = FakeProxy(clock, positions)
    with pytest.raises(TimeoutError) as exc:
        proxy.move_absolute('Axis', 1, timeout=0.003)
    assert clock.milliseconds == 3
    assert proxy.axis_current_position.waits == [1, 1, 1]
    assert 'Axis' in str(exc.value) and '1 mm' in str(exc.value)
    assert last_readback in str(exc.value)
    # Timing out only stops waiting; it does not replace or cancel the command.
    proxy.axis_command.submit_data.assert_called_once()
    np.testing.assert_array_equal(proxy.axis_command.get(), [1])


@pytest.mark.parametrize('timeout', [0.0005, 0.001])
def test_deadline_expires_even_if_target_frame_arrives_late(clock, timeout):
    proxy = FakeProxy(clock, [1])
    with pytest.raises(TimeoutError):
        proxy.move_absolute('Axis', 1, timeout=timeout)
    assert clock.milliseconds == 1


@pytest.mark.parametrize('timeout', [0, -1])
def test_nonblocking_move(clock, timeout):
    proxy = FakeProxy(clock, [None])
    proxy.move_absolute('Axis', 1, timeout=timeout)
    proxy.axis_command.submit_data.assert_called_once()
    proxy.axis_command.get.assert_not_called()
    assert proxy.axis_current_position.waits == []


@pytest.mark.parametrize('readback', [None, 0.25, 1])
def test_interrupted_move(clock, readback):
    proxy = FakeProxy(clock, [readback])
    proxy.axis_current_position.on_read = lambda: proxy.set_command(np.array([2.0]))
    with pytest.raises(RuntimeError, match='interrupted') as exc:
        proxy.move_absolute('Axis', 1)
    assert 'Axis' in str(exc.value) and '1 mm' in str(exc.value)
    assert 'current command: 2.0 mm' in str(exc.value)


def test_nearby_replacement_retains_existing_interruption_tolerance(clock):
    proxy = FakeProxy(clock, [None, 10.0])
    proxy.axis_current_position.on_read = lambda: proxy.set_command(np.array([10.0]))
    proxy.move_absolute('Axis', 10.00105, timeout=0.01)
    assert len(proxy.axis_current_position.waits) == 2


def test_named_position_and_relative_move(clock):
    proxy = FakeProxy(clock, [10.0])
    proxy.move_absolute('AXIS', 'nominal', timeout=0.01)
    np.testing.assert_array_equal(proxy.axis_command.get(), [10.00105])
    proxy.move_relative('Axis', 0.00105, timeout=0.01)
    np.testing.assert_array_equal(proxy.axis_command.get(), [10.00105])


def test_default_tolerance_matches_service_lookup(clock):
    proxy = FakeProxy(clock, [0.001])
    # A differently cased tolerance key does not override the service's default.
    proxy.config['atol'] = {'default': 0.001, 'axis': 0}
    proxy.move_absolute('axis', 0, timeout=0.01)
