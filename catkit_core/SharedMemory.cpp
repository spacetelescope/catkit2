#include "SharedMemory.h"

#include <stdexcept>

#ifdef _WIN32
	//Returns the last Win32 error, in string format. Returns an empty string if there is no error.
	std::string GetLastErrorAsString(DWORD error_message_id)
	{
		//Get the error message ID, if any.
		if(error_message_id == 0) {
			return std::string(); //No error message has been recorded
		}

		LPSTR message_buffer = nullptr;

		//Ask Win32 to give us the string version of that message ID.
		//The parameters we pass in, tell Win32 to create the buffer that holds the message for us (because we don't yet know how long the message string will be).
		size_t size = FormatMessageA(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
									NULL, error_message_id, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), (LPSTR) &message_buffer, 0, NULL);

		//Copy the error message into a std::string.
		std::string message(message_buffer, size);

		//Free the Win32's string's buffer.
		LocalFree(message_buffer);

		return message;
	}
#else
	#include <cerrno>
	#include <cstring>

	std::string ErrnoAsString(int error_id)
	{
		char *e = std::strerror(error_id);
		return e ? e : "";
	}
#endif

SharedMemory::~SharedMemory()
{
	if (m_Buffer)
	{
#ifdef _WIN32
		// Unmap the buffer.
		UnmapViewOfFile(m_Buffer);

		// Close the file.
		// If all handles to the file are closed, the file is automatically removed. In Windows
		// there is no manual remove as for Linux/MacOS.
		CloseHandle(m_File);
#else
		// Remove the shared memory if we are the owner. After this, the shared memory cannot
		// be opened again.
		if (m_IsOwner)
			shm_unlink((m_Id + ".mem").c_str());

		// Get size in bytes.
		struct stat stat_buf;
		fstat(m_File, &stat_buf);

		// Unmap buffer and close the file.
		munmap(m_Buffer, stat_buf.st_size);
		close(m_File);
#endif
	}
}

std::shared_ptr<SharedMemory> SharedMemory::Create(const std::string &id, size_t num_bytes_in_buffer)
{
#ifdef _WIN32
	// Ensure last error is zero before calling CreateFileMapping().
	SetLastError(NO_ERROR);

	FileObject file = CreateFileMapping(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, (DWORD) num_bytes_in_buffer, (id + ".mem").c_str());

	if (file == NULL || GetLastError() != NO_ERROR)
	{
		// Throw an error containing the error message.
		DWORD error_message_id = GetLastError();
		std::string error_message = GetLastErrorAsString(error_message_id);

		// Ensure that we close the file handle, if we were given one.
		if (file)
			CloseHandle(file);

		throw std::runtime_error("Something went wrong while creating shared memory: " + error_message);
	}
#else
	FileObject file = shm_open((id + ".mem").c_str(), O_CREAT | O_RDWR | O_EXCL, 0666);

	if (file < 0)
	{
		// Throw an error containing the error message.
		std::string error_message = ErrnoAsString(errno);

		throw std::runtime_error("Something went wrong while creating shared memory: " + error_message);
	}

    int res = ftruncate(file, num_bytes_in_buffer);

	if (res < 0)
	{
		// Throw an error containing the error message.
		std::string error_message = ErrnoAsString(errno);

		shm_unlink((id + ".mem").c_str());
		close(file);

		throw std::runtime_error("Something went wrong while setting the size of shared memory: " + error_message);
	}
#endif

	return std::shared_ptr<SharedMemory>(new SharedMemory(id, file, true));
}

std::shared_ptr<SharedMemory> SharedMemory::Open(const std::string &id)
{
#ifdef _WIN32
	FileObject file = OpenFileMapping(FILE_MAP_ALL_ACCESS, FALSE, (id + ".mem").c_str());

	if (file == NULL)
	{
		// Throw an error containing the error message.
		DWORD error_message_id = GetLastError();
		std::string error_message = GetLastErrorAsString(error_message_id);

		throw std::runtime_error("Something went wrong while opening shared memory: " + error_message);
	}
#else
	FileObject file = shm_open((id + ".mem").c_str(), O_RDWR, 0666);

	if (file < 0)
	{
		// Throw an error containing the error message.
		std::string error_message = ErrnoAsString(errno);

		throw std::runtime_error("Something went wrong while opening shared memory: " + error_message);
	}
#endif

	return std::shared_ptr<SharedMemory>(new SharedMemory(id, file, false));
}

SharedMemory::SharedMemory(const std::string &id, FileObject file, bool is_owner)
	: m_File(file), m_Id(id), m_IsOwner(is_owner), m_Buffer(nullptr)
{
#ifdef _WIN32
	m_Buffer = MapViewOfFile(m_File, FILE_MAP_ALL_ACCESS, 0, 0, 0);

	if (!m_Buffer)
	{
		// Throw an error containing the error message.
		DWORD error_message_id = GetLastError();
		std::string error_message = GetLastErrorAsString(error_message_id);

		throw std::runtime_error("Something went wrong while mapping shared memory file: " + error_message);
	}
#else
	struct stat stat_buf;
	fstat(m_File, &stat_buf);

	m_Buffer = mmap(0, stat_buf.st_size, PROT_WRITE, MAP_SHARED, m_File, 0);

	if (!m_Buffer)
	{
		// Throw an error containing the error message.
		std::string error_message = ErrnoAsString(errno);

		throw std::runtime_error("Something went wrong while mapping shared memory file: " + error_message);
	}
#endif // _WIN32
}

void *SharedMemory::GetAddress()
{
	return m_Buffer;
}
