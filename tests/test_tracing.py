from catkit2 import TraceWriter, trace_interval, trace_instant, trace_counter
from catkit2.catkit_bindings import trace_connect, trace_disconnect, LocalMessageBroker, LocalMemory

import time
import json
import os
import pytest


PROCESS_NAME = 'our_process_name'
FNAME = 'trace.json'
INSTANT_NAME = 'blank'
COUNTER_NAME = 'counter'
SERIES_NAME = 'series'
INTERVAL_NAME_1 = 'a'
INTERVAL_NAME_2 = 'ab'

@pytest.fixture(scope='module')
def broker():
    header = LocalMemory.create(1024 * 1024 * 512)
    block = LocalMemory.create(1024 * 1024 * 1024)

    broker = LocalMessageBroker.create(header, [block])
    yield broker


def test_trace_writer(tmpdir, broker):
    fname = os.path.join(tmpdir, FNAME)

    writer = TraceWriter(broker)
    trace_connect(PROCESS_NAME, broker)

    try:
        with writer.open(fname):

            with trace_interval(INTERVAL_NAME_1):
                with trace_interval(INTERVAL_NAME_2):
                    time.sleep(0.01)

            for i in range(10):
                trace_counter(COUNTER_NAME, SERIES_NAME, i)

                if i % 2 == 0:
                    trace_instant(INSTANT_NAME)

            # Wait for all messages to pass through the system and be written out.
            time.sleep(0.3)

    finally:
        trace_disconnect()

    # Check the written JSON file.
    with open(fname) as f:
        data = f.read()[:-2] + ']'

        entries = json.loads(data)

        for entry in entries:
            assert entry['ph'] in ['M', 'X', 'C', 'i']

            if entry['ph'] == 'M':
                if entry['name'] == 'process_name':
                    assert entry['args']['name'] == PROCESS_NAME
            elif entry['ph'] == 'X':
                assert entry['name'] in [INTERVAL_NAME_1, INTERVAL_NAME_2]
                assert 'dur' in entry
                assert 'ts' in entry
                assert 'pid' in entry
                assert 'tid' in entry
            elif entry['ph'] == 'C':
                assert entry['name'] == COUNTER_NAME
                assert 'ts' in entry
                assert 'pid' in entry
                assert SERIES_NAME in entry['args']
            elif entry['ph'] == 'i':
                assert entry['name'] == INSTANT_NAME
                assert 'ts' in entry
                assert 'pid' in entry
                assert 'tid' in entry
