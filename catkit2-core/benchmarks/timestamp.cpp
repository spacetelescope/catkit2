#include <iostream>

#include "Timing.h"

const size_t NUM_ITERATIONS = 100000000;

int main(int argc, char *argv[])
{
    auto start = GetTimeStamp();

    for (size_t i = 0; i < NUM_ITERATIONS; ++i)
    {
        GetTimeStamp();
    }

    auto end = GetTimeStamp();

    std::cout << double(end - start) / NUM_ITERATIONS << " ns per timestamp" << std::endl;

	return 0;
}
