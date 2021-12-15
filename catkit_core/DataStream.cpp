#include "DataStream.h"

//#include "Log.h"
#include "TimeStamp.h"

#include <algorithm>
#include <iostream>

using namespace std;

std::string MakeStreamId(const std::string &stream_name, const std::string &service_name, int pid)
{
	return service_name + "." + std::to_string(pid) + "." + stream_name;
}

void CalculateBufferSize(DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer,
	size_t &num_elements_per_frame, size_t &num_bytes_per_frame, size_t &num_bytes_in_buffer)
{
	if (dimensions.size() > 4)
		throw std::runtime_error("Maximum dimensionality of the frames is 4.");

	if (num_frames_in_buffer > MAX_NUM_FRAMES_IN_BUFFER)
		throw std::runtime_error("Too many frames requested for the buffer.");

	num_elements_per_frame = 1;
	for (auto d : dimensions)
	{
		num_elements_per_frame *= d;
	}

	num_bytes_per_frame = num_elements_per_frame * GetSizeOfDataType(type);
	num_bytes_in_buffer = sizeof(DataStreamHeader) + num_bytes_per_frame * num_frames_in_buffer;
}

const char *GetDataTypeAsString(DataType type)
{
	switch (type)
	{
		case DataType::DT_UINT8:
			return "B";
		case DataType::DT_UINT16:
			return "H";
		case DataType::DT_UINT32:
			return "L";
		case DataType::DT_UINT64:
			return "Q";
		case DataType::DT_INT8:
			return "b";
		case DataType::DT_INT16:
			return "h";
		case DataType::DT_INT32:
			return "l";
		case DataType::DT_INT64:
			return "q";
		case DataType::DT_FLOAT32:
			return "f";
		case DataType::DT_FLOAT64:
			return "d";
		case DataType::DT_COMPLEX64:
			return "zf";
		case DataType::DT_COMPLEX128:
			return "zd";
		default:
			return "unknown";
	}
}

DataType GetDataTypeFromString(const char *type)
{
	return GetDataTypeFromString(string(type));
}

DataType GetDataTypeFromString(string type)
{
	if (type == "B" || type == "uint8")
		return DataType::DT_UINT8;
	if (type == "H" || type == "uint16")
		return DataType::DT_UINT16;
	if (type == "L" || type == "uin32")
		return DataType::DT_UINT32;
	if (type == "Q" || type == "uint64")
		return DataType::DT_UINT64;
	if (type == "b" || type == "int8")
		return DataType::DT_INT8;
	if (type == "h" || type == "int16")
		return DataType::DT_INT16;
	if (type == "l" || type == "int32")
		return DataType::DT_INT32;
	if (type == "q" || type == "int64")
		return DataType::DT_INT64;
	if (type == "f" || type == "float32")
		return DataType::DT_FLOAT32;
	if (type == "d" || type == "float64")
		return DataType::DT_FLOAT64;
	if (type == "zf" || type == "complex64")
		return DataType::DT_COMPLEX64;
	if (type == "zd" || type == "complex128")
		return DataType::DT_COMPLEX128;
	return DataType::DT_UNKNOWN;
}

size_t GetSizeOfDataType(DataType type)
{
	switch (type)
	{
		case DataType::DT_UINT8:
		case DataType::DT_INT8:
			return 1;
		case DataType::DT_UINT16:
		case DataType::DT_INT16:
			return 2;
		case DataType::DT_UINT32:
		case DataType::DT_INT32:
		case DataType::DT_FLOAT32:
			return 4;
		case DataType::DT_UINT64:
		case DataType::DT_INT64:
		case DataType::DT_FLOAT64:
		case DataType::DT_COMPLEX64:
			return 8;
		case DataType::DT_COMPLEX128:
			return 16;
		default:
			return 0;
	}
}

size_t DataFrame::GetNumElements()
{
	return m_Dimensions[0] * m_Dimensions[1] * m_Dimensions[2] * m_Dimensions[3];
}

size_t DataFrame::GetSizeInBytes()
{
	return GetNumElements() * GetSizeOfDataType(m_DataType);
}

