"""Exercise the ZWO v2 property callbacks with a synthetic SDK, without a camera or service process."""
import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from catkit2.catkit_bindings import LocalMemory, LocalMessageBroker
from catkit2.proto import core_pb2
from catkit2.services.zwo_camera_v2.exposure_mapping import ExposureMapping


CALIBRATION = dict(command_range_us=[0, 22], first_boundary_us=8, step_commands_us=4,
                   floor_index=-1, index_corrections={'12': -1}, k0=-2, duration_scale_us=3,
                   sdk_readback_same_stair_verified=True)
KNOT_CALIBRATION = {key: value for key, value in CALIBRATION.items() if key not in ('k0', 'duration_scale_us')}
KNOT_CALIBRATION.update(duration_knots=[[-1, 2], [1, 8], [3, 20]], supported_stair_ranges=[[-1, 3]])


@pytest.fixture(scope='module')
def broker():
    header = LocalMemory.create(512 * 1024**2)
    block = LocalMemory.create(4 * 1024**2)
    return LocalMessageBroker.create(header, [block])


@pytest.fixture
def open_camera(monkeypatch, tmp_path, broker):
    sdk = ModuleType('zwoasi')
    for name in ('EXPOSURE', 'BANDWIDTHOVERLOAD', 'GAIN', 'IMG_RAW16'):
        setattr(sdk, 'ASI_' + name, name)
    sdk.init = Mock()
    sdk.get_num_cameras = lambda: 1
    sdk._get_camera_property = lambda i: {'Name': 'synthetic'}
    device = Mock()
    sdk.Camera = lambda i: device
    device.get_controls.return_value = {'Exposure': dict(ControlType='EXPOSURE', MinValue=2, MaxValue=100),
                                        'BandWidth': dict(ControlType='BANDWIDTHOVERLOAD', MinValue=1, MaxValue=10)}
    controls = {'EXPOSURE': 10, 'GAIN': 0, 'BANDWIDTHOVERLOAD': 5}
    device.apply_exposure = lambda command: max(2, min(command, 100))

    def set_control(name, value):
        controls[name] = device.apply_exposure(value) if name == 'EXPOSURE' else value

    device.set_control_value.side_effect = set_control
    device.get_control_value.side_effect = lambda name: (controls[name], False)
    device.get_camera_property.return_value = dict(MaxWidth=4, MaxHeight=4)
    device.get_roi_format.side_effect = lambda: [4, 4, 1, 0]
    device.get_roi_start_position.return_value = (0, 0)
    monkeypatch.setenv('ZWO_ASI_LIB', str(tmp_path))
    monkeypatch.setitem(sys.modules, 'zwoasi', sdk)
    name = 'catkit2.services.zwo_camera_v2.zwo_camera_v2'
    monkeypatch.delitem(sys.modules, name, raising=False)
    driver = importlib.import_module(name)
    monkeypatch.setattr(driver.CameraService, 'monitor_temperature', lambda self: None)

    class OfflineCamera(driver.ZwoCamera):
        id = 'camera'
        config = {'device_name': 'synthetic'}
        testbed = SimpleNamespace(message_broker=broker)
        callbacks = {}
        commands = {}

        def make_command(self, name, callback):
            self.commands[name] = callback

        make_data_stream = Mock(side_effect=lambda *args: Mock(**{'get.return_value': [0]}))

        def make_property(self, name, getter, setter=None):
            self.callbacks[name] = (getter, setter)

    def open_with(**settings):
        service = OfflineCamera.__new__(OfflineCamera)
        service.config.update(settings)
        service.open()
        return service, device

    yield open_with
    sys.modules.pop(name, None)


def published_exposure(service):
    topic = 'camera/exposure_time/get'
    packet = service.testbed.message_broker.get_current_message(topic)
    msg = core_pb2.Value.FromString(bytes(packet.payload))
    field = msg.WhichOneof('kind')
    return None if field == 'none_value' else getattr(msg, field)


