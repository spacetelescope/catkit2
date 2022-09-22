from catkit2.catkit_bindings import DataStream
import numpy as np
import pytest
import sys

dtypes = ['int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64', 'float32', 'float64', 'complex64', 'complex128']
shapes = [[10], [10, 10], [10, 10, 10], [10, 10, 10, 10]]

@pytest.mark.xfail(sys.platform != 'win32', reason="Failing on *nix due to mixing of (u)int32 and (u)int64.")
@pytest.mark.parametrize("shape", shapes)
@pytest.mark.parametrize("dtype", dtypes)
def test_data_stream(shape, dtype):
    # Use a unique name for each created stream.
    created_stream = DataStream.create(f'{dtype}_{len(shape)}_stream', 'service', dtype, shape, 20)

    assert created_stream.dtype == dtype
    assert np.allclose(created_stream.shape, shape)

    opened_stream = DataStream.open(created_stream.stream_id)

    assert opened_stream.dtype == dtype
    assert np.allclose(opened_stream.shape, shape)

    data = np.random.randn(*shape).astype(dtype)
    created_stream.submit_data(data)

    frame = opened_stream.get_latest_frame()

    assert frame.id == 0

    assert np.allclose(frame.data, data)
    assert np.allclose(opened_stream.get(), data)
