from catkit2.catkit_bindings import DataStream
import numpy as np

def test_data_stream():
    dtypes = ['int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64', 'float32', 'float64', 'complex64', 'complex128']
    name = 'stream_name'
    service = 'service'
    dimss = [[10], [10, 10], [10, 10, 10]]

    for dims in dimss:
        for dtype in dtypes:
            created_stream = DataStream.create(name, 'service', dtype, dims, 20)

            assert created_stream.dtype == dtype
            assert np.allclose(created_stream.shape, dims)

            opened_stream = DataStream.open(created_stream.stream_id)

            assert opened_stream.dtype == dtype
            assert np.allclose(opened_stream.shape, dims)

            data = np.random.randn(*dims).astype(dtype)
            created_stream.submit_data(data)

            frame = opened_stream.get_latest_frame()

            assert frame.id == 0

            assert np.allclose(frame.data, data)
            assert np.allclose(opened_stream.get(), data)

            # Since we are creating a lot of data streams with the same name, we need to
            # ensure that the shared memory is closed before trying to reopen the same
            # part of memory. The order doesn't matter.
            del created_stream
            del opened_stream
