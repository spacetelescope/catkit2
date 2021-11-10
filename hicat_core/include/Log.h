#ifndef LOG_H
#define LOG_H

#include <string>
#include <vector>
#include <memory>

#ifndef LOG_LEVEL
	#define LOG_LEVEL 5
#endif

#if LOG_LEVEL > 0
	#define LOG_CRITICAL(message) SubmitLogEntry(__FILE__, __LINE__, __func__, S_CRITICAL, message)
#else
	#define LOG_CRITICAL(message) ((void) 0)
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
	#define LOG_INFO(message) SubmitLogEntry(__FILE__, __LINE__, __func__, S_INFO, message)
#else
	#define LOG_INFO(message) ((void) 0)
#endif

#if LOG_LEVEL > 4
	#define LOG_DEBUG(message) SubmitLogEntry(__FILE__, __LINE__, __func__, S_DEBUG, message)
#else
	#define LOG_DEBUG(message) ((void) 0)
#endif

#ifdef NDEBUG
	#define LOG_ASSERT(condition, message) if (!(condition)) LOG_ERROR("Assertion failed: "s + (message))
#else
	#define LOG_ASSERT(condition, message) ((void) 0)
#endif

// Define the same numeric values of log levels as Python.
enum Severity
{
	S_CRITICAL = 50,
	S_ERROR = 40,
	S_WARNING = 30,
	S_INFO = 20,
	S_DEBUG = 10
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
	LogListener();
	virtual ~LogListener();

	virtual void AddLogEntry(const LogEntry &entry);
};

void SubmitLogEntry(std::string filename, unsigned int line, std::string function, Severity severity, std::string message);
std::string ToString(Severity severity);

#endif // LOG_H
