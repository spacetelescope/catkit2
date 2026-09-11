#include "TestHelpers.h"

#include <vector>

namespace TestHelpers
{
	StressTestParams DefaultStressParams()
	{
		StressTestParams params;
		params.num_threads = 8;
		params.iterations = 1000;
		params.max_item_shift = 5;
		params.max_retained_shift = 7;
		params.alloc_probability = 0.5;
		params.retain_probability = 0.25;
		params.free_probability = 0.66;
		params.transfer_probability = 0.25;
		params.transfer_buffer_size = 128;
		params.data_buffer_size = 1000;
		return params;
	}

	ThreadRNG::ThreadRNG(uint64_t seed)
		: m_Rng(seed),
		  m_Uniform01(0.0, 1.0)
	{}

	bool ThreadRNG::Chance(double p)
	{
		return m_Uniform01(m_Rng) < p;
	}

	size_t ThreadRNG::Pick(size_t max)
	{
		std::uniform_int_distribution<size_t> dist(0, max - 1);
		return dist(m_Rng);
	}

	template<typename Allocator>
	AllocatorStressContext<Allocator>::AllocatorStressContext(
		std::shared_ptr<Allocator> allocator,
		const StressTestParams& params)
		: m_Allocator(std::move(allocator)),
		  m_Params(params),
		  m_TransferBuffer(params.transfer_buffer_size)
	{
		for (size_t i = 0; i < m_TransferBuffer.size(); ++i)
		{
			m_TransferBuffer[i].store(AllocatorTraits<Allocator>::INVALID_HANDLE, std::memory_order_relaxed);
		}
	}

	template<typename Allocator>
	void AllocatorStressContext<Allocator>::RunThread(intptr_t tid)
	{
		using Traits = AllocatorTraits<Allocator>;

		ThreadRNG rng(static_cast<uint64_t>(tid + 1) * 43);

		size_t allocs = m_Params.iterations;
		size_t retain = allocs / 2;

		std::vector<Handle> data;
		data.reserve(m_Params.data_buffer_size);
		size_t data_top = 0;

		std::vector<Handle> retained;
		retained.reserve(retain);
		size_t retain_top = 0;

		while (allocs > 0 || retain > 0)
		{
			if (retain == 0 || (rng.Chance(m_Params.alloc_probability) && allocs > 0))
			{
				allocs--;

				size_t size = 1ULL << rng.Pick(m_Params.max_item_shift);
				Handle handle = Traits::Allocate(m_Allocator, size);

				if (handle != Traits::INVALID_HANDLE)
				{
					if (data_top >= data.size())
					{
						data.resize(data.size() + 1000);
					}
					data[data_top++] = handle;
					m_TotalAllocations.fetch_add(1, std::memory_order_relaxed);
				}
				else
				{
					m_FailedAllocations.fetch_add(1, std::memory_order_relaxed);
				}
			}
			else
			{
				size_t size = 1ULL << rng.Pick(m_Params.max_retained_shift);
				Handle handle = Traits::Allocate(m_Allocator, size);

				if (handle != Traits::INVALID_HANDLE)
				{
					if (retain_top >= retained.size())
					{
						retained.resize(retained.size() + 100);
					}
					retained[retain_top++] = handle;
					m_TotalAllocations.fetch_add(1, std::memory_order_relaxed);
				}
				else
				{
					m_FailedAllocations.fetch_add(1, std::memory_order_relaxed);
				}
				retain--;
			}

			if (rng.Chance(m_Params.free_probability) && data_top > 0)
			{
				size_t idx = rng.Pick(data_top);
				Handle handle = data[idx];

				if (handle != Traits::INVALID_HANDLE)
				{
					Traits::Release(m_Allocator, handle);
					m_TotalReleases.fetch_add(1, std::memory_order_relaxed);
					data[idx] = Traits::INVALID_HANDLE;
				}
			}

			if (rng.Chance(m_Params.transfer_probability) && data_top > 0)
			{
				size_t data_idx = rng.Pick(data_top);
				size_t transfer_idx = rng.Pick(m_Params.transfer_buffer_size);

				Handle our_handle = data[data_idx];
				Handle their_handle = m_TransferBuffer[transfer_idx].exchange(our_handle, std::memory_order_relaxed);

				if (their_handle != Traits::INVALID_HANDLE)
				{
					Traits::Release(m_Allocator, their_handle);
					m_TotalReleases.fetch_add(1, std::memory_order_relaxed);
					data[data_idx] = Traits::INVALID_HANDLE;
				}
			}
		}

		for (size_t i = 0; i < retain_top; i++)
		{
			if (retained[i] != Traits::INVALID_HANDLE)
			{
				Traits::Release(m_Allocator, retained[i]);
				m_TotalReleases.fetch_add(1, std::memory_order_relaxed);
			}
		}

		for (size_t i = 0; i < data_top; i++)
		{
			if (data[i] != Traits::INVALID_HANDLE)
			{
				Traits::Release(m_Allocator, data[i]);
				m_TotalReleases.fetch_add(1, std::memory_order_relaxed);
			}
		}
	}

	template class AllocatorStressContext<PoolAllocator>;
	template class AllocatorStressContext<BuddyAllocator>;
	template class AllocatorStressContext<HybridPoolAllocator>;
}
