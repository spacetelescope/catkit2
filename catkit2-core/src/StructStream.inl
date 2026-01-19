#include "StructStream.h"

#include "Memory.h"

template <typename T>
T *StructStream::Extract(std::size_t num_elements)
{
	AddPadding<T>();

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
