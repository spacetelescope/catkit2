#ifndef UUID_GENERATOR_H
#define UUID_GENERATOR_H

#include <random>

class UuidGenerator
{
public:
	UuidGenerator();

	void GenerateUuid(char *uuid);

private:
	std::mt19937_64 m_Engines[2];
};

#endif // UUID_GENERATOR_H
