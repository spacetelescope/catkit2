#ifndef STRUCT_STREAM_H
#define STRUCT_STREAM_H

#include <cstddef>

class StructStream
{
public:
	StructStream(void *buffer)
		: m_Buffer(reinterpret_cast<char *>(buffer)),
	m_Offset(0)
	{
	}

	template <typename T>
	T *Extract(std::size_t num_elements = 1)
	{
		AddPadding<T>();

		// Link element to the buffer.
		T *res = reinterpret_cast<T *>(m_Buffer + m_Offset);

		// Consume bytes from the buffer.
		m_Offset += num_elements * sizeof(T);

		return res;
	}

	template <typename T>
	inline void AddPadding()
	{
		// Get alignment requirement of the type.
		constexpr std::size_t align = alignof(T);

		// Pad the buffer to satisfy alignment requirement.
		m_Offset += (align - (m_Offset % align)) % align;
	}

	std::size_t GetOffset()
	{
		return m_Offset;
	}

private:
	char *m_Buffer;
	std::size_t m_Offset;
};

#endif // STRUCT_STREAM_H