DataStream::DataStream(HANDLE file_mapping, HANDLE frame_written)
	: m_FileMapping(file_mapping), m_FrameWritten(frame_written),
	m_Header(nullptr), m_Buffer(nullptr),
	m_NextFrameIdToRead(0),
	m_BufferHandlingMode(BM_NEWEST_ONLY)
{
	void *buffer = MapViewOfFile(m_FileMapping, FILE_MAP_ALL_ACCESS, 0, 0, 0);

	if (!buffer)
	{
		// Something went wrong with the memory mapping.
		return;
	}

	m_Header = (DataStreamHeader *) buffer;
	m_Buffer = ((char *)buffer) + sizeof(DataStreamHeader);
}

DataStream::~DataStream()
{
	CloseHandle(m_FrameWritten);

	UnmapViewOfFile(m_Header);
	CloseHandle(m_FileMapping);
}

std::shared_ptr<DataStream> DataStream::Create(const std::string &stream_name, const std::string &service_name, DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer)
{
	size_t num_elements_per_frame, num_bytes_per_frame, num_bytes_in_buffer;

	CalculateBufferSize(type, dimensions, num_frames_in_buffer,
		num_elements_per_frame, num_bytes_per_frame, num_bytes_in_buffer);

	auto stream_id = MakeStreamId(stream_name, service_name, GetCurrentProcessId());

	HANDLE file_mapping = CreateFileMapping(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, (DWORD) num_bytes_in_buffer, (stream_id + ".mem").c_str());

	if (file_mapping == NULL)
		throw std::runtime_error("Something went wrong while creating shared memory.");

	HANDLE semaphore = CreateSemaphore(NULL, 0, 9999, (stream_id + ".sem").c_str());

	if (semaphore == NULL)
	{
		CloseHandle(file_mapping);

		throw std::runtime_error("Something went wrong while creating semaphore.");
	}

	auto data_stream = std::unique_ptr<DataStream>(new DataStream(file_mapping, semaphore));
	auto header = data_stream->m_Header;

	strcpy(header->m_Version, CURRENT_DATASTREAM_VERSION);

	strcpy(header->m_StreamName, stream_name.c_str());
	strcpy(header->m_StreamId, stream_id.c_str());
	header->m_TimeCreated = GetTimeStamp();
	header->m_CreatorPID = GetCurrentProcessId();

	header->m_FirstId = 0;
	header->m_LastId = 0;
	header->m_NextRequestId = 0;
	header->m_NumReadersWaiting = 0;

	header->m_NumBytesInBuffer = num_bytes_in_buffer;

	data_stream->UpdateParameters(type, dimensions, num_frames_in_buffer);

	return data_stream;
}

std::shared_ptr<DataStream> DataStream::Create(const std::string &stream_name, const std::string &service_name, DataType type, std::initializer_list<size_t> dimensions, size_t num_frames_in_buffer)
{
	return Create(stream_name, service_name, type, std::vector<size_t>{dimensions}, num_frames_in_buffer);
}

std::shared_ptr<DataStream> DataStream::Open(const std::string &stream_id)
{
	HANDLE file_mapping = OpenFileMapping(FILE_MAP_ALL_ACCESS, FALSE, (stream_id + ".mem").c_str());

	if (file_mapping == NULL)
		throw std::runtime_error("Something went wrong while opening shared memory.");

	HANDLE semaphore = OpenSemaphore(SEMAPHORE_ALL_ACCESS, FALSE, (stream_id + ".sem").c_str());

	if (semaphore == NULL)
	{
		CloseHandle(file_mapping);

		throw std::runtime_error("Something went wrong while opening semaphore.");
	}

	auto data_stream = std::unique_ptr<DataStream>(new DataStream(file_mapping, semaphore));

	if (strcmp(data_stream->m_Header->m_Version, CURRENT_DATASTREAM_VERSION) != 0)
	{
		// DataStreams were made with different versions.
		return nullptr;
	}

	// Don't read frames that already are available at the time the data stream is opened.
	data_stream->m_NextFrameIdToRead = data_stream->m_Header->m_LastId;

	return data_stream;
}

