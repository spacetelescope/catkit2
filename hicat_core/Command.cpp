#include "Command.h"

Command::Command(std::string name, CommandFunction command)
	: m_Name(name), m_CommandFunction(command)
{
}

Command::~Command()
{
}

void Command::Execute(const SerializedMessage &arguments, SerializedMessage &result)
{
	m_CommandFunction(arguments, result);
}

std::string Command::GetName()
{
	return m_Name;
}