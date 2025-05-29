#include "Array.h"

#include <cstring>

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

bool Array::IsFortranContiguous() const
{
	return info.IsFortranContiguous();
}
