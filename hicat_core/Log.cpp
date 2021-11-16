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
	// Remove myself from the log_listeners vector (with erase-remove).
	log_listeners.erase(std::remove(log_listeners.begin(), log_listeners.end(), this), log_listeners.end());
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

std::string ConvertSeverityToString(Severity severity)
{
	switch (severity)
	{
	case S_CRITICAL:
		return "critical";
	case S_ERROR:
		return "error";
	case S_WARNING:
		return "warning";
	case S_INFO:
		return "info";
	case S_DEBUG:
		return "debug";
	default:
		return "undefined";
	}
}
