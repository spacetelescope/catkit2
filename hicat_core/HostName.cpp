#include "HostName.h"

#include <cstring>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tchar.h>
#else
#include <unistd.h>
#endif

void GetHostName(char* hostname)
{
	char name[150];

#ifdef _WIN32
	TCHAR info_buf[150];
	DWORD buf_char_count = 150;
	memset(name, 0, 150);
	if (GetComputerName(info_buf, &buf_char_count))
	{
		for (int i = 0; i<150; i++)
		{
			name[i] = info_buf[i];
		}
	}
	else
	{
		strcpy(name, "unknown");
	}
#else
	memset(name, 0, 150);
	gethostname(name, 150);
#endif
	strncpy(hostname, name, 150);
}
