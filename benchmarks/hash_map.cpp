#include "HashMap.h"
#include "Timing.h"

#include <iostream>

int main(int argc, char **argv)
{
    typedef HashMap<int, 16384, 32> MyHashMap;

    std::size_t buffer_size = MyHashMap::CalculateBufferSize();
    char *buffer = new char[buffer_size];

    MyHashMap map(buffer);
    map.Initialize();

    std::uint64_t total_time = 0;
    std::size_t N = 5000;

    for (size_t i = 0; i < N; ++i)
    {
        std::string key = "key" + std::to_string(i);

        auto start = GetTimeStamp();
        map.Insert(key, i);
        auto end = GetTimeStamp();

        total_time += end - start;
    }

    std::cout << "Insertion time: " << total_time / N << " ns" << std::endl;

    total_time = 0;

    for (size_t i = 0; i < N; ++i)
    {
        std::string key = "key" + std::to_string(i);

        auto start = GetTimeStamp();
        const int *value = map.Find(key);
        auto end = GetTimeStamp();

        total_time += end - start;
    }

    std::cout << "Lookup time: " << total_time / N << " ns" << std::endl;

    delete[] buffer;

    return 0;
}
