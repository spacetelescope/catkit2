#ifndef CUDA_SHARED_MEMORY_H
#define CUDA_SHARED_MEMORY_H

#include <memory>

#ifdef HAVE_CUDA
#include <cuda_runtime_api.h>
typedef cudaIpcMemHandle_t CudaIpcHandle;
#else
// CUDA cudaIpcMemHandle_t is a struct of 64 bytes.
typedef char CudaIpcHandle[64];
#endif

class CudaSharedMemory
{
private:
    CudaSharedMemory(const CudaIpcHandle &ipc_handle, void *device_pointer=nullptr);

public:
    ~CudaSharedMemory();

    static std::shared_ptr<CudaSharedMemory> Create(size_t num_bytes_in_buffer);
    static std::shared_ptr<CudaSharedMemory> Open(const CudaIpcHandle &ipc_handle);

    void *GetAddress();
};

#endif // CUDA_SHARED_MEMORY_H
