#include "StructStream.h"

#include "Memory.h"

#include <iostream>
#include <stdexcept>

template <typename T>
T *StructStream::Extract(std::size_t num_elements)
{
	AddPadding<T>();

	const auto capacity = m_Buffer->GetCapacity();
	const auto required_bytes = num_elements * sizeof(T);

	if (m_Offset + required_bytes > capacity)
	{
		std::cerr << "StructStream::Extract exceeded buffer capacity: offset="
				  << m_Offset << " required=" << required_bytes
				  << " capacity=" << capacity << std::endl;
		throw std::runtime_error("StructStream::Extract exceeded buffer capacity");
	}

	// Link element to the buffer.
	T *res = reinterpret_cast<T *>(m_Buffer->GetAddress(m_Offset));

	// Consume bytes from the buffer.
	m_Offset += num_elements * sizeof(T);

	return res;
}

template <typename... Ts>
void StructStream::AddPadding()
{
	// Get alignment requirement of the type.
	constexpr std::size_t align = std::max({alignof(Ts)...});

	// Pad the buffer to satisfy alignment requirement.
	m_Offset += (align - (m_Offset % align)) % align;
}
