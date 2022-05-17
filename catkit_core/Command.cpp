#include "Command.h"

Command::Command(std::string name, CommandFunction command)
	: m_Name(name), m_CommandFunction(command)
{
}

Command::~Command()
{
}

Value Command::Execute(const Dict &arguments)
{
	return m_CommandFunction(arguments);
}

std::string Command::GetName()
{
	return m_Name;
}
