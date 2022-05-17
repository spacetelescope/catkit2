#ifndef PROPERTY_H
#define PROPERTY_H

#include "Types.h"

#include <string>

class Property
{
public:
	typedef std::function<Value()> Getter;
	typedef std::function<void(const Value &)> Setter;

	Property(std::string name, Getter getter = nullptr, Setter setter = nullptr);

	Value Get();
	void Set(const Value &value);

	std::string GetName();

private:
	std::string m_Name;

	Getter m_Getter;
	Setter m_Setter;
};

#endif // PROPERTY_H
