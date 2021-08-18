#ifndef PROPERTY_H
#define PROPERTY_H

#include "Serialization.h"

#include <string>

class Property
{
public:
	typedef std::function<void(SerializedMessage &)> Getter;
	typedef std::function<void(const SerializedMessage &)> Setter;

	Property(std::string name, Getter getter = nullptr, Setter setter = nullptr);
	virtual ~Property();

	virtual void Get(SerializedMessage &value);
	virtual void Set(const SerializedMessage &value);

	std::string GetName();

private:
	std::string m_Name;

	Getter m_Getter;
	Setter m_Setter;
};

#endif // PROPERTY_H
