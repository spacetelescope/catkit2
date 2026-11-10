import time

import numpy as np
import pytest

from catkit2.testbed.proxies.nkt_superk_evo import NktSuperkEvoProxy
from catkit2.testbed.proxies.thorlabs_mcls1 import ThorlabsMcls1
from catkit2.testbed.proxies.thorlabs_s4fc import ThorlabsS4fcProxy


class FakeSource:
    def __init__(self, events):
        self.emission = self
        self.events = events

    def submit_data(self, data):
        self.events.append(('submit', data))


@pytest.mark.parametrize('proxy, startup_wait', [
    (ThorlabsS4fcProxy, 6.5),
    (ThorlabsMcls1, None),
    (NktSuperkEvoProxy, None),
])
def test_turn_on_and_off(monkeypatch, proxy, startup_wait):
    events = []
    monkeypatch.setattr(time, 'sleep', lambda seconds: events.append(('sleep', seconds)))
    source = FakeSource(events)

    proxy.turn_on(source)
    proxy.turn_off(source)

    expected = [('submit', 1)]
    if startup_wait is not None:
        expected.append(('sleep', startup_wait))
    expected.append(('submit', 0))

    assert [(kind, value if kind == 'sleep' else value[0]) for kind, value in events] == expected
    assert all(value.dtype == np.uint8 and value.shape == (1,) for kind, value in events if kind == 'submit')
