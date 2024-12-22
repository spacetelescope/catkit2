#ifndef LOCAL_MEMORY_H
#define LOCAL_MEMORY_H

#include "Memory.h"

class LocalMemory : public Memory
{
public:
    LocalMemory(std::size_t num_bytes);
    virtual ~LocalMemory();

    virtual void *GetAddress(std::size_t offset = 0);

private:
    char *m_Memory;
};

#endif // LOCAL_MEMORY_H
