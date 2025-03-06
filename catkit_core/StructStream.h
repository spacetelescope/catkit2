#ifndef STRUCT_STREAM_H
#define STRUCT_STREAM_H

#include <cstddef>
#include <concepts>
#include <type_traits>

class StructStream
{
public:
	StructStream(void *buffer)
		: m_Buffer(reinterpret_cast<char *>(buffer)),
	m_Offset(0)
	{
	}

	template <typename T>
	requires std::is_fundamental_v<T>
	StructStream &operator >> (T *&element)
	{
		AddPadding<T>();

		// Link element to the buffer.
		element = reinterpret_cast<T *>(m_Buffer + m_Offset);

		// Consume bytes from the buffer.
		m_Offset += size;

		return *this;
	}

	template <typename T, std::size_t N>
	requires std::is_fundamental_v<T>
	StructStream &operator >> (T (*&array)[N])
	{
		AddPadding<T>();

		// Link element to the buffer.
		array = reinterpret_cast<T (*)[N]>(m_Buffer + m_Offset);

		// Consume bytes from the buffer.
		m_Offset += size * N;

		return *this;
	}

	template <typename T>
	inline void AddPadding()
	{
		// Get alignment requirement of the type.
		constexpr std::size_t align = alignof(T);

		// Pad the buffer to satisfy alignment requirement.
		std::size_t padding = (align - (m_Offset % align)) % align;
		m_Offset += padding;
	}

	char *m_Buffer;
	std::size_t m_Offset;
};

#endif // STRUCT_STREAM_H
