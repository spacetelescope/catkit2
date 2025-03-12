#include "HashMap.h"
#include "Timing.h"

#include <iostream>
#include <cstdint>
#include <string>

int main(int argc, char **argv)
{
    std::size_t buffer_size = HashMap::GetMemorySize(65536, 13, sizeof(std::int16_t));
    std::cout << "Buffer size: " << buffer_size << " bytes" << std::endl;

    char *buffer = new char[buffer_size];
    auto stream = StructStream(buffer);

    auto map = HashMap::Create(stream, 65536, 13, sizeof(std::int16_t));

    std::uint64_t total_time = 0;
    std::size_t N = 5000;

    for (std::int16_t i = 0; i < N; ++i)
    {
        std::string key = "key" + std::to_string(i);

        auto start = GetTimeStamp();
        auto value = map->Insert(key, &i);
        auto end = GetTimeStamp();

        if (value == nullptr)
        {
            std::cout << "Insertion failed." << std::endl;
        }

        total_time += end - start;
    }

    std::cout << "Insertion time: " << total_time / N << " ns" << std::endl;

    total_time = 0;

    for (std::int16_t i = 0; i < N; ++i)
    {
        std::string key = "key" + std::to_string(i);

        auto start = GetTimeStamp();
        auto *value = map->Find(key);
        auto end = GetTimeStamp();

        if (value == nullptr || *((std::uint16_t *)value) != i)
        {
            std::cout << "Key not found." << std::endl;
        }

        total_time += end - start;
    }

    std::cout << "Lookup time: " << total_time / N << " ns" << std::endl;

    delete[] buffer;

    return 0;
}
