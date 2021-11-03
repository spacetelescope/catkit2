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
	log_listeners.push_back(this);
}

LogListener::~LogListener()
{
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
