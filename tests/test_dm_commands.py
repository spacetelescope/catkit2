import pytest

from catkit2.testbed.proxies import BmcDmProxy

def test_startup_service(testbed, dummy_dm_service):

    dm_proxy = BmcDmProxy(testbed, 'dummy_dm_service')
    breakpoint()
    assert True
