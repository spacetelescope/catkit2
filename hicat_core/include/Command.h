#ifndef COMMAND_H
#define COMMAND_H

#include <functional>
#include <string>

#include "Serialization.h"

class Command
{
public:
	typedef std::function<void(const SerializedMessage &arguments, SerializedMessage &result)> CommandFunction;

	Command(std::string name, CommandFunction command);
	virtual ~Command();

	void Execute(const SerializedMessage &arguments, SerializedMessage &result);

	std::string GetName();

protected:
	std::string m_Name;

	CommandFunction m_CommandFunction;
};

#endif // COMMAND_H