DataFrame DataStream::RequestNewFrame()
{
	// If the frame buffer is full: make oldest frame unavailable.
	if ((m_Header->m_LastId - m_Header->m_FirstId) == m_Header->m_NumFramesInBuffer)
		m_Header->m_FirstId++;

	size_t new_frame_id = m_Header->m_NextRequestId++;

	size_t offset = (new_frame_id % m_Header->m_NumFramesInBuffer) * m_Header->m_NumBytesPerFrame;

	// Build a DataFrame and return it.
	DataFrame frame;
	frame.m_Id = new_frame_id;
	frame.m_TimeStamp = 0;
	frame.m_DataType = m_Header->m_DataType;
	frame.m_NumDimensions = m_Header->m_NumDimensions;
	copy(m_Header->m_Dimensions, m_Header->m_Dimensions + 4, frame.m_Dimensions);
	frame.m_Data = m_Buffer + offset;

	return frame;
}

void DataStream::SubmitFrame(size_t id)
{
	// Save timing information to frame metadata.
	DataFrameMetadata *meta = m_Header->m_FrameMetadata + (id % m_Header->m_NumFramesInBuffer);
	meta->m_TimeStamp = GetTimeStamp();

	// Make frame available:
	// Use a do-while loop to ensure we are never decrementing the last id.
	size_t last_id;
	do
	{
		last_id = m_Header->m_LastId;

		if (last_id >= id + 1)
			break;
	} while (!m_Header->m_LastId.compare_exchange_strong(last_id, id + 1));

	// Notify waiting processes.
	long num_readers_waiting = m_Header->m_NumReadersWaiting.exchange(0);

	if (num_readers_waiting > 0)
		ReleaseSemaphore(m_FrameWritten, (LONG) num_readers_waiting, NULL);
}

void DataStream::SubmitData(void *data)
{
	DataFrame frame = RequestNewFrame();

	char *source = (char *) data;
	std::copy(source, source + frame.GetSizeInBytes(), frame.m_Data);

	SubmitFrame(frame.m_Id);
}

std::vector<size_t> DataStream::GetDimensions()
{
	return std::vector<size_t>(m_Header->m_Dimensions, m_Header->m_Dimensions + m_Header->m_NumDimensions);
}

DataType DataStream::GetDataType()
{
	return m_Header->m_DataType;
}

size_t DataStream::GetNumFramesInBuffer()
{
	return m_Header->m_NumFramesInBuffer;
}

size_t DataStream::GetNumElementsPerFrame()
{
	return m_Header->m_NumElementsPerFrame;
}

size_t DataStream::GetNumDimensions()
{
	return m_Header->m_NumDimensions;
}

void DataStream::SetDataType(DataType type)
{
	UpdateParameters(type, GetDimensions(), GetNumFramesInBuffer());
}

void DataStream::SetDimensions(std::vector<size_t> dimensions)
{
	UpdateParameters(GetDataType(), dimensions, GetNumFramesInBuffer());
}

void DataStream::SetNumFramesInBuffer(size_t num_frames_in_buffer)
{
	UpdateParameters(GetDataType(), GetDimensions(), num_frames_in_buffer);
}

void DataStream::UpdateParameters(DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer)
{
	size_t num_elements_per_frame, num_bytes_per_frame, num_bytes_in_buffer;

	CalculateBufferSize(type, dimensions, num_frames_in_buffer,
		num_elements_per_frame, num_bytes_per_frame, num_bytes_in_buffer);

	if (num_bytes_in_buffer > m_Header->m_NumBytesInBuffer)
		throw std::runtime_error("New parameters would exceed the allocated shared memory buffer size.");

	// Make all frames unavailable.
	m_Header->m_FirstId = m_Header->m_LastId.load();

	// Set the parameters in the header.
	m_Header->m_DataType = type;
	m_Header->m_NumDimensions = dimensions.size();
	size_t *dims = m_Header->m_Dimensions;
	fill(dims, dims + 4, 1);
	copy(dimensions.begin(), dimensions.end(), dims);

	m_Header->m_NumElementsPerFrame = num_elements_per_frame;
	m_Header->m_NumBytesPerFrame = num_bytes_per_frame;
	m_Header->m_NumFramesInBuffer = num_frames_in_buffer;
}

std::string DataStream::GetVersion()
{
	return m_Header->m_Version;
}

std::string DataStream::GetStreamName()
{
	return m_Header->m_StreamName;
}

std::string DataStream::GetStreamId()
{
	return m_Header->m_StreamId;
}

