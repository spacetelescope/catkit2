#include "Util.h"

#include "Timing.h"

#ifdef _WIN32
	#define WIN32_LEAN_AND_MEAN
	#include <windows.h>
#else
	#include <unistd.h>
#endif // _WIN32

#include <thread>
#include <atomic>
#include <chrono>
#include <algorithm>

int GetProcessId()
{
#ifdef _WIN32
	static int process_id(GetCurrentProcessId());
	return process_id;
#else
	static int process_id(getpid());
	return process_id;
#endif // _WIN32
}

int GetThreadId()
{
	static std::atomic_int next_thread_id(0);
	thread_local static int thread_id(next_thread_id++);

	return thread_id;
}

void Sleep(double sleep_time_in_sec, std::function<bool()> cancellation_callback)
{
	Timer timer;

	while (true)
	{
		double sleep_remaining = sleep_time_in_sec - timer.GetTime();

		// Sleep is over when timer has expired.
		if (sleep_remaining < 0)
			break;

		// Sleep is over when cancellation is requested.
		if (cancellation_callback)
		{
			if (cancellation_callback())
				break;
		}

		// Use brackets around std::min to avoid the macro from windows.h. Sigh.
		double this_sleep_time = (std::min)(double(0.001), sleep_remaining);

		std::this_thread::sleep_for(std::chrono::duration<double>(this_sleep_time));
	}
}

// MurmurHash3 32-bit version
uint32_t murmurhash3(std::string_view key, uint32_t seed)
{
	const uint8_t *data = reinterpret_cast<const uint8_t *>(key.data());
	size_t len = key.size();

	uint32_t h = seed;
	const uint32_t c1 = 0xcc9e2d51;
	const uint32_t c2 = 0x1b873593;

	// Partition in blocks of 4 bytes.
	const size_t nblocks = len / 4;
	const uint32_t* blocks = reinterpret_cast<const uint32_t *>(data);
	for (size_t i = 0; i < nblocks; i++)
	{
		uint32_t k = blocks[i];
		k *= c1;
		k = (k << 15) | (k >> 17);
		k *= c2;

		h ^= k;
		h = (h << 13) | (h >> 19);
		h = h * 5 + 0xe6546b64;
	}

	// Process leftover bytes.
	const uint8_t* tail = data + nblocks * 4;
	uint32_t k1 = 0;

	switch (len & 3)
	{
		case 3:
			k1 ^= tail[2] << 16;
		case 2:
			k1 ^= tail[1] << 8;
		case 1:
			k1 ^= tail[0];
			k1 *= c1;
			k1 = (k1 << 15) | (k1 >> 17);
			k1 *= c2;
			h ^= k1;
		case 0:
			; // Do nothing.
	}

	h ^= len;
	h ^= (h >> 16);
	h *= 0x85ebca6b;
	h ^= (h >> 13);
	h *= 0xc2b2ae35;
	h ^= (h >> 16);

	return h;
}
