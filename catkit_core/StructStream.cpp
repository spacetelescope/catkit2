#include "StructStream.h"

StructStream::StructStream(std::shared_ptr<Memory> buffer, std::size_t offset)
	: m_Buffer(buffer), m_Offset(offset)
{
}

std::size_t StructStream::GetOffset()
{
	return m_Offset;
}

std::shared_ptr<Memory> StructStream::GetBuffer()
{
	return m_Buffer;
}
