#ifndef MEMORY_H
#define MEMORY_H

#include <cstddef>

class Memory
{
public:
	virtual ~Memory()
	{
	}

	virtual void *GetAddress(std::size_t offset = 0) = 0;
	virtual std::size_t GetCapacity() const = 0;
};

#endif // MEMORY_H
