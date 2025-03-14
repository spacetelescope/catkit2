#ifndef LOCAL_MEMORY_H
#define LOCAL_MEMORY_H

#include "Memory.h"
#include "Shareable.h"
#include "Util.h"

class LocalMemory : public Shareable, public Memory
{
public:
    virtual ~LocalMemory();

    static std::unique_ptr<LocalMemory> Create(StructStream &stream, std::size_t num_bytes);
    static std::unique_ptr<LocalMemory> Open(StructStream &stream);

    virtual void *GetAddress(std::size_t offset = 0) override;
    virtual std::size_t GetCapacity() const override;
    virtual void WriteReference(StructStream &stream) override;

    virtual ShareableType GetType() const override;

private:
    LocalMemory(char *memory, std::size_t num_bytes, bool is_owner);

    char *m_Memory;
    const std::size_t m_Capacity;
    bool m_IsOwner;
};

#endif // LOCAL_MEMORY_H
