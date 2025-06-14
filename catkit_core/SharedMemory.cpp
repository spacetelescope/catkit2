#include "SharedMemory.h"

#include "Timing.h"

#include <stdexcept>
#include <iostream>
#include <array>
#include <algorithm>

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
		// Unmap the view of the file.
		UnmapViewOfFile(m_Buffer);

		// Close the file mapping object. For Windows, once all handles are closed,
		// the shared memory object is automatically deleted.
		CloseHandle(m_File);
#else
		// Delete the shared memory object if we are the owner.
		if (m_IsOwner)
			shm_unlink(m_FileName.c_str());

		// Unmap and close the file descriptor.
		struct stat stat_buf;
		fstat(m_File, &stat_buf);

		munmap(m_Buffer, stat_buf.st_size);
		close(m_File);
#endif
	}
}

std::size_t SharedMemory::GetSharedStateSize()
{
	return SHARED_MEMORY_FNAME_SIZE;
}

std::shared_ptr<SharedMemory> SharedMemory::Create(std::string_view fname, size_t num_bytes_in_buffer)
{
	std::string fname_string = std::string(fname);

#ifdef _WIN32
	// Ensure the last error is zero before calling CreateFileMapping.
	SetLastError(NO_ERROR);

	// Create a file mapping object with the specified name.
	FileObject file = CreateFileMapping(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, (DWORD) num_bytes_in_buffer + sizeof(Header), fname_string.c_str());

	if (file == NULL || GetLastError() != NO_ERROR)
	{
		DWORD error_message_id = GetLastError();
		std::string error_message = GetLastErrorAsString(error_message_id);

		// If we were given a file handle, we should close it.
		if (file)
			CloseHandle(file);

		throw std::runtime_error("Something went wrong while creating shared memory: " + error_message);
	}
#else
	FileObject file = shm_open(fname_string.c_str(), O_CREAT | O_RDWR | O_EXCL, 0666);

	if (file < 0)
	{
		// Throw an error containing the error message.
		std::string error_message = ErrnoAsString(errno);

		throw std::runtime_error("Something went wrong while creating shared memory: " + error_message);
	}

    int res = ftruncate(file, num_bytes_in_buffer + sizeof(Header));

	if (res < 0)
	{
		// Throw an error containing the error message.
		std::string error_message = ErrnoAsString(errno);

		shm_unlink(fname_string.c_str());
		close(file);

		throw std::runtime_error("Something went wrong while setting the size of shared memory: " + error_message);
	}
#endif

	auto obj = std::shared_ptr<SharedMemory>(new SharedMemory(fname, file, true));

	// Set the header for metadata.
	Header *header = reinterpret_cast<Header *>(obj->m_Buffer);
	header->capacity = num_bytes_in_buffer;

	obj->m_Capacity = num_bytes_in_buffer;

	return obj;
}

std::shared_ptr<SharedMemory> SharedMemory::Create(StructStream &stream, size_t num_bytes_in_buffer)
{
	// Create a randomized file name.
	std::string fname = std::to_string(GetTimeStamp()) + ".mem";

	return Create(stream, fname, num_bytes_in_buffer);
}

std::shared_ptr<SharedMemory> SharedMemory::Create(StructStream &stream, std::string_view fname, size_t num_bytes_in_buffer)
{
	// Copy over fname to stream.
	auto arr = stream.Extract<std::array<char, SHARED_MEMORY_FNAME_SIZE>>();
	arr->fill('\0');
	fname.copy(arr->data(), SHARED_MEMORY_FNAME_SIZE - 1);

	return Create(fname, num_bytes_in_buffer);
}

std::shared_ptr<SharedMemory> SharedMemory::Open(std::string_view fname)
{
	std::string fname_string = std::string(fname);

#ifdef _WIN32
	FileObject file = OpenFileMapping(FILE_MAP_ALL_ACCESS, FALSE, fname_string.c_str());

	if (file == NULL)
	{
		// Throw an error containing the error message.
		DWORD error_message_id = GetLastError();
		std::string error_message = GetLastErrorAsString(error_message_id);

		throw std::runtime_error("Something went wrong while opening shared memory: " + error_message);
	}
#else
	FileObject file = shm_open(fname_string.c_str(), O_RDWR, 0666);

	if (file < 0)
	{
		// Throw an error containing the error message.
		std::string error_message = ErrnoAsString(errno);

		throw std::runtime_error("Something went wrong while opening shared memory: " + error_message);
	}
#endif

	auto res = std::shared_ptr<SharedMemory>(new SharedMemory(fname, file, false));

	// Get the header for metadata.
	Header *header = reinterpret_cast<Header *>(res->m_Buffer);
	res->m_Capacity = header->capacity;

	return res;
}

std::shared_ptr<SharedMemory> SharedMemory::Open(StructStream &stream)
{
	auto arr = stream.Extract<std::array<char, SHARED_MEMORY_FNAME_SIZE>>();

	std::string_view fname{arr->data()};

	return Open(fname);
}

SharedMemory::SharedMemory(std::string_view fname, FileObject file, bool is_owner)
	: Shareable(nullptr), m_File(file), m_FileName(fname), m_IsOwner(is_owner), m_Buffer(nullptr)
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

void SharedMemory::Destroy()
{
#ifdef _WIN32
	throw std::runtime_error("Destroying shared memory is not possible on Windows. Close the process using the shared memory instead.");
#else
	shm_unlink(m_FileName.c_str());
#endif
}

void *SharedMemory::GetAddress(std::size_t offset)
{
	return static_cast<char *>(m_Buffer) + sizeof(Header) + offset;
}

ShareableType SharedMemory::GetType() const
{
	return ShareableType::SharedMemory;
}

MemoryType SharedMemory::GetMemoryType() const
{
	return MemoryType::SharedMemory;
}

std::size_t SharedMemory::GetCapacity() const
{
	return m_Capacity;
}

void SharedMemory::WriteReference(StructStream &stream)
{
	auto filename = stream.Extract<char>(SHARED_MEMORY_FNAME_SIZE);

	std::fill(filename, filename + SHARED_MEMORY_FNAME_SIZE, '\0');
	m_FileName.copy(filename, SHARED_MEMORY_FNAME_SIZE - 1);
}

std::string SharedMemory::GetFileName()
{
	return m_FileName;
}
