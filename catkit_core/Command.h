#ifndef COMMAND_H
#define COMMAND_H

#include "Types.h"

#include <functional>
#include <string>

class Command
{
public:
	typedef std::function<Value(const Dict &arguments)> CommandFunction;

	Command(std::string name, CommandFunction command);
	~Command();

	Value Execute(const Dict &arguments);
	std::string GetName();

private:
	std::string m_Name;
	CommandFunction m_CommandFunction;
};

#endif // COMMAND_H
