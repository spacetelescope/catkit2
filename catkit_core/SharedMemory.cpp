#include "SharedMemory.h"

#include "Timing.h"

#include <stdexcept>
#include <iostream>
#include <string>

SharedMemory::~SharedMemory()
{
	if (m_Buffer)
	{
#ifdef _WIN32
		UnmapViewOfFile(m_Buffer);
		CloseHandle(m_File);
#else
		if (m_IsOwner)
			shm_unlink(m_FileName.c_str());

		struct stat stat_buf;
		fstat(m_File, &stat_buf);

		munmap(m_Buffer, stat_buf.st_size);
		close(m_File);
#endif
	}
}

std::unique_ptr<SharedMemory> SharedMemory::Create(SharedState *shared_state, std::string_view fname, size_t num_bytes_in_buffer)
{
	std::cout << "Creating shared memory " << fname << std::endl;

	std::string fname_string = std::string(fname);

#ifdef _WIN32
	FileObject file = CreateFileMapping(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, (DWORD) num_bytes_in_buffer, fname_string.c_str());

	if (file == NULL)
		throw std::runtime_error("Something went wrong while creating shared memory.");
#else
	FileObject file = shm_open(fname_string.c_str(), O_CREAT | O_RDWR | O_EXCL, 0666);

	if (file < 0)
		throw std::runtime_error("Something went wrong while creating shared memory.");

    int res = ftruncate(file, num_bytes_in_buffer);

	if (res < 0)
	{
		shm_unlink(fname_string.c_str());
		close(file);

		throw std::runtime_error("Something went wrong while setting the size of shared memory.");
	}
#endif

	if (shared_state)
	{
		std::fill(shared_state->fname, shared_state->fname + SHARED_MEMORY_FNAME_SIZE, '\0');
		fname.copy(shared_state->fname, SHARED_MEMORY_FNAME_SIZE - 1);
	}

	return std::unique_ptr<SharedMemory>(new SharedMemory(fname, file, true));
}

std::unique_ptr<SharedMemory> SharedMemory::Create(SharedState *shared_state, size_t num_bytes_in_buffer)
{
	// Create a randomized file name.
	std::string fname = std::to_string(GetTimeStamp()) + ".mem";

	return Create(shared_state, fname, num_bytes_in_buffer);
}

std::unique_ptr<SharedMemory> SharedMemory::Create(std::string_view fname, size_t num_bytes_in_buffer)
{
	return Create(nullptr, fname, num_bytes_in_buffer);
}

std::unique_ptr<SharedMemory> SharedMemory::Open(std::string_view fname)
{
	std::string fname_string = std::string(fname);

#ifdef _WIN32
	FileObject file = OpenFileMapping(FILE_MAP_ALL_ACCESS, FALSE, fname_string.c_str());

	if (file == NULL)
		throw std::runtime_error("Something went wrong while opening shared memory.");
#else
	FileObject file = shm_open(fname_string.c_str(), O_RDWR, 0666);

	if (file < 0)
		throw std::runtime_error("Something went wrong while opening shared memory.");
#endif

	return std::unique_ptr<SharedMemory>(new SharedMemory(fname, file, false));
}

std::unique_ptr<SharedMemory> SharedMemory::Open(SharedState *shared_state)
{
	std::string_view fname{shared_state->fname};

	return Open(fname);
}

SharedMemory::SharedMemory(std::string_view fname, FileObject file, bool is_owner)
	: m_File(file), m_FileName(fname), m_IsOwner(is_owner), m_Buffer(nullptr),
	ShareableImpl(nullptr)
{
#ifdef _WIN32
	m_Buffer = MapViewOfFile(m_File, FILE_MAP_ALL_ACCESS, 0, 0, 0);
#else
	struct stat stat_buf;
	fstat(m_File, &stat_buf);

	m_Buffer = mmap(0, stat_buf.st_size, PROT_WRITE, MAP_SHARED, m_File, 0);
#endif // _WIN32

	if (!m_Buffer)
		throw std::runtime_error("Something went wrong while mapping shared memory file.");
}

void *SharedMemory::GetAddress()
{
	return m_Buffer;
}
