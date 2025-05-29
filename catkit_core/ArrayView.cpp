#include "Array.h"

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

Array::Array()
	: data(nullptr), owns_data(false)
{
}

Array::Array(const ArrayInfo &info, void *data, bool owns_data)
	: data(data), info(info), owns_data(owns_data)
{
}

Array::Array(const Array &other)
	: data(other.data), info(other.info), owns_data(false)
{
}

Array::Array(Array &&other) noexcept
	: Array()
{
	*this = std::move(other);
}

Array::~Array()
{
	if (owns_data)
		delete[] data;
}

Array &Array::operator=(const Array &other)
{
	info = other.info;
	data = other.data;
	owns_data = false;

	return *this;
}

Array &Array::operator=(Array &&other) noexcept
{
	std::swap(info, other.info);
	std::swap(data, other.data);
	std::swap(owns_data, other.owns_data);

	return *this;
}

Array Array::Copy()
{
	if (!data)
		return {};

	char *new_data = new char[info.GetSizeInBytes()];
	std::memcpy(new_data, data, info.GetSizeInBytes());

	return Array(info, new_data);
}

bool Array::IsAligned() const
{
	return uintptr_t(data) % 128 == 0;
}

bool Array::IsCContiguous() const
{
	return info.IsCContiguous();
}

bool Array::IsFContiguous() const
{
	return info.IsFContiguous();
}
