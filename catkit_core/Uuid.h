#ifndef UUID_GENERATOR_H
#define UUID_GENERATOR_H

#include <random>
#include <string>

struct Uuid {
    unsigned char data[16];

	static void Generate(Uuid *uuid);

    std::string to_string() const;
};

#endif // UUID_GENERATOR_H
