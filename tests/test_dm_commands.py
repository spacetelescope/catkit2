import pytest
import numpy as np

from catkit2.testbed.proxies import BmcDmProxy

def test_startup_dm_proxy(testbed, dummy_dm_service):
    # DM proxy should start up with no errors
    dm_proxy = BmcDmProxy(testbed, 'dummy_dm_service')
    assert True

def test_get_num_actuators(testbed, dummy_dm_service):
    # Check that num_actuators is correct and readable
    dm_proxy = BmcDmProxy(testbed, 'dummy_dm_service')
    assert dm_proxy.num_actuators == dummy_dm_service.config['num_actuators']

def test_save_and_zero_channel(testbed, dummy_dm_service):
    # Check that save_and_zero_channel zeros the channel and returns the command
    dm_proxy = BmcDmProxy(testbed, 'dummy_dm_service')

    expected_initial_command = dummy_dm_service.config['channel_init_value']*np.ones(dummy_dm_service.config['dm_shape'])
    expected_zero_command = np.zeros(dummy_dm_service.config['dm_shape'])

    previous_dm_command = dm_proxy.save_and_zero_channel('correction_howfs')
    assert np.allclose(previous_dm_command, expected_initial_command)

    current_dm_command = dm_proxy.correction_howfs.get_latest_frame().data
    assert np.allclose(current_dm_command, expected_zero_command)

def test_move_dm_command(testbed, dummy_dm_service):
    # Check that move_command zeros the channels and returns the summed command

    dm_proxy = BmcDmProxy(testbed, 'dummy_dm_service')

    initial_fill_value = dummy_dm_service.config['channel_init_value']
    num_channels_summed = 3

    expected_summed_command = initial_fill_value*num_channels_summed*np.ones(dummy_dm_service.config['dm_shape'])
    expected_zero_command = np.zeros(dummy_dm_service.config['dm_shape'])

    move_command = dm_proxy.move_dm_command(['correction_lowfs', 'atmosphere', 'aberration'])
    assert np.allclose(move_command, expected_summed_command)

    current_lowfs_command = dm_proxy.correction_lowfs.get_latest_frame().data
    assert np.allclose(current_lowfs_command, expected_zero_command)

    current_atmosphere_command = dm_proxy.atmosphere.get_latest_frame().data
    assert np.allclose(current_atmosphere_command, expected_zero_command)

    current_aberration_command = dm_proxy.aberration.get_latest_frame().data
    assert np.allclose(current_aberration_command, expected_zero_command)

