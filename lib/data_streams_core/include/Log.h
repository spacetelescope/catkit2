#ifndef LOG_H
#define LOG_H

#include <string>
#include <vector>
#include <memory>

#ifndef LOG_LEVEL
	#define LOG_LEVEL 6
#endif

#if LOG_LEVEL > 0
	#define LOG_CRITICAL_ERROR(message) SubmitLogEntry(__FILE__, __LINE__, __func__, S_CRITICAL_ERROR, message)
#else
	#define LOG_CRITICAL_ERROR(message) ((void) 0)
#endif

#if LOG_LEVEL > 1
	#define LOG_ERROR(message) SubmitLogEntry(__FILE__, __LINE__, __func__, S_ERROR, message)
#else
	#define LOG_ERROR(message) ((void) 0)
#endif

#if LOG_LEVEL > 2
	#define LOG_WARNING(message) SubmitLogEntry(__FILE__, __LINE__, __func__, S_WARNING, message)
#else
	#define LOG_WARNING(message) ((void) 0)
#endif

#if LOG_LEVEL > 3
	#define LOG_USER(message) SubmitLogEntry(__FILE__, __LINE__, __func__, S_USER, message)
#else
	#define LOG_USER(message) ((void) 0)
#endif

#if LOG_LEVEL > 4
	#define LOG_INFO(message) SubmitLogEntry(__FILE__, __LINE__, __func__, S_INFO, message)
#else
	#define LOG_INFO(message) ((void) 0)
#endif

#if LOG_LEVEL > 5
	#define LOG_DEBUG(message) SubmitLogEntry(__FILE__, __LINE__, __func__, S_DEBUG, message)
#else
	#define LOG_DEBUG(message) ((void) 0)
#endif

#ifdef NDEBUG
	#define LOG_ASSERT(condition, message) if (!(condition)) LOG_ERROR("Assertion failed: "s + (message))
#else
	#define LOG_ASSERT(condition, message) ((void) 0)
#endif

enum Severity
{
	S_CRITICAL_ERROR,
	S_ERROR,
	S_WARNING,
	S_USER,
	S_INFO,
	S_DEBUG
};

typedef struct LogEntry
{
	std::string filename;
	unsigned int line;
	std::string function;
	Severity severity;
	std::string message;
	std::uint64_t timestamp;
	std::string time;
	
	LogEntry(std::string filename, unsigned int line, std::string function, Severity severity, std::string message, std::uint64_t timestamp);
} LogEntry;

class LogListener
{
public:
	virtual void AddLogEntry(const LogEntry &entry);
};

void SubscribeToLog(std::shared_ptr<LogListener> listener);
void UnsubscribeToLog(std::shared_ptr<LogListener> listener);

void SubmitLogEntry(std::string filename, unsigned int line, std::string function, Severity severity, std::string message);

#endif // LOG_H
