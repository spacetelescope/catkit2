from catkit2.catkit_bindings import SharedMemory
import pytest


def test_shared_memory_lifetime():
    stream_id = 'test_memory'
    memory = SharedMemory.create(stream_id, 1024)

    # Creating shared memory with the same ID should raise an error.
    with pytest.raises(RuntimeError) as excinfo:
        SharedMemory.create(stream_id, 1024)
    assert "File exists" in str(excinfo.value)

    # We should be able to access the shared memory when opening.
    memory2 = SharedMemory.open(stream_id)

    # After closing the opened memory, we should still be able to reopen it.
    del memory2

    memory2 = SharedMemory.open(stream_id)

    # Delete both the created and opened memory.
    del memory
    del memory2

    # Now we should not be able to open the shared memory anymore.
    with pytest.raises(RuntimeError) as excinfo:
        SharedMemory.open(stream_id)
    assert "No such file or directory" in str(excinfo.value)

    # However, we should be able to create a new shared memory with the same ID.
    memory = SharedMemory.create(stream_id, 1024)
    del memory
