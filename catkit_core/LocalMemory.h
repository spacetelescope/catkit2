#ifndef LOCAL_MEMORY_H
#define LOCAL_MEMORY_H

#include "Memory.h"

class LocalMemory : public Memory
{
public:
    LocalMemory(std::size_t num_bytes);
    virtual ~LocalMemory();

    virtual void *GetAddress(std::size_t offset = 0) override;
    virtual std::size_t GetCapacity() const override;

private:
    char *m_Memory;
    const std::size_t m_Capacity;
};

#endif // LOCAL_MEMORY_H
