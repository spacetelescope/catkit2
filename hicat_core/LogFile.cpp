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
	case S_CRITICAL:
		m_File << "Critical: ";
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
	}

	m_File << entry.message << endl;
}