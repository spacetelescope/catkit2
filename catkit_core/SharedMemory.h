#ifndef SHARED_MEMORY_H
#define SHARED_MEMORY_H

#include "Memory.h"

#include <memory>
#include <string>
#include <string_view>
#include <cstdint>
#include <cstddef>

#include "Shareable.h"

#ifdef _WIN32
	#define WIN32_LEAN_AND_MEAN
	#define NOMINMAX
	#include <windows.h>
#else
	#include <sys/mman.h>
	#include <sys/stat.h>
	#include <fcntl.h>
	#include <unistd.h>
#endif // _WIN32

const int SHARED_MEMORY_FNAME_SIZE = 256;

class SharedMemory : public Memory
{
public:
	#ifdef _WIN32
	typedef HANDLE FileObject;
	#else
	typedef int FileObject;
	#endif

private:
	SharedMemory(std::string_view fname, FileObject file, bool is_owner);

	struct Header
	{
		std::uint64_t capacity;

		// Pad to 128bytes.
		char padding[128 - sizeof(capacity)];
	};

public:
	virtual ~SharedMemory();

	std::size_t GetSharedStateSize();

	static std::shared_ptr<SharedMemory> Create(StructStream &stream, std::string_view fname, size_t num_bytes_in_buffer);
	static std::shared_ptr<SharedMemory> Create(StructStream &stream, size_t num_bytes_in_buffer);
	static std::shared_ptr<SharedMemory> Create(std::string_view fname, size_t num_bytes_in_buffer);
	static std::shared_ptr<SharedMemory> Open(StructStream &stream);
	static std::shared_ptr<SharedMemory> Open(std::string_view fname);

	virtual void *GetAddress(std::size_t offset = 0) override;
	virtual std::size_t GetCapacity() const override;
	virtual void WriteReference(StructStream &stream) override;

	ShareableType GetType() const override;

private:
	std::string m_FileName;
	bool m_IsOwner;

	FileObject m_File;
	void *m_Buffer;

	std::size_t m_Capacity;
};

#endif // SHARED_MEMORY_H
