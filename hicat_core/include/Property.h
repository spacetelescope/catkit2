#ifndef PROPERTY_H
#define PROPERTY_H

#include <string>

#include <nlohmann/json.hpp>

class Property
{
public:
	typedef std::function<nlohmann::json()> Getter;
	typedef std::function<void(const nlohmann::json &)> Setter;

	Property(std::string name, Getter getter = nullptr, Setter setter = nullptr);

	nlohmann::json Get();
	void Set(const nlohmann::json &value);

	std::string GetName();

private:
	std::string m_Name;

	Getter m_Getter;
	Setter m_Setter;
};

#endif // PROPERTY_H
