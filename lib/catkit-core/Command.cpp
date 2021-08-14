#include "Command.h"

Command::Command(CommandFunction command)
	: m_CommandFunction(command)
{
}

void Command::Execute(const SerializedMessage &arguments, SerializedMessage &result)
{
	m_CommandFunction(arguments, result);
}