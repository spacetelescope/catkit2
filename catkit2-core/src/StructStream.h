#ifndef STRUCT_STREAM_H
#define STRUCT_STREAM_H

#include <cstddef>
#include <algorithm>
#include <memory>

class Memory;

class StructStream
{
public:
	StructStream(std::shared_ptr<Memory> buffer, std::size_t offset = 0);

	template <typename T>
	T *Extract(std::size_t num_elements = 1);

	template <typename... Ts>
	inline void AddPadding();

	std::size_t GetOffset();

	std::shared_ptr<Memory> GetBuffer();

private:
	std::shared_ptr<Memory> m_Buffer;
	std::size_t m_Offset;
};

#include "StructStream.inl"

#endif // STRUCT_STREAM_H
