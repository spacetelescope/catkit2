#include "LogFile.h"

using namespace std;

LogFile::LogFile(const char *filename)
{
	m_File.open(filename);
}

void LogFile::AddLogEntry(const LogEntry &entry)
{
	m_File << entry.time << " ";
	m_File << entry.function << "@" << entry.filename << ":" << "  ";

	switch (entry.severity)
	{
	case S_CRITICAL_ERROR:
		m_File << "Critical Error: ";
		break;
	case S_ERROR:
		m_File << "Error: ";
		break;
	case S_WARNING:
		m_File << "Warning: ";
		break;
	case S_INFO:
		m_File << "Info: ";
		break;
	case S_DEBUG:
		m_File << "Debug: ";
		break;
	case S_USER:
		m_File << "User:";
		break;
	}

	m_File << entry.message << endl;
}