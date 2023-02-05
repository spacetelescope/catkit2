#ifndef PROPERTY_H
#define PROPERTY_H

#include "Types.h"
#include "DataStream.h"

#include <string>

class Property
{
public:
	typedef std::function<Value()> Getter;
	typedef std::function<void(const Value &)> Setter;

	Property(std::string name, std::shared_ptr<DataStream> stream = nullptr, Getter getter = nullptr, Setter setter = nullptr);

	Value Get();
	void Set(const Value &value);

	std::string GetName();

private:
	std::string m_Name;

	std::shared_ptr<DataStream> m_DataStream;

	Getter m_Getter;
	Setter m_Setter;
};

#endif // PROPERTY_H
