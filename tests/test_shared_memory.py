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

def test_large_shared_memory_size():
    large_size = 1024 * 1024 * 1024  # 1GB

    stream_id = 'large_memory'

    memory = SharedMemory.create(stream_id, large_size)
    assert memory is not None

    del memory


def test_shared_memory_open_non_existent_or_invalid_name():
    stream_id = 'non_existent_memory'

    # Opening a non-existent shared memory should raise an error.
    with pytest.raises(RuntimeError) as excinfo:
        SharedMemory.open(stream_id)
    assert "Something went wrong while opening shared memory" in str(excinfo.value)

    # Opening a shared memory with an invalid name should raise an error.
    with pytest.raises(RuntimeError) as excinfo:
        SharedMemory.create("", 1024)  # Invalid name
    assert "Something went wrong while creating shared memory" in str(excinfo.value)


def test_shared_memory_wrong_type():
    # Opening a shared memory with a float for the memory size should raise an error.
    with pytest.raises(TypeError) as excinfo:
        SharedMemory.create('dflgkjdhfg', 1024.1)  # Invalid name
    assert "create(): incompatible function arguments" in str(excinfo.value)

    # Opening a shared memory with a string for the memory size should raise an error.
    with pytest.raises(TypeError) as excinfo:
        SharedMemory.create('dflgkjdhfg', 'abc')  # Invalid name
    assert "create(): incompatible function arguments" in str(excinfo.value)
