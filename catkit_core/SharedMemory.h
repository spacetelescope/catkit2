#ifndef SHARED_MEMORY_H
#define SHARED_MEMORY_H

#include <memory>
#include <string>
#include <string_view>

#include "Shareable.h"
#include "Memory.h"

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

template<>
struct SharedState<ShareableType::SharedMemory>
{
	char id[SHARED_MEMORY_FNAME_SIZE];
};

class SharedMemory : public ShareableImpl<ShareableType::SharedMemory>
{
public:
	#ifdef _WIN32
	typedef HANDLE FileObject;
	#else
	typedef int FileObject;
	#endif

private:
	SharedMemory(SharedState *shared_state, FileObject file, bool is_owner);

public:
	~SharedMemory();

	static std::unique_ptr<SharedMemory> Create(SharedState *shared_state, std::string_view id, size_t num_bytes_in_buffer);
	static std::unique_ptr<SharedMemory> Open(SharedState *shared_state);
	static std::unique_ptr<SharedMemory> Open(std::string_view id);

	void *GetAddress();

private:
	std::string m_Id;
	bool m_IsOwner;

	FileObject m_File;
	void *m_Buffer;
};

#endif // SHARED_MEMORY_H
