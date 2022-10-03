from catkit2.catkit_bindings import DataStream
import numpy as np
import pytest
import sys

dtypes = ['int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64', 'float32', 'float64', 'complex64', 'complex128']
shapes = [[10], [10, 10], [10, 10, 10], [10, 10, 10, 10]]

@pytest.mark.parametrize("shape", shapes)
@pytest.mark.parametrize("dtype", dtypes)
def test_data_stream(shape, dtype):
    # Use a unique name for each created stream.
    created_stream = DataStream.create(f'{dtype}_{len(shape)}_stream', 'service', dtype, shape, 20)

    # Created stream should have the right dtype and shape.
    assert created_stream.dtype == dtype
    assert np.allclose(created_stream.shape, shape)

    opened_stream = DataStream.open(created_stream.stream_id)

    # The opened stream should have the right dtype and shape.
    assert opened_stream.dtype == dtype
    assert np.allclose(opened_stream.shape, shape)

    data = np.random.randn(*shape).astype(dtype)
    created_stream.submit_data(data)

    frame = opened_stream.get_latest_frame()

    # This should be the first frame on this datastream.
    assert frame.id == 0

    # The data should match with what we put in.
    assert np.allclose(frame.data, data)
    assert np.allclose(opened_stream.get(), data)

    # We should get an error if we submit the wrong dtype on a data stream.
    for send_dtype in dtypes:
        if send_dtype == dtype:
            continue

        data = np.random.randn(*shape).astype(send_dtype)

        with pytest.raises(RuntimeError):
            created_stream.submit_data(data)

    # We should get an error if we submit data with the wrong shape.
    wrong_shape = np.copy(shape)
    wrong_shape[-1] += 1

    data = np.random.randn(*wrong_shape).astype(dtype)

    with pytest.raises(RuntimeError):
        created_stream.submit_data(data)

    # We should get an error if we submit a non-contiguous array.
    if len(shape) >= 2:
        data = np.random.randn(*wrong_shape).astype(dtype)
        data = data[..., :-1]

        with pytest.raises(RuntimeError):
            created_stream.submit_data(data)
