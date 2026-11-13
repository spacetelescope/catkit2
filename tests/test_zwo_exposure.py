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
        exposure_time_requires_stopped_acquisition = True
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
                         exposure_time_base_step=3, exposure_time_offset_correction=2)
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


def test_nearest_matches_all_reachable_stairs():
    mapping = ExposureMapping(CALIBRATION, 2, 100)
    commands = range(mapping.low, mapping.high + 1)
    for tick in range(12, 61):
        target = tick / 4
        expected = min(commands, key=lambda c: (abs(mapping.duration(c) - target), c))
        assert mapping.command(target) == expected