def test_calibrated_service(open_camera):
    cam, device = open_camera(exposure_calibration=CALIBRATION, exposure_time=0)
    read, write = cam.callbacks['exposure_time']
    raw = cam.commands['raw_exposure_time']
    assert (raw(), read()) == (2, 3.)
    assert cam.callbacks['minimum_calibrated_exposure_time'][0]() == 3.
    assert cam.callbacks['maximum_calibrated_exposure_time'][0]() == 15.
    # At the corrected edge, command 12 still belongs to the shorter stair.
    device.apply_exposure = lambda command: command + 1
    write(7.5)
    assert (raw(), read()) == (9, 6.)
    write(7.51)
    assert raw() == 14 and read() == 9.
    raw(command_us=11)
    assert raw() == 12 and published_exposure(cam) == read() == 6.
    with pytest.raises(ValueError, match='integer'):
        raw(command_us=12.5)
    raw(command_us=40)
    assert raw() == 41 and published_exposure(cam) is None
    with pytest.raises(ValueError, match='outside'):
        read()
    write(0)
    assert read() == 3.
    for bad_duration in (-1, 1, 15.01, float('nan')):
        with pytest.raises(ValueError, match='outside'):
            write(bad_duration)
    assert raw() == 3
    # A changed ROI/SDK clamp changing stair must not publish the selected duration.
    device.apply_exposure = lambda command: 16
    with pytest.raises(RuntimeError, match='different calibrated stair'):
        write(6)
    assert (raw(), published_exposure(cam)) == (16, 12.)
    device.apply_exposure = lambda command: 50
    with pytest.raises(ValueError, match='outside'):
        write(6)
    assert raw() == 50 and published_exposure(cam) is None


@pytest.mark.parametrize('calibration', [None, False])
def test_legacy_and_raw_properties_share_pause_policy(open_camera, calibration):
    cam, _ = open_camera(exposure_calibration=calibration, exposure_time_step_size=4,
                         exposure_time_base_step=3, exposure_time_offset_correction=2,
                         exposure_time_requires_stopped_acquisition=True)
    assert 'minimum_calibrated_exposure_time' not in cam.callbacks
    read, write = cam.callbacks['exposure_time']
    raw = cam.commands['raw_exposure_time']
    cam.is_acquiring.get.side_effect = [[1], [0], [1], [0]]
    cam._start_acquisition = Mock()
    cam._end_acquisition = Mock()
    write(10)
    assert (raw(), read()) == (11, 9)
    raw(command_us=6)
    assert (raw(), read(), published_exposure(cam)) == (6, 4, 4)
    assert cam._start_acquisition.call_count == cam._end_acquisition.call_count == 2


@pytest.mark.parametrize('overrides', [dict(sdk_readback_same_stair_verified=False), dict(index_corrections={10: -1}),
                                      dict(k0=-1), dict(command_range_us=[200, 210]), dict(step_commands_us=0)])
def test_invalid_calibration_rejected_at_startup(open_camera, overrides):
    with pytest.raises(ValueError):
        open_camera(exposure_calibration=dict(CALIBRATION, **overrides), exposure_time=0)


def test_sdk_readback_trial_checks_extrapolated_commands(open_camera):
    config = dict(CALIBRATION, sdk_readback_verified_command_range_us=[2, 14])
    del config['sdk_readback_same_stair_verified']
    cam, device = open_camera(exposure_calibration=config, exposure_time=0)
    read, write = cam.callbacks['exposure_time']
    raw = cam.commands['raw_exposure_time']
    assert raw() == 2  # SDK minimum on the floor
    write(15)
    assert (raw(), read()) == (20, 15.)
    device.apply_exposure = lambda command: 19
    with pytest.raises(RuntimeError, match='different calibrated stair'):
        write(15)
    assert (raw(), published_exposure(cam)) == (19, 12.)
    with pytest.raises(ValueError, match='outside'):
        write(16)


@pytest.mark.parametrize('verified', [[14, 2], [2, 23], [0, 1], [2.5, 14], [], None])
def test_sdk_readback_trial_requires_a_valid_measured_interval(verified):
    config = dict(CALIBRATION, sdk_readback_verified_command_range_us=verified)
    del config['sdk_readback_same_stair_verified']
    with pytest.raises(ValueError):
        ExposureMapping(config, 2, 100)


