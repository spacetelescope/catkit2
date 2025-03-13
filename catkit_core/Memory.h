#ifndef MEMORY_H
#define MEMORY_H

#include "StructStream.h"

#include <cstddef>

class Memory
{
public:
	virtual ~Memory()
	{
	}

	virtual void *GetAddress(std::size_t offset = 0) = 0;
	virtual std::size_t GetCapacity() const = 0;

	virtual void WriteReference(StructStream &stream) = 0;
};

#endif // MEMORY_H
