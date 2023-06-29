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

    data = np.abs(np.random.randn(*shape)).astype(dtype)
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

        data = np.abs(np.random.randn(*shape)).astype(send_dtype)

        with pytest.raises(RuntimeError):
            created_stream.submit_data(data)

    # We should get an error if we submit data with the wrong shape.
    wrong_shape = np.copy(shape)
    wrong_shape[-1] += 1

    data = np.abs(np.random.randn(*wrong_shape)).astype(dtype)

    with pytest.raises(RuntimeError):
        created_stream.submit_data(data)

    # We should get an error if we submit a non-contiguous array.
    if len(shape) >= 2:
        data = np.abs(np.random.randn(*wrong_shape)).astype(dtype)
        data = data[..., :-1]

        with pytest.raises(RuntimeError):
            created_stream.submit_data(data)

def test_datastream_lifetime():
    dtype = 'int8'
    shape = [10, 10]
    stream_name = 'stream'
    service_id = 'service'

    stream_created = DataStream.create(stream_name, service_id, dtype, shape, 20)

    stream_id = stream_created.stream_id

    # Creating a stream with the same info should raise an error.
    with pytest.raises(RuntimeError):
        DataStream.create(stream_name, service_id, dtype, shape, 20)

    # We should be able to open this stream.
    stream_opened_1 = DataStream.open(stream_id)

    # Delete the created
    del stream_created

    # Because the opened stream is still open, opening the datastream again should be fine.
    stream_opened_2 = DataStream.open(stream_id)

    # Deleting both opened streams. This should give the shared memory back to the OS.
    del stream_opened_1
    del stream_opened_2

    # Opening a deleted stream should raise an error.
    with pytest.raises(RuntimeError):
        DataStream.open(stream_name, service_id, dtype, shape, 20)

    # Reopening a stream with the same info right after deleting the original one should be fine.
    stream_created = DataStream.create(stream_name, service_id, dtype, shape, 20)

    # Deleting new created stream
    del stream_created
