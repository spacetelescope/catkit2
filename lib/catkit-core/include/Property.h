#ifndef PROPERTY_H
#define PROPERTY_H

#include "Serialization.h"

// Base class for all Properties.
class Property
{
public:
	virtual ~Property();

	virtual void Get(SerializedMessage &value);
	virtual void Set(const SerializedMessage &value);
};

// Helper class for simple Properties based on one/two functions.
class PropertyFromFunctions : public Property
{
public:
	typedef std::function<void(SerializedMessage &)> Getter;
	typedef std::function<void(const SerializedMessage &)> Setter;

	PropertyFromFunctions(Getter getter = nullptr, Setter setter = nullptr);

	virtual void Get(SerializedMessage &value);
	virtual void Set(const SerializedMessage &value);

private:
	Getter m_Getter;
	Setter m_Setter;
};

#endif // PROPERTY_H