#ifndef UUID_GENERATOR_H
#define UUID_GENERATOR_H

#include <random>
#include <string>
#include <array>

struct Uuid
{
	std::array<unsigned char, 16> data;

	static void Generate(Uuid *uuid);

	bool operator==(const Uuid &other) const;
	bool operator!=(const Uuid &other) const;

	std::string to_string() const;
};

#endif // UUID_GENERATOR_H
