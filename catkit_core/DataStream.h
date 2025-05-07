#ifndef DATASTREAM_H
#define DATASTREAM_H

#include <functional>
#include <map>
#include <vector>
#include <climits>
#include <cstdint>
#include <string>

#include "SharedMemory.h"
#include "Event.h"
#include "Tensor.h"
#include "Shareable.h"

const size_t MAX_NUM_FRAMES_IN_BUFFER = 20;
const long INFINITE_WAIT_TIME = LONG_MAX;

struct DataFrameMetadata
{
	std::uint64_t m_TimeStamp;
};

struct DataStreamHeader
{
	std::array<char, 4> m_Version;

	char m_StreamName[256];
	char m_StreamId[256];
	std::uint64_t m_TimeCreated;
	int m_OwnerPID;

	DataType m_DataType;
	size_t m_NumDimensions;
	size_t m_Dimensions[4];

	size_t m_NumElementsPerFrame;
	size_t m_NumBytesPerFrame;

	size_t m_NumBytesInBuffer;

	size_t m_NumFramesInBuffer;
	DataFrameMetadata m_FrameMetadata[MAX_NUM_FRAMES_IN_BUFFER];

	std::atomic_size_t m_FirstId;
	std::atomic_size_t m_LastId;
	std::atomic_size_t m_NextRequestId;

	double m_FrameRateCounter;
};

class DataFrame : public Tensor
{
public:
	size_t m_Id;
	std::uint64_t m_TimeStamp;
};

enum BufferHandlingMode
{
	BM_NEWEST_ONLY,
	BM_OLDEST_FIRST_OVERWRITE
};

class DataStream : public Shareable
{
private:
	DataStream(DataStreamHeader *header, std::shared_ptr<SharedMemory> buffer_shared_memory, std::shared_ptr<SharedMemory> header_shared_memory, std::shared_ptr<Event> event);

public:
	~DataStream();

	static std::shared_ptr<DataStream> Create(std::string_view stream_name, std::string_view service_id, DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer);
	static std::shared_ptr<DataStream> Create(StructStream &stream, std::string_view stream_name, std::string_view service_id, DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer, std::shared_ptr<SharedMemory> header_shared_memory = nullptr);
	static std::shared_ptr<DataStream> Open(StructStream &stream, std::shared_ptr<SharedMemory> header_shared_memory = nullptr);
	static std::shared_ptr<DataStream> Open(std::string_view stream_id);

	DataFrame RequestNewFrame();
	void SubmitFrame(size_t id);
	void SubmitData(const void *data);

	std::vector<size_t> GetDimensions();
	DataType GetDataType();

	size_t GetNumFramesInBuffer();
	size_t GetNumElementsPerFrame();
	size_t GetNumDimensions();

	void SetDataType(DataType type);
	void SetDimensions(std::vector<size_t> dimensions);
	void SetNumFramesInBuffer(size_t num_frames_in_buffer);

	void UpdateParameters(DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer);

	std::string GetVersion();
	std::string GetStreamName();
	std::string GetStreamId();
	std::uint64_t GetTimeCreated();
	int GetOwnerPID();

	DataFrame GetFrame(size_t id, long wait_time_in_ms=INFINITE_WAIT_TIME, void (*error_check)()=nullptr);
	DataFrame GetNextFrame(long wait_time_in_ms=INFINITE_WAIT_TIME, void (*error_check)()=nullptr);
	DataFrame GetLatestFrame();

	BufferHandlingMode GetBufferHandlingMode();
	void SetBufferHandlingMode(BufferHandlingMode mode);

	bool IsFrameAvailable(size_t id);
	bool WillFrameBeAvailable(size_t id);

	size_t GetNewestAvailableFrameId();
	size_t GetOldestAvailableFrameId();

	double GetFrameRate();

	ShareableType GetType() const override;

private:
	DataStreamHeader *m_Header;
	char *m_Buffer;

	std::shared_ptr<Event> m_Event;

	size_t m_NextFrameIdToRead;
	BufferHandlingMode m_BufferHandlingMode;

	std::shared_ptr<SharedMemory> m_HeaderSharedMemory;
	std::shared_ptr<SharedMemory> m_BufferSharedMemory;
};

#endif // DATASTREAM_H
