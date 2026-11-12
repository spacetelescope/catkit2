from types import SimpleNamespace

import pytest

from catkit2.testbed.proxies.thorlabs_s4fc import ThorlabsS4fcProxy


@pytest.mark.parametrize('warmup', [False, True])
def test_turn_on_waits_for_enable_before_optional_warmup(monkeypatch, warmup):
    events = []
    readbacks = iter([False, True])

    class OfflineS4fc(ThorlabsS4fcProxy):
        property_names = command_names = data_stream_names = ()
        emission = SimpleNamespace(submit_data=lambda value: events.append(('request', int(value[0]))))

        def get_enable(self):
            enabled = next(readbacks)
            events.append(('enabled', enabled))
            return enabled

    # Use the real proxy method without opening a native testbed connection.
    proxy = OfflineS4fc.__new__(OfflineS4fc)
    monkeypatch.setattr('catkit2.testbed.proxies.thorlabs_s4fc.time.sleep', lambda delay: events.append(('sleep', delay)))
    proxy.turn_on(wait_for_warmup=warmup)
    expected = [('request', 1), ('enabled', False), ('sleep', 0.1), ('enabled', True)]
    assert events == expected + ([('sleep', 30)] if warmup else [])
