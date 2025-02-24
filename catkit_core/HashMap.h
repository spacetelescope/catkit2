#ifndef HASH_MAP_H
#define HASH_MAP_H

#include "Shareable.h"

#include <cstddef>
#include <cstdint>
#include <atomic>
#include <string_view>
#include <algorithm>

// A hash map with the following limitations:
// * entries cannot be removed.
// * key is string type of fixed size.
class HashMap
{
private:
	enum EntryFlags : uint8_t
	{
		UNOCCUPIED = 0,
		INITIALIZING = 1,
		OCCUPIED = 2
	};

	char *m_Data;

	std::size_t m_NumEntries;
	std::size_t m_MaxKeySize;
	std::size_t m_ValueSize;
	std::size_t m_EntrySize;

	std::size_t GetIndex(std::string_view key) const;

	std::string_view GetKey(std::size_t entry) const;
	void SetKey(std::size_t entry, std::string_view key);
	std::atomic<EntryFlags> *GetFlagsRef(std::size_t entry) const;
	void *GetValue(std::size_t entry) const;

public:
	HashMap(void *buffer, std::size_t num_entries, std::size_t max_key_size, std::size_t value_size);

	static std::size_t CalculateBufferSize(std::size_t num_entries, std::size_t max_key_size, std::size_t value_size);

	void Initialize();

	void *Insert(std::string_view key);
	void *Find(std::string_view key) const;
};

#endif // HASH_MAP_H
