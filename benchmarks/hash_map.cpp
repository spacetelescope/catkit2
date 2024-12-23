#include "HashMap.h"
#include "Timing.h"

#include <iostream>

int main(int argc, char **argv)
{
    typedef HashMap<uint16_t, 16384, 13> MyHashMap;

    std::size_t buffer_size = MyHashMap::CalculateBufferSize();
    std::cout << "Buffer size: " << buffer_size << " bytes" << std::endl;
    char *buffer = new char[buffer_size];

    MyHashMap map(buffer);
    map.Initialize();

    std::uint64_t total_time = 0;
    std::size_t N = 5000;

    for (size_t i = 0; i < N; ++i)
    {
        std::string key = "key" + std::to_string(i);

        auto start = GetTimeStamp();
        bool success = map.Insert(key, uint16_t(i));
        auto end = GetTimeStamp();

        if (!success)
        {
            std::cout << "Insertion failed." << std::endl;
        }

        total_time += end - start;
    }

    std::cout << "Insertion time: " << total_time / N << " ns" << std::endl;

    total_time = 0;

    for (size_t i = 0; i < N; ++i)
    {
        std::string key = "key" + std::to_string(i);

        auto start = GetTimeStamp();
        auto *value = map.Find(key);
        auto end = GetTimeStamp();

        if (value == nullptr || *value != i)
        {
            std::cout << "Key not found." << std::endl;
        }

        total_time += end - start;
    }

    std::cout << "Lookup time: " << total_time / N << " ns" << std::endl;

    delete[] buffer;

    return 0;
}
