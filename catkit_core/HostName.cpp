#include "HostName.h"

#include <cstring>
#include <locale>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tchar.h>
#else
#include <unistd.h>
#endif

std::string GetHostName()
{
#ifdef _WIN32
	TCHAR info_buf[MAX_COMPUTERNAME_LENGTH + 1];
	DWORD buf_char_count = MAX_COMPUTERNAME_LENGTH + 1;

	if (GetComputerName(info_buf, &buf_char_count))
	{
#ifdef UNICODE
		std::vector<char> buffer;

		int size = WideCharToMultiByte(CP_UTF8, 0, info_buf, -1, NULL, 0, NULL, NULL);

		if (size > 0)
		{
			buffer.resize(size);
			WideCharToMultiByte(CP_UTF8, 0, info_buf, -1, static_cast<BYTE*>(&buffer[0]), buffer.size(), NULL, NULL);
		}
		else
		{
			throw std::runtime_error("Host name cannot be converted to ASCII.");
		}

		return std::string(buffer[0]);
#else
		return std::string(info_buf);
#endif
	}
	else
	{
		return "unknown";
	}
#else
	char name[150];
	memset(name, 0, 150);

	// Get a hostname, but ensure that it's zero terminated at all costs.
	if (gethostname(name, 150 - 1))
		throw std::runtime_error("Host name could not be retrieved.");

	return name;
#endif
}
