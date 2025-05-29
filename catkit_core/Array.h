#ifndef ARRAY_H
#define ARRAY_H

#include <cstddef>
#include <cstdint>
#include <array>

const size_t MAX_NUM_DIMENSIONS = 4;

struct ArrayInfo
{
	char data_type; // b, i, u, f, c
	char byte_order; // < > = !
	std::uint8_t item_size; // 1, 2, 4, 8, 16
	std::uint8_t ndim; // 0, 1, 2, 3, ..., MAX_NUM_DIMENSIONS
	std::array<std::uint32_t, MAX_NUM_DIMENSIONS> shape; // in elements
	std::array<std::uint32_t, MAX_NUM_DIMENSIONS> strides; // in bytes

	bool IsCContiguous() const;
	bool IsFortranContiguous() const;
    std::size_t GetItemSize() const;
    std::size_t GetSize() const;
	std::size_t GetSizeInBytes() const;
};

// A mathematical array class.
// This follows the NumPy convention.
struct Array
{
public:
	Array();
    Array(const ArrayInfo &info, void *data, bool owns_data = true);
	Array(const Array &other);
	Array(Array &&other) noexcept;
	~Array();

	Array &operator=(const Array &other);
	Array &operator=(Array &&other) noexcept;

    Array Copy();

	bool IsAligned() const;
	bool IsCContiguous() const;
	bool IsFortranContiguous() const;

	ArrayInfo info;
	bool owns_data;
	void *data;
};

#endif // ARRAY_H
