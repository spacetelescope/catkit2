#ifndef UUID_GENERATOR_H
#define UUID_GENERATOR_H

#include <random>
#include <string>

struct Uuid {
    unsigned char data[16];

    std::string to_string() const;
};

class UuidGenerator
{
public:
	UuidGenerator();

	void Generate(Uuid *uuid);

private:
	std::mt19937_64 m_Engines[2];
};

#endif // UUID_GENERATOR_H
