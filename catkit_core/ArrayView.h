#ifndef ARRAY_VIEW_H
#define ARRAY_VIEW_H

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
	bool IsFContiguous() const;
    std::size_t GetSize() const;
	std::size_t GetSizeInBytes() const;
};

// A mathematical array class.
// This follows the NumPy convention.
struct ArrayView
{
public:
	ArrayView();
    ArrayView(const ArrayInfo &info, void *data);
	ArrayView(const ArrayView &other);
	ArrayView(ArrayView &&other) noexcept;
	~ArrayView();

	ArrayView &operator=(const ArrayView &other);
	ArrayView &operator=(ArrayView &&other) noexcept;

	bool IsAligned() const;
	bool IsCContiguous() const;
	bool IsFContiguous() const;

	ArrayInfo info;
	void *data;
};

#endif // ARRAY_VIEW_H
