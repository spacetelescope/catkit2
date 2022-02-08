#ifndef SHARED_MEMORY_H
#define SHARED_MEMORY_H

#include <memory>
#include <string>

#ifdef _WIN32
	#define WIN32_LEAN_AND_MEAN
	#include <windows.h>
#else
	#include <sys/shm.h>
	#include <sys/stat.h>
#endif // _WIN32

#ifdef _WIN32
	typedef HANDLE FileObject;
#else
	typedef int FileObject;
#endif

class SharedMemory
{
private:
	SharedMemory(const std::string &id, FileObject file, bool is_owner);

public:
	~SharedMemory();

	static std::shared_ptr<SharedMemory> Create(const std::string &id, size_t num_bytes_in_buffer);
	static std::shared_ptr<SharedMemory> Open(const std::string &id);

	void *GetAddress();

private:
	std::string m_Id;
	bool m_IsOwner;

	FileObject m_File;
	void *m_Buffer;
};

#endif // SHARED_MEMORY_H
