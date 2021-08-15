#ifndef PROPERTY_H
#define PROPERTY_H

#include "Serialization.h"

#include <string>

// Base class for all Properties.
class Property
{
public:
	Property(std::string name);
	virtual ~Property();

	virtual void Get(SerializedMessage &value);
	virtual void Set(const SerializedMessage &value);

	std::string GetName();

private:
	std::string m_Name;
};

// Helper class for simple Properties based on one/two functions.
class PropertyFromFunctions : public Property
{
public:
	typedef std::function<void(SerializedMessage &)> Getter;
	typedef std::function<void(const SerializedMessage &)> Setter;

	PropertyFromFunctions(std::string name, Getter getter = nullptr, Setter setter = nullptr);

	virtual void Get(SerializedMessage &value);
	virtual void Set(const SerializedMessage &value);

private:
	Getter m_Getter;
	Setter m_Setter;
};

#endif // PROPERTY_H
