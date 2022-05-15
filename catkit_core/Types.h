#ifndef TYPES_H
#define TYPES_H

#include "Tensor.h"

#include <list>
#include <map>
#include <variant>
#include <string>

class Value;

class NoneValue
{
};

typedef std::list<Value> List;
typedef std::map<std::string, Value> Dict;

class Value : public std::variant<
	NoneValue,
	double,
	std::string,
	bool,
	Dict,
	List,
	Tensor>
{
};

#endif // TYPES_H