def test_sdk_readback_rejects_conflicting_assertions():
    with pytest.raises(ValueError, match='Conflicting'):
        ExposureMapping(dict(CALIBRATION, sdk_readback_verified_command_range_us=[2, 14]), 2, 100)


def test_nearest_matches_all_reachable_stairs():
    mapping = ExposureMapping(CALIBRATION, 2, 100)
    commands = range(mapping.low, mapping.high + 1)
    for tick in range(12, 61):
        target = tick / 4
        expected = min(commands, key=lambda c: (abs(mapping.duration(c) - target), c))
        assert mapping.command(target) == expected


@pytest.mark.parametrize('sdk_min,sdk_max', [(2, 100), (10, 19), (13, 14)])
def test_nonlinear_nearest_matches_independent_stair_oracle(sdk_min, sdk_max):
    mapping = ExposureMapping(KNOT_CALIBRATION, sdk_min, sdk_max)
    # Explicit synthetic command groups and interpolated durations, independent of the implementation.
    groups = [(range(0, 8), 2), (range(8, 13), 5), (range(13, 16), 8),
              (range(16, 20), 14), (range(20, 23), 20)]
    reachable = [(command, duration) for commands, duration in groups for command in commands
                 if sdk_min <= command <= sdk_max]
    assert mapping.command(0) == reachable[0][0]
    assert (mapping.minimum, mapping.maximum) == (reachable[0][1], reachable[-1][1])
    for command, duration in reachable:
        assert mapping.duration(command) == duration
    for tick in range(int(mapping.minimum * 4), int(mapping.maximum * 4) + 1):
        target = tick / 4
        expected = min(reachable, key=lambda item: (abs(item[1] - target), item[0]))[0]
        assert mapping.command(target) == expected


def test_supported_ranges_reject_gaps_and_keep_exact_endpoints():
    config = dict(KNOT_CALIBRATION, supported_stair_ranges=[[-1, 0], [2, 3]])
    mapping = ExposureMapping(config, 2, 100)
    assert [mapping.command(target) for target in (0, 2, 5, 14, 20)] == [2, 2, 8, 16, 20]
    for target in (5.01, 8, 13.99):
        with pytest.raises(ValueError, match='unsupported.*gap'):
            mapping.command(target)
    for command in (13, 14, 15):
        with pytest.raises(ValueError, match='unsupported.*stair'):
            mapping.duration(command)
    # The first supported stair can begin after the SDK minimum.
    mapping = ExposureMapping(dict(KNOT_CALIBRATION, supported_stair_ranges=[[0, 2]]), 2, 100)
    assert (mapping.command(0), mapping.minimum, mapping.maximum) == (8, 5, 14)
    with pytest.raises(ValueError, match='outside'):
        mapping.command(20)
    with pytest.raises(ValueError, match='No supported'):
        ExposureMapping(dict(KNOT_CALIBRATION, supported_stair_ranges=[[3, 3]]), 2, 19)


@pytest.mark.parametrize('overrides', [
    dict(duration_knots=[]), dict(duration_knots=[[0, 1]]), dict(duration_knots=[[0, 1], [0, 2]]),
    dict(duration_knots=[[0, 1], [-1, 2]]), dict(duration_knots=[[0, 1], [2, 1]]),
    dict(duration_knots=[[0, 1], [2, 0]]), dict(duration_knots=[[0, 1], [2, float('nan')]]),
    dict(duration_knots=[[0, 1], [2, float('inf')]]), dict(duration_knots=[[0, None], [2, 3]]),
    dict(duration_knots=[[0.5, 1], [2, 3]]), dict(duration_knots=[[True, 1], [2, 3]]),
    dict(duration_knots=[[0, 1, 2], [2, 3]]), dict(k0=-2), dict(duration_scale_us=3),
    dict(supported_stair_ranges=None), dict(supported_stair_ranges=[]), dict(supported_stair_ranges=[[0]]),
    dict(supported_stair_ranges=[[-2, 0]]), dict(supported_stair_ranges=[[0, 4]]),
    dict(supported_stair_ranges=[[2, 0]]), dict(supported_stair_ranges=[[-1, 1], [1, 3]]),
    dict(supported_stair_ranges=[[2, 3], [-1, 0]]), dict(supported_stair_ranges=[[0.5, 2]]),
])
def test_malformed_knot_calibration_is_rejected(overrides):
    with pytest.raises(ValueError):
        ExposureMapping(dict(KNOT_CALIBRATION, **overrides), 2, 100)


