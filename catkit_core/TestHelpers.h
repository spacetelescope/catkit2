#ifndef TEST_HELPERS_H
#define TEST_HELPERS_H

#include "PoolAllocator.h"
#include "BuddyAllocator.h"
#include "HybridPoolAllocator.h"

#include <cstdint>
#include <cstddef>
#include <memory>
#include <vector>
#include <atomic>
#include <random>

namespace TestHelpers
{
	struct StressTestParams
	{
		size_t num_threads;
		size_t iterations;
		size_t max_item_shift;
		size_t max_retained_shift;
		double alloc_probability;
		double retain_probability;
		double free_probability;
		double transfer_probability;
		size_t transfer_buffer_size;
		size_t data_buffer_size;
	};

	StressTestParams DefaultStressParams();

	class StressTestContextBase
	{
	public:
		virtual ~StressTestContextBase() = default;
		virtual void RunThread(intptr_t tid) = 0;

		size_t GetTotalAllocations() const { return m_TotalAllocations.load(std::memory_order_relaxed); }
		size_t GetTotalReleases() const { return m_TotalReleases.load(std::memory_order_relaxed); }
		size_t GetFailedAllocations() const { return m_FailedAllocations.load(std::memory_order_relaxed); }
		size_t GetFailedReleases() const { return m_FailedReleases.load(std::memory_order_relaxed); }
		size_t GetDoubleFreeDetected() const { return m_DoubleFreeDetected.load(std::memory_order_relaxed); }
		bool GetSuccess() const { return m_DoubleFreeDetected.load(std::memory_order_relaxed) == 0; }

	protected:
		std::atomic<size_t> m_TotalAllocations{0};
		std::atomic<size_t> m_TotalReleases{0};
		std::atomic<size_t> m_FailedAllocations{0};
		std::atomic<size_t> m_FailedReleases{0};
		std::atomic<size_t> m_DoubleFreeDetected{0};
	};

	template<typename Allocator>
	struct AllocatorTraits;

	template<>
	struct AllocatorTraits<PoolAllocator>
	{
		using Handle = uint32_t;
		static constexpr Handle INVALID_HANDLE = UINT32_MAX;

		static Handle Allocate(std::shared_ptr<PoolAllocator> alloc, size_t)
		{
			return alloc->Allocate();
		}

		static bool Release(std::shared_ptr<PoolAllocator> alloc, Handle handle)
		{
			return alloc->Release(handle);
		}
	};

	template<>
	struct AllocatorTraits<BuddyAllocator>
	{
		using Handle = size_t;
		static constexpr Handle INVALID_HANDLE = 0;

		static Handle Allocate(std::shared_ptr<BuddyAllocator> alloc, size_t size)
		{
			return alloc->Allocate(size);
		}

		static bool Release(std::shared_ptr<BuddyAllocator> alloc, Handle handle)
		{
			return alloc->Release(handle);
		}
	};

	template<>
	struct AllocatorTraits<HybridPoolAllocator>
	{
		using Handle = size_t;
		static constexpr Handle INVALID_HANDLE = 0;

		static Handle Allocate(std::shared_ptr<HybridPoolAllocator> alloc, size_t size)
		{
			return alloc->Allocate(size);
		}

		static bool Release(std::shared_ptr<HybridPoolAllocator> alloc, Handle handle)
		{
			return alloc->Release(handle);
		}
	};

	class ThreadRNG
	{
	public:
		explicit ThreadRNG(uint64_t seed);
		bool Chance(double p);
		size_t Pick(size_t max);

	private:
		std::mt19937_64 m_Rng;
		std::uniform_real_distribution<double> m_Uniform01;
	};

	template<typename Allocator>
	class AllocatorStressContext : public StressTestContextBase
	{
	public:
		using Handle = typename AllocatorTraits<Allocator>::Handle;

		AllocatorStressContext(std::shared_ptr<Allocator> allocator, const StressTestParams& params);
		void RunThread(intptr_t tid) override;

	private:
		std::shared_ptr<Allocator> m_Allocator;
		StressTestParams m_Params;
		std::vector<std::atomic<Handle>> m_TransferBuffer;
	};

	using PoolAllocatorStressContext = AllocatorStressContext<PoolAllocator>;
	using BuddyAllocatorStressContext = AllocatorStressContext<BuddyAllocator>;
	using HybridPoolAllocatorStressContext = AllocatorStressContext<HybridPoolAllocator>;
}

#endif // TEST_HELPERS_H
