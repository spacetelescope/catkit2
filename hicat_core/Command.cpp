#include "Command.h"

using json = nlohmann::json;

Command::Command(std::string name, CommandFunction command)
	: m_Name(name), m_CommandFunction(command)
{
}

Command::~Command()
{
}

json Command::Execute(const json &arguments)
{
	return m_CommandFunction(arguments);
}

std::string Command::GetName()
{
	return m_Name;
}
