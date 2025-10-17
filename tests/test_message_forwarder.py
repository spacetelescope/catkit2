"""Unit tests for message forwarder serialization helpers."""

import pytest
import numpy as np
from catkit2.testbed.message_forwarder import (
    serialize_array,
    deserialize_array
)


class TestSerializeArray:
    """Tests for serialize_array function."""

    def test_serialize_float64_1d(self):
        """Test serializing 1D float64 array."""
        data = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        serialized = serialize_array(data)
        
        # Should contain dtype string and shape info
        assert isinstance(serialized, bytes)
        assert len(serialized) > len(data.tobytes())

    def test_serialize_float64_2d(self):
        """Test serializing 2D float64 array (image)."""
        data = np.random.rand(240, 240).astype(np.float64)
        serialized = serialize_array(data)
        
        assert isinstance(serialized, bytes)
        assert len(serialized) > 0

    def test_serialize_uint16(self):
        """Test serializing uint16 array."""
        data = np.arange(100, dtype=np.uint16).reshape(10, 10)
        serialized = serialize_array(data)
        
        assert isinstance(serialized, bytes)

    def test_serialize_int32(self):
        """Test serializing int32 array."""
        data = np.array([-1, 0, 1, 2], dtype=np.int32)
        serialized = serialize_array(data)
        
        assert isinstance(serialized, bytes)

    def test_serialize_complex64(self):
        """Test serializing complex64 array."""
        data = np.array([1+2j, 3+4j], dtype=np.complex64)
        serialized = serialize_array(data)
        
        assert isinstance(serialized, bytes)

    def test_serialize_with_explicit_dtype(self):
        """Test serializing with explicit dtype override."""
        data = np.array([1, 2, 3])
        serialized = serialize_array(data, dtype='float32')
        
        assert isinstance(serialized, bytes)

    def test_serialize_with_explicit_shape(self):
        """Test serializing with explicit shape override."""
        data = np.array([1, 2, 3, 4, 5, 6])
        serialized = serialize_array(data, shape=(2, 3))
        
        assert isinstance(serialized, bytes)

    def test_serialize_scalar(self):
        """Test serializing scalar (0D array)."""
        data = np.array(42.0, dtype=np.float64)
        serialized = serialize_array(data)
        
        assert isinstance(serialized, bytes)


class TestDeserializeArray:
    """Tests for deserialize_array function."""

    def test_roundtrip_float64_1d(self):
        """Test serialize/deserialize roundtrip for 1D float64."""
        original = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.allclose(original, recovered)
        assert original.dtype == recovered.dtype
        assert original.shape == recovered.shape

    def test_roundtrip_float64_2d(self):
        """Test serialize/deserialize roundtrip for 2D float64."""
        original = np.random.rand(240, 240).astype(np.float64)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.allclose(original, recovered)
        assert original.dtype == recovered.dtype
        assert original.shape == recovered.shape

    def test_roundtrip_uint16(self):
        """Test serialize/deserialize roundtrip for uint16."""
        original = np.arange(100, dtype=np.uint16).reshape(10, 10)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.array_equal(original, recovered)
        assert original.dtype == recovered.dtype
        assert original.shape == recovered.shape

    def test_roundtrip_int32(self):
        """Test serialize/deserialize roundtrip for int32."""
        original = np.array([-1, 0, 1, 2], dtype=np.int32)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.array_equal(original, recovered)
        assert original.dtype == recovered.dtype

    def test_roundtrip_complex64(self):
        """Test serialize/deserialize roundtrip for complex64."""
        original = np.array([1+2j, 3+4j], dtype=np.complex64)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.allclose(original, recovered)
        assert original.dtype == recovered.dtype

    def test_roundtrip_3d_array(self):
        """Test serialize/deserialize for 3D array."""
        original = np.random.rand(10, 20, 30).astype(np.float32)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.allclose(original, recovered)
        assert original.dtype == recovered.dtype
        assert original.shape == recovered.shape

    def test_roundtrip_scalar(self):
        """Test serialize/deserialize for scalar."""
        original = np.array(42.0, dtype=np.float64)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.allclose(original, recovered)
        assert original.dtype == recovered.dtype
        assert original.shape == recovered.shape

    def test_roundtrip_large_array(self):
        """Test serialize/deserialize for large array."""
        original = np.random.rand(1024, 1024).astype(np.float64)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.allclose(original, recovered)
        assert original.dtype == recovered.dtype
        assert original.shape == recovered.shape

    def test_roundtrip_preserves_nan(self):
        """Test that NaN values are preserved."""
        original = np.array([1.0, np.nan, 3.0], dtype=np.float64)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.isnan(recovered[1])
        assert recovered[0] == original[0]
        assert recovered[2] == original[2]

    def test_roundtrip_preserves_inf(self):
        """Test that inf values are preserved."""
        original = np.array([1.0, np.inf, -np.inf], dtype=np.float64)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.isinf(recovered[1]) and recovered[1] > 0
        assert np.isinf(recovered[2]) and recovered[2] < 0
        assert recovered[0] == original[0]


