#ifndef UUID_GENERATOR_H
#define UUID_GENERATOR_H

#include <random>
#include <string>
#include <string_view>
#include <array>

struct Uuid
{
	std::array<unsigned char, 16> data;

	static void Generate(Uuid *uuid);
	static Uuid FromString(std::string_view str);

	bool operator==(const Uuid &other) const;
	bool operator!=(const Uuid &other) const;

	std::string to_string() const;
};

#endif // UUID_GENERATOR_H
