#include "ArrayView.h"

#include <cstring>

bool ArrayInfo::IsCContiguous() const
{
	size_t expected_stride = item_size;

	for (std::size_t i = 0; i < ndim; ++i)
	{
		if (strides[ndim - 1 - i] != expected_stride)
			return false;

		expected_stride *= shape[ndim - 1 - i];
	}

	return true;
}

bool ArrayInfo::IsFContiguous() const
{
	size_t expected_stride = item_size;

	for (std::size_t i = 0; i < ndim; ++i)
	{
		if (strides[i] != expected_stride)
			return false;

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