class TestBrokerIntegration:
    """Tests for broker integration (numpy array handling)."""

    def test_deserialize_from_numpy_array(self):
        """Test deserializing when data is numpy array (from broker)."""
        original = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        serialized = serialize_array(original)

        # Convert serialized bytes to numpy array (as broker does)
        serialized_array = np.frombuffer(serialized, dtype=np.uint8)

        # Deserialize should handle numpy array input
        recovered = deserialize_array(serialized_array)

        assert np.allclose(original, recovered)
        assert original.dtype == recovered.dtype
        assert original.shape == recovered.shape

    def test_deserialize_accepts_bytes_and_arrays(self):
        """Test that deserialize accepts both bytes and numpy arrays."""
        original = np.array([1, 2, 3, 4, 5], dtype=np.int32)
        serialized = serialize_array(original)

        # Test with bytes
        recovered_bytes = deserialize_array(serialized)

        # Test with numpy array
        serialized_array = np.frombuffer(serialized, dtype=np.uint8)
        recovered_array = deserialize_array(serialized_array)

        # Both should produce same result
        assert np.array_equal(recovered_bytes, recovered_array)
        assert np.array_equal(original, recovered_bytes)

    def test_broker_image_roundtrip(self):
        """Test roundtrip simulating broker path."""
        # Simulate sender
        original = np.random.rand(240, 240).astype(np.float64)
        serialized = serialize_array(original)

        # Simulate broker storing as numpy array
        broker_stored = np.frombuffer(serialized, dtype=np.uint8)

        # Simulate receiver
        recovered = deserialize_array(broker_stored)

        assert np.allclose(original, recovered)
        assert original.shape == recovered.shape
        assert original.dtype == recovered.dtype


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_array(self):
        """Test serializing empty array."""
        original = np.array([], dtype=np.float64)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert len(recovered) == 0
        assert original.dtype == recovered.dtype

    def test_single_element_array(self):
        """Test serializing single element array."""
        original = np.array([42.0], dtype=np.float64)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert recovered[0] == original[0]
        assert original.dtype == recovered.dtype

    def test_bool_array(self):
        """Test serializing boolean array."""
        original = np.array([True, False, True], dtype=bool)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.array_equal(original, recovered)
        assert original.dtype == recovered.dtype

    def test_uint8_array(self):
        """Test serializing uint8 array (common for images)."""
        original = np.random.randint(0, 256, (480, 640), dtype=np.uint8)
        serialized = serialize_array(original)
        recovered = deserialize_array(serialized)
        
        assert np.array_equal(original, recovered)
        assert original.dtype == recovered.dtype
        assert original.shape == recovered.shape

    def test_various_shapes(self):
        """Test various array shapes."""
        shapes = [
            (10,),
            (10, 20),
            (10, 20, 30),
            (10, 20, 30, 40),
            (1,),
            (1, 1),
            (1, 1, 1),
        ]
        
        for shape in shapes:
            original = np.random.rand(*shape).astype(np.float64)
            serialized = serialize_array(original)
            recovered = deserialize_array(serialized)
            
            assert original.shape == recovered.shape
            assert np.allclose(original, recovered)


