#ifndef LOGCONSOLE_H
#define LOGCONSOLE_H

#include "Log.h"

class LogConsole : public LogListener
{
public:
	LogConsole(bool use_color = true, bool print_context = true);

	void AddLogEntry(const LogEntry &entry);

private:
	bool m_UseColor;
	bool m_PrintContext;
};

#endif // LOGCONSOLE_H