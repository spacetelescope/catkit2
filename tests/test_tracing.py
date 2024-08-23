from catkit2 import TraceWriter, trace_interval, trace_instant, trace_counter, ZmqDistributor
from catkit2.catkit_bindings import trace_connect

import time
import zmq
import json


PROCESS_NAME = 'our_process_name'
FNAME = 'trace.json'
INSTANT_NAME = 'blank'
COUNTER_NAME = 'counter'
SERIES_NAME = 'series'
INTERVAL_NAME_1 = 'a'
INTERVAL_NAME_2 = 'ab'

def test_trace_writer(unused_port):
    input_port = unused_port()
    output_port = unused_port()

    writer = TraceWriter('127.0.0.1', output_port)
    trace_connect(PROCESS_NAME, '127.0.0.1', input_port)

    context = zmq.Context()

    tracing_distributor = ZmqDistributor(context, input_port, output_port)
    tracing_distributor.start()

    try:
        with writer.open(FNAME):
            time.sleep(0.1)

            with trace_interval(INTERVAL_NAME_1):
                with trace_interval(INTERVAL_NAME_2):
                    time.sleep(0.01)

            for i in range(10):
                trace_counter(COUNTER_NAME, SERIES_NAME, i)

                if i % 2 == 0:
                    trace_instant(INSTANT_NAME)

            time.sleep(0.1)

    finally:
        tracing_distributor.stop()

    # Check the written JSON file.
    with open(FNAME) as f:
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