std::uint64_t DataStream::GetTimeCreated()
{
	return m_Header->m_TimeCreated;
}

unsigned long DataStream::GetCreatorPID()
{
	return m_Header->m_CreatorPID;
}

DataFrame DataStream::GetFrame(size_t id, long wait_time_in_ms, void (*error_check)())
{
	DataFrame frame;
	frame.m_Id = 0;

	bool wait = wait_time_in_ms > 0;

	if (!IsFrameAvailable(id))
	{
		if (!WillFrameBeAvailable(id))
			throw std::runtime_error("Frame will never be available anymore.");

		if (!wait)
			throw std::runtime_error("Frame is not available yet.");

		TimeDelta timer;
		DWORD res = WAIT_OBJECT_0;

		while (m_Header->m_LastId <= id)
		{
			if (res == WAIT_OBJECT_0)
				m_Header->m_NumReadersWaiting++;

			// Wait for a maximum of 20ms to perform periodic error checking.
			auto res = WaitForSingleObject(m_FrameWritten, (unsigned long) min(20, wait_time_in_ms));

			if (res == WAIT_TIMEOUT && timer.GetTimeDelta() > (wait_time_in_ms * 0.001))
			{
				m_Header->m_NumReadersWaiting--;
				throw std::runtime_error("Waiting time has expired.");
			}

			if (error_check != nullptr)
			{
				try
				{
					error_check();
				}
				catch (...)
				{
					m_Header->m_NumReadersWaiting--;
					throw;
				}
			}
		}
	}

	size_t offset = (id % m_Header->m_NumFramesInBuffer) * m_Header->m_NumBytesPerFrame;

	// Build a DataFrame and return it.
	frame.m_Id = id;
	frame.m_TimeStamp = m_Header->m_FrameMetadata[id % m_Header->m_NumFramesInBuffer].m_TimeStamp;
	frame.m_DataType = m_Header->m_DataType;
	frame.m_NumDimensions = m_Header->m_NumDimensions;
	copy(m_Header->m_Dimensions, m_Header->m_Dimensions + 4, frame.m_Dimensions);
	frame.m_Data = m_Buffer + offset;

	return frame;
}

DataFrame DataStream::GetNextFrame(long wait_time_in_ms, void (*error_check)())
{
	size_t frame_id = m_NextFrameIdToRead;
	size_t newest_frame_id = GetNewestAvailableFrameId();
	size_t oldest_frame_id = GetOldestAvailableFrameId();

	switch (m_BufferHandlingMode)
	{
		case BM_NEWEST_ONLY:

		// If the frame we are aiming to read is not the newest,
		// return the newest frame instead.
		if (newest_frame_id > frame_id)
			frame_id = newest_frame_id;

		break;

		case BM_OLDEST_FIRST_OVERWRITE:

		// If the frame was discarded already,
		// return the oldest available frame instead.
		if (frame_id < oldest_frame_id)
			frame_id = oldest_frame_id;

		break;
	}

	auto frame = GetFrame(frame_id, wait_time_in_ms, error_check);

	m_NextFrameIdToRead = frame_id + 1;
	return frame;
}

DataFrame DataStream::GetLatestFrame()
{
	if (m_Header->m_LastId == 0)
		throw std::runtime_error("DataStream does not have any frames when trying to get the latest one.");

	return GetFrame(GetNewestAvailableFrameId(), -1);
}

BufferHandlingMode DataStream::GetBufferHandlingMode()
{
	return m_BufferHandlingMode;
}

void DataStream::SetBufferHandlingMode(BufferHandlingMode mode)
{
	m_BufferHandlingMode = mode;
}

bool DataStream::IsFrameAvailable(size_t id)
{
	return (id >= m_Header->m_FirstId) && (id < m_Header->m_LastId);
}

bool DataStream::WillFrameBeAvailable(size_t id)
{
	return id >= m_Header->m_FirstId;
}

size_t DataStream::GetOldestAvailableFrameId()
{
	return m_Header->m_FirstId;
}

size_t DataStream::GetNewestAvailableFrameId()
{
	// Check if any frames are available, and if not, return the first one anyway.
	if (m_Header->m_LastId == 0)
		return 0;

	return m_Header->m_LastId - 1;
}
