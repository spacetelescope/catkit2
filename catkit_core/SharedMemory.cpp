#include "SharedMemory.h"

#include <stdexcept>

SharedMemory::~SharedMemory()
{
	if (m_Buffer)
	{
#ifdef _WIN32
		UnmapViewOfFile(m_Buffer);
		CloseHandle(m_File);
#else
		if (m_IsOwner)
			shm_unlink((m_Id + ".mem").c_str());

		stat stat_buf;
		fstat(m_File, &stat_buf);

		munmap(m_Buffer, stat_buf.st_size);
		close(m_File);
#endif
	}
}

std::shared_ptr<SharedMemory> SharedMemory::Create(const std::string &id, size_t num_bytes_in_buffer)
{
#ifdef _WIN32
	FileObject file = CreateFileMapping(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, (DWORD) num_bytes_in_buffer, (id + ".mem").c_str());

	if (file == NULL)
		throw std::runtime_error("Something went wrong while creating shared memory.");
#else
	FileObject file = shm_open((id + ".mem").c_str(), O_CREAT | O_RDWR | O_EXCL, 0666);

	if (file < 0)
		throw std::runtime_error("Something went wrong while creating shared memory.");

    int res = ftruncate(file, num_bytes_in_buffer);

	if (res < 0)
	{
		shm_unlink((id + ".mem").c_str();
		close(file);

		throw std::runtime_error("Something went wrong while setting the size of shared memory.");
	}
#endif

	return std::shared_ptr<SharedMemory>(new SharedMemory(id, file, true));
}

std::shared_ptr<SharedMemory> SharedMemory::Open(const std::string &id)
{
#ifdef _WIN32
	FileObject file = OpenFileMapping(FILE_MAP_ALL_ACCESS, FALSE, (id + ".mem").c_str());

	if (file == NULL)
		throw std::runtime_error("Something went wrong while opening shared memory.");
#else
	FileObject file = shm_open((id + ".mem").c_str(), O_RDWR, 0666);

	if (file < 0)
		throw std::runtime_error("Something went wrong while creating shared memory.");
#endif

	return std::shared_ptr<SharedMemory>(new SharedMemory(id, file, false));
}

SharedMemory::SharedMemory(const std::string &id, FileObject file, bool is_owner)
	: m_File(file), m_Id(id), m_IsOwner(is_owner), m_Buffer(nullptr)
{
#ifdef _WIN32
	m_Buffer = MapViewOfFile(m_File, FILE_MAP_ALL_ACCESS, 0, 0, 0);
#else
	stat stat_buf;
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
