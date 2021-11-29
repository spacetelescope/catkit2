#ifndef COMMAND_H
#define COMMAND_H

#include <functional>
#include <string>

#include <nlohmann/json.hpp>

class Command
{
public:
	typedef std::function<nlohmann::json(const nlohmann::json &arguments)> CommandFunction;

	Command(std::string name, CommandFunction command);
	~Command();

	nlohmann::json Execute(const nlohmann::json &arguments);
	std::string GetName();

private:
	std::string m_Name;
	CommandFunction m_CommandFunction;
};

#endif // COMMAND_H