class TestImageSimulation:
    """Tests simulating real image use cases."""

    def test_camera_image_240x240_float64(self):
        """Simulate camera image: 240x240 float64."""
        image = np.random.rand(240, 240).astype(np.float64)
        serialized = serialize_array(image)
        recovered = deserialize_array(serialized)
        
        assert recovered.shape == (240, 240)
        assert recovered.dtype == np.float64
        assert np.allclose(image, recovered)

    def test_camera_image_480x640_uint8(self):
        """Simulate camera image: 480x640 uint8."""
        image = np.random.randint(0, 256, (480, 640), dtype=np.uint8)
        serialized = serialize_array(image)
        recovered = deserialize_array(serialized)
        
        assert recovered.shape == (480, 640)
        assert recovered.dtype == np.uint8
        assert np.array_equal(image, recovered)

    def test_multichannel_image_rgb(self):
        """Simulate RGB image: 480x640x3."""
        image = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        serialized = serialize_array(image)
        recovered = deserialize_array(serialized)
        
        assert recovered.shape == (480, 640, 3)
        assert recovered.dtype == np.uint8
        assert np.array_equal(image, recovered)

    def test_waveform_data_float32(self):
        """Simulate waveform data: 1D float32."""
        waveform = np.sin(np.linspace(0, 2*np.pi, 1000)).astype(np.float32)
        serialized = serialize_array(waveform)
        recovered = deserialize_array(serialized)
        
        assert recovered.shape == (1000,)
        assert recovered.dtype == np.float32
        assert np.allclose(waveform, recovered)

    def test_matrix_data_float64(self):
        """Simulate matrix data: NxN float64."""
        matrix = np.random.randn(100, 100).astype(np.float64)
        serialized = serialize_array(matrix)
        recovered = deserialize_array(serialized)
        
        assert recovered.shape == (100, 100)
        assert recovered.dtype == np.float64
        assert np.allclose(matrix, recovered)


class TestMetadataIntegrity:
    """Tests to verify metadata is correctly preserved."""

    def test_dtype_preserved(self):
        """Test that dtype is preserved through serialization."""
        dtypes = [
            np.float32, np.float64,
            np.int8, np.int16, np.int32, np.int64,
            np.uint8, np.uint16, np.uint32, np.uint64,
            np.complex64, np.complex128,
            bool
        ]
        
        for dtype in dtypes:
            if dtype is bool:
                original = np.array([True, False], dtype=dtype)
            else:
                original = np.array([1, 2], dtype=dtype)
            
            serialized = serialize_array(original)
            recovered = deserialize_array(serialized)
            
            assert original.dtype == recovered.dtype, \
                f"dtype mismatch for {dtype}"

    def test_shape_preserved(self):
        """Test that shape is preserved through serialization."""
        shapes = [
            (10,),
            (10, 20),
            (5, 10, 15),
            (2, 3, 4, 5),
        ]
        
        for shape in shapes:
            original = np.random.rand(*shape)
            serialized = serialize_array(original)
            recovered = deserialize_array(serialized)
            
            assert original.shape == recovered.shape, \
                f"shape mismatch for {shape}"

    def test_header_minimal(self):
        """Test that header is minimal and doesn't waste space."""
        data = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        serialized = serialize_array(data)

        # Header should be small: dtype_len(1) + dtype_str + shape_len(1)
        # + shape (2 bytes per dimension for 1D)
        # For float64 (6 chars) and shape (1D): 1 + 6 + 1 + 2 = 10 bytes
        data_size = len(data.tobytes())
        serialized_size = len(serialized)
        overhead = serialized_size - data_size

        # Overhead should be less than 100 bytes even for large arrays
        assert overhead < 100, \
            f"Overhead too large: {overhead} bytes for {data_size} bytes data"
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
