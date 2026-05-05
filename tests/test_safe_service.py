import os
import time
import socket
import pathlib
import multiprocessing

import pytest

from catkit2 import TestbedProxy, Testbed, read_config_files
from catkit2.catkit_bindings import ServiceState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_free_port():
    """Return a TCP port number that is not currently in use."""
    with socket.socket() as sock:
        sock.bind(('', 0))
        return sock.getsockname()[1]


def _config_dir():
    """Return the path to the directory that holds services.yml / testbed.yml."""
    # conftest.py reads from a 'config' subdirectory next to the test files.
    return pathlib.Path(os.path.dirname(__file__)) / 'config'


def _base_config():
    """Load the standard project config files, just like conftest.py does."""
    config_files = _config_dir().resolve().glob('*.yml')
    return read_config_files(config_files)


def _dummy_safe_service_path():
    """Absolute path to the dummy_safe_service.py file sitting next to this test."""
    return os.path.join(os.path.dirname(__file__), 'dummy_safe_service.py')


def _run_testbed(port, config):
    """Entry point for a testbed subprocess."""
    print(f'DEBUG config check_interval={config["services"]["safety"]["check_interval"]}', flush=True)
    print(f'DEBUG config safeties={config["services"]["safety"]["safeties"]}', flush=True)
    testbed = Testbed(port, False, config)

    base = os.path.dirname(__file__)
    testbed.register_service_type(
        'dummy_safe_service',
        _dummy_safe_service_path()
    )
    testbed.register_service_type(
        'dummy_service',
        os.path.join(base, 'services/dummy_service/dummy_service.py')
    )

    testbed.run()

@pytest.fixture(scope='module')
def safe_testbed():
    """
    A real Testbed running in a separate process whose config marks
    'dummy_safe_service' as requires_safety=true and whose safety monitor
    has no actual checks (safeties: []), so it always reports safe.
    """
    config = _base_config()
    port = _get_free_port()

    # Configure a real safety check that watches dummy_service's heartbeat.
    # dummy_service has requires_safety=false so it can start freely,
    # and its heartbeat will always be recent and healthy.
    config['services']['safety']['check_interval'] = 1 
    config['services']['safety']['safeties'] = {
        'dummy_stream': {
            'service_id': 'dummy_service',
            'stream_name': 'stream',
            'safe_interval': 30,
            'minimum_value': None,
            'maximum_value': None,
        }
    }

    process = multiprocessing.Process(
        target=_run_testbed,
        args=(port, config),
        daemon=True,
    )
    process.start()

    # Give the testbed a moment to start listening before we connect.
    time.sleep(1.0)

    proxy = TestbedProxy('127.0.0.1', port)

    yield proxy

    proxy.shut_down()
    process.join(timeout=10)


# ---------------------------------------------------------------------------
# Scenario 2 - unsafe testbed
# ---------------------------------------------------------------------------
# We configure the safety monitor to watch a data stream from a service that
# does not exist. The safety monitor will catch the exception and mark the
# testbed as unsafe. Then we try to start dummy_safe_service and expect it
# to be refused (FAIL_SAFE state).

@pytest.fixture(scope='module')
def unsafe_testbed():
    """
    A real Testbed running in a separate process whose safety monitor is
    configured to watch a non-existent service. This causes the safety monitor
    to report unsafe, so any service with requires_safety=true should be
    refused.
    """
    config = _base_config()
    port = _get_free_port()

    # Override the safety config to watch a service that will never exist.
    # The safety monitor will catch the resulting error and publish is_safe=0.
    config['services']['safety']['check_interval'] = 1
    config['services']['safety']['safeties'] = {
        'nonexistent_check': {
            'service_id': 'nonexistent_service',
            'stream_name': 'nonexistent_stream',
            'safe_interval': 10,
            'minimum_value': None,
            'maximum_value': None,
        }
    }

    process = multiprocessing.Process(
        target=_run_testbed,
        args=(port, config),
        daemon=True,
    )
    process.start()

    # Give the testbed and the safety service time to start and publish at
    # least one safety reading before our test asks to start a service.
    time.sleep(2.0)

    proxy = TestbedProxy('127.0.0.1', port)

    yield proxy

    proxy.shut_down()
    process.join(timeout=10)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSafetyCheckOnStartService:

    def test_service_starts_when_testbed_is_safe(self, safe_testbed):
        # Start dummy_service
        safe_testbed.start_service('dummy_service')
        _wait_for_state(safe_testbed, 'dummy_service', ServiceState.RUNNING, timeout=10)

        # Now start the safety service.
        safe_testbed.start_service('safety')
        _wait_for_state(safe_testbed, 'safety', ServiceState.RUNNING, timeout=10)

        # Give the safety monitor time to run one check cycle and publish results.
        time.sleep(2.5)

        # Now start our safety-requiring service.
        safe_testbed.start_service('dummy_safe_service')
        _wait_for_state(safe_testbed, 'dummy_safe_service', ServiceState.RUNNING, timeout=10)

        proxy = safe_testbed.get_service('dummy_safe_service')
        assert proxy.state == ServiceState.RUNNING, (
            "dummy_safe_service should be RUNNING on a safe testbed"
        )

        safe_testbed.stop_service('dummy_safe_service')
        safe_testbed.stop_service('dummy_service')

    def test_service_blocked_when_testbed_is_unsafe(self, unsafe_testbed):
        """
        When the safety monitor reports unsafe (because the service it is
        watching does not exist), start_service should refuse to launch a
        service that declares requires_safety=true, leaving it in FAIL_SAFE.
        """
        # Start the safety service so it runs its checks and marks the
        # testbed unsafe.
        unsafe_testbed.start_service('safety')
        _wait_for_state(unsafe_testbed, 'safety', ServiceState.RUNNING, timeout=10)

        # Give the safety monitor time to run at least one check cycle and
        # publish an unsafe result before we ask to start the service.
        time.sleep(1.0)

        # Ask the testbed to start the service that requires safety.
        unsafe_testbed.start_service('dummy_safe_service')

        # Give the testbed a moment to process the request and write the state.
        time.sleep(1.0)

        proxy = unsafe_testbed.get_service('dummy_safe_service')
        assert proxy.state == ServiceState.FAIL_SAFE, (
            "dummy_safe_service should be FAIL_SAFE when the testbed is unsafe"
        )

    def test_service_without_safety_requirement_ignores_safety(self, safe_testbed):
        """
        A service with requires_safety=false should start normally regardless
        of the safety state. This is the existing behaviour and must be
        preserved by the new code.
        """
        safe_testbed.start_service('dummy_service')
        _wait_for_state(safe_testbed, 'dummy_service', ServiceState.RUNNING, timeout=10)

        proxy = safe_testbed.get_service('dummy_service')
        assert proxy.state == ServiceState.RUNNING, (
            "dummy_service (requires_safety=false) should start regardless of safety"
        )

        safe_testbed.stop_service('dummy_service')


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _wait_for_state(testbed_proxy, service_id, target_state, timeout=10, interval=0.1):
    """
    Poll the service state every `interval` seconds until it reaches
    `target_state`, or until `timeout` seconds have elapsed.
    Raises AssertionError if the timeout expires without the state being
    reached, so pytest will report the test as failed with a clear message.
    """
    elapsed = 0.0
    proxy = testbed_proxy.get_service(service_id)

    while elapsed < timeout:
        if proxy.state == target_state:
            return
        time.sleep(interval)
        elapsed += interval

    raise AssertionError(
        f"Service '{service_id}' did not reach state {target_state} "
        f"within {timeout}s. Current state: {proxy.state}"
    )