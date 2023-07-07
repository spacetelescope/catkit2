import pytest
import numpy as np

def test_flatten_single_channel(testbed):
    # Test with single channel
    dm_proxy = testbed.dummy_dm_service

    expected_zero_command = np.zeros(dm_proxy.config['dm_shape'])
    initial_command = np.ones(dm_proxy.config['dm_shape'])
    dm_proxy.correction_howfs.submit_data(initial_command)

    previous_dm_command = dm_proxy.flatten_channels('correction_howfs')
    assert np.allclose(previous_dm_command, initial_command)

    current_dm_command = dm_proxy.correction_howfs.get_latest_frame().data
    assert np.allclose(current_dm_command, expected_zero_command)

def test_flatten_multiple_channels(testbed):
    # Flatten multiple channels
    dm_proxy = testbed.dummy_dm_service

    initial_command = np.ones(dm_proxy.config['dm_shape'])
    dm_proxy.correction_lowfs.submit_data(initial_command)
    dm_proxy.atmosphere.submit_data(initial_command)
    dm_proxy.aberration.submit_data(initial_command)
    num_channels_summed = 3

    expected_summed_command = num_channels_summed*initial_command
    expected_zero_command = np.zeros(dm_proxy.config['dm_shape'])

    move_command = dm_proxy.flatten_channels(['correction_lowfs', 'atmosphere', 'aberration'])
    assert np.allclose(move_command, expected_summed_command)

    current_lowfs_command = dm_proxy.correction_lowfs.get_latest_frame().data
    assert np.allclose(current_lowfs_command, expected_zero_command)

    current_atmosphere_command = dm_proxy.atmosphere.get_latest_frame().data
    assert np.allclose(current_atmosphere_command, expected_zero_command)

    current_aberration_command = dm_proxy.aberration.get_latest_frame().data
    assert np.allclose(current_aberration_command, expected_zero_command)

