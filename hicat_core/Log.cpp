#include "Log.h"
#include "TimeStamp.h"

#include <algorithm>
#include <iostream>

using namespace std;

LogEntry::LogEntry(std::string filename, unsigned int line, std::string function, Severity severity, std::string message, uint64_t timestamp)
	: filename(filename), line(line), function(function), severity(severity), message(message), timestamp(timestamp)
{
	time = ConvertTimestampToString(timestamp);
}

vector<LogListener *> log_listeners;

LogListener::LogListener()
{
	// Add myself to the log_listeners vector.
	log_listeners.push_back(this);
}

LogListener::~LogListener()
{
	// Remove myself from the log_listeners vector.
	auto it = find(log_listeners.begin(), log_listeners.end(), this);
	if (it != log_listeners.end())
		log_listeners.erase(it);
}

void LogListener::AddLogEntry(const LogEntry &entry)
{
}

void SubmitLogEntry(std::string filename, unsigned int line, std::string function, Severity severity, std::string message)
{
	auto entry = LogEntry(filename, line, function, severity, message, GetTimeStamp());
	for (auto listener : log_listeners)
	{
		listener->AddLogEntry(entry);
	}
}

std::string ToString(Severity severity)
{
	switch (severity)
	{
	case S_CRITICAL_ERROR:
		return "critical error";
	case S_ERROR:
		return "error";
	case S_WARNING:
		return "warning";
	case S_USER:
		return "user";
	case S_INFO:
		return "info";
	case S_DEBUG:
		return "debug";
	default:
		return "undefined";
	}
}
