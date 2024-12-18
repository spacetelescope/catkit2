#ifndef UUID_GENERATOR_H
#define UUID_GENERATOR_H

#include <random>

using Uuid = char[16];

class UuidGenerator
{
public:
	UuidGenerator();

	void Generate(Uuid &uuid);

private:
	std::mt19937_64 m_Engines[2];
};

#endif // UUID_GENERATOR_H
