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

void LogListener::AddLogEntry(const LogEntry &entry)
{
}

vector<shared_ptr<LogListener>> log_listeners;

void SubscribeToLog(shared_ptr<LogListener> listener)
{
	log_listeners.push_back(listener);
}

void UnsubscribeToLog(shared_ptr<LogListener> listener)
{
	auto it = find(log_listeners.begin(), log_listeners.end(), listener);
	if (it != log_listeners.end())
		log_listeners.erase(it);
}

void SubmitLogEntry(std::string filename, unsigned int line, std::string function, Severity severity, std::string message)
{
	auto entry = LogEntry(filename, line, function, severity, message, GetTimeStamp());
	for (auto i : log_listeners)
	{
		i->AddLogEntry(entry);
	}
}