def test_supported_ranges_require_knots():
    with pytest.raises(ValueError, match='requires duration_knots'):
        ExposureMapping(dict(CALIBRATION, supported_stair_ranges=[[-1, 3]]), 2, 100)


def test_adjacent_supported_ranges_do_not_create_a_duration_gap():
    mapping = ExposureMapping(dict(KNOT_CALIBRATION, supported_stair_ranges=[[-1, 0], [1, 3]]), 2, 100)
    assert mapping.command(6.5) == 8
    assert mapping.command(6.51) == 13


def test_nonlinear_service_readback_and_unsupported_raw_publication(open_camera):
    config = dict(KNOT_CALIBRATION, supported_stair_ranges=[[-1, 0], [2, 3]])
    cam, device = open_camera(exposure_calibration=config, exposure_time=0)
    read, write = cam.callbacks['exposure_time']
    raw = cam.commands['raw_exposure_time']
    assert (raw(), read()) == (2, 2)
    assert cam.callbacks['minimum_calibrated_exposure_time'][0]() == 2
    assert cam.callbacks['maximum_calibrated_exposure_time'][0]() == 20
    device.apply_exposure = lambda command: command + 1
    write(17)
    assert (raw(), read()) == (17, 14)
    write(17.01)
    assert (raw(), read()) == (21, 20)
    assert all(isinstance(call.args[1], int) for call in device.set_control_value.call_args_list
               if call.args[0] == 'EXPOSURE')
    with pytest.raises(ValueError, match='unsupported.*gap'):
        write(8)
    assert raw() == 21
    raw(command_us=13)
    assert raw() == 14 and published_exposure(cam) is None
    with pytest.raises(ValueError, match='unsupported.*stair'):
        read()
    write(0)
    assert read() == 2
    device.apply_exposure = lambda command: 20
    with pytest.raises(RuntimeError, match='different calibrated stair'):
        write(14)
    assert (raw(), published_exposure(cam)) == (20, 20)
    device.apply_exposure = lambda command: 14
    with pytest.raises(ValueError, match='unsupported.*stair'):
        write(14)
    assert published_exposure(cam) is None


@pytest.mark.parametrize('pause', [None, False, True])
@pytest.mark.parametrize('calibration', [False, CALIBRATION])
def test_configured_exposure_pause_waits_and_preserves_running_state(open_camera, pause, calibration):
    settings = dict(exposure_calibration=calibration, exposure_time=6)
    if pause is not None:
        settings['exposure_time_requires_stopped_acquisition'] = pause
    cam, device = open_camera(**settings)
    assert cam.exposure_time_requires_stopped_acquisition is bool(pause)
    events, running = [], [1]
    cam.is_acquiring.get.side_effect = lambda: list(running)
    cam._end_acquisition = lambda: events.append('stop requested')
    def wait(seconds):
        events.append('stopped')
        running[0] = 0
    def start():
        events.append('restart requested')
        running[0] = 1
    cam.sleep, cam._start_acquisition = wait, start
    sdk_set = device.set_control_value.side_effect
    def set_control(name, value):
        events.append('set')
        sdk_set(name, value)
    device.set_control_value.side_effect = set_control
    cam.callbacks['exposure_time'][1](6)
    cam.commands['raw_exposure_time'](command_us=6)
    expected = ['stop requested', 'stopped', 'set', 'restart requested'] if pause else ['set']
    assert events == expected * 2 and running == [1]
    events.clear()
    running[0] = 0
    cam.commands['raw_exposure_time'](command_us=6)
    assert events == ['set'] and running == [0]
