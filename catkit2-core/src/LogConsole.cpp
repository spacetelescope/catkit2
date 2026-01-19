#include "LogConsole.h"

#include <ostream>
#include <iostream>

using namespace std;

enum ColorCode {
	FG_BLACK = 30,
	FG_RED = 31,
	FG_GREEN = 32,
	FG_BROWN = 33,
	FG_BLUE = 34,
	FG_MAGENTA = 35,
	FG_CYAN = 36,
	FG_GRAY = 37,
	FG_DEFAULT = 39,
	BG_RED = 41,
	BG_GREEN = 42,
	BG_YELLOW = 43,
	BG_BLUE = 44,
	BG_MAGENTA = 45,
	BG_CYAN = 46,
	BG_GRAY = 47,
	BG_DEFAULT = 49
};

ostream &operator<<(ostream &os, ColorCode code) {
	return os << "\033[" << static_cast<int>(code) << "m";
}

LogConsole::LogConsole(bool use_color, bool print_context)
	: m_UseColor(use_color), m_PrintContext(print_context)
{
}

void LogConsole::AddLogEntry(const LogEntry &entry)
{
	if (m_PrintContext)
		cout << "Function " << entry.function << " in " << entry.filename << ":" << entry.line << "\n  ";

	if (m_UseColor)
	{
		switch (entry.severity)
		{
		case S_CRITICAL:
			cout << BG_RED;
			break;
		case S_ERROR:
			cout << FG_RED;
			break;
		case S_WARNING:
			cout << FG_BROWN;
			break;
		case S_INFO:
			cout << FG_BLUE;
			break;
		case S_DEBUG:
			cout << FG_GREEN;
			break;
		}
	}

	switch (entry.severity)
	{
	case S_CRITICAL:
		cout << "Critical Error: ";
		break;
	case S_ERROR:
		cout << "Error: ";
		break;
	case S_WARNING:
		cout << "Warning: ";
		break;
	case S_INFO:
		cout << "Info: ";
		break;
	case S_DEBUG:
		cout << "Debug: ";
		break;
	}

	cout << entry.message;

	if (m_UseColor)
		cout << FG_DEFAULT << BG_DEFAULT;

	cout << endl;
}
