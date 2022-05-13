#ifndef TYPES_H
#define TYPES_H

#include <list>
#include <map>
#include <variant>
#include <string>

class Value;

typedef std::list<Value> List;
typedef std::map<std::string, Value> Dict;

class NoneValue
{
};

class Value : public std::variant<
    NoneValue,
    double,
    std::string,
    bool,
    Dict,
    List>
{
};

#endif // TYPES_H
