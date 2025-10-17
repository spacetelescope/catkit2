"""Simple integration test for message forwarder."""

import numpy as np
from catkit2.testbed.message_forwarder import (
    serialize_array,
    deserialize_array
)


def test_serialization_roundtrip():
    """Test serialization and deserialization roundtrip."""
    # Create test image
    image = np.random.rand(240, 240).astype(np.float64)

    # Serialize
    serialized = serialize_array(image)
    print(f"✓ Serialized image: {len(serialized)} bytes")

    # Deserialize
    recovered = deserialize_array(serialized)
    msg = f"shape={recovered.shape}, dtype={recovered.dtype}"
    print(f"✓ Deserialized image: {msg}")

    # Verify
    assert np.allclose(image, recovered), "Images don't match!"
    print("✓ Images match perfectly")

    return True


if __name__ == '__main__':
    try:
        if test_serialization_roundtrip():
            print("\n✅ All integration tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
