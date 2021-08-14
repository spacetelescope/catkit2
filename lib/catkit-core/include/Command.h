#ifndef COMMAND_H
#define COMMAND_H

#include <functional>

#include "Serialization.h"

class Command
{
public:
	typedef std::function<void(const SerializedMessage &arguments, SerializedMessage &result)> CommandFunction;
	
	Command(CommandFunction command);

	void Execute(const SerializedMessage &arguments, SerializedMessage &result);

protected:
	CommandFunction m_CommandFunction;
};

#endif // COMMAND_H