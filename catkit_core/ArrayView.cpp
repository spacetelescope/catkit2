#include "ArrayView.h"

#include <cstring>

bool ArrayInfo::IsCContiguous() const
{
	// Zero-dimensional arrays are C Contiguous by default.
	if (ndim == 0)
		return true;

	size_t expected_stride = item_size;

	for (std::size_t i = 0; i < ndim; ++i)
	{
		// Axes with length 1 can have whatever stride they want.
		if (shape[ndim - 1 - i] == 1)
			continue;

		// Check the stride against expected.
		if (strides[ndim - 1 - i] != expected_stride)
			return false;

		// Update the expected stride.
		expected_stride *= shape[ndim - 1 - i];
	}

	return true;
}

bool ArrayInfo::IsFContiguous() const
{
	// Zero-dimensional arrays are C Contiguous by default.
	if (ndim == 0)
		return true;

	size_t expected_stride = item_size;

	for (std::size_t i = 0; i < ndim; ++i)
	{
		// Axes with length 1 can have whatever stride they want.
		if (shape[i] == 1)
			continue;

		// Check the stride against expected.
		if (strides[i] != expected_stride)
			return false;

		// Update the expected stride.
		expected_stride *= shape[i];
	}

	return true;
}

std::size_t ArrayInfo::GetSize() const
{
	std::size_t num_items = 1;

	for (std::size_t i = 0; i < ndim; ++i)
	{
		num_items *= shape[i];
	}

	return num_items;
}

std::size_t ArrayInfo::GetSizeInBytes() const
{
	return GetSize() * item_size;
}

bool ArrayView::IsAligned() const
{
	return uintptr_t(data) % 128 == 0;
}

bool ArrayView::IsCContiguous() const
{
	return info.IsCContiguous();
}

bool ArrayView::IsFContiguous() const
{
	return info.IsFContiguous();
}
