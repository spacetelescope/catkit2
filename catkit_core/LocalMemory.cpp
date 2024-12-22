#include "LocalMemory.h"

LocalMemory::LocalMemory(std::size_t num_bytes)
    : m_Memory(new char[num_bytes])
{
}

LocalMemory::~LocalMemory()
{
    delete[] m_Memory;
}

void *LocalMemory::GetAddress(std::size_t offset)
{
    return m_Memory + offset;
}
