#include "DeformableMirrorService.h"

#include "FitsFile.h"

template<typename T>
void CastToBool(T *data, bool *mask, size_t size)
{
	for (size_t i = 0; i < size; ++i)
		mask[i] = data[i] > 0;
}

template<typename T>
void CastToDouble(T *data, double *mask, size_t size)
{
	for (size_t i = 0; i < size; ++i)
		mask[i] = data[i];
}

DeformableMirrorService::DeformableMirrorService(std::string service_type, std::string service_id, int service_port, int testbed_port)
	: Service(service_type, service_id, service_port, testbed_port)
{
	// Get the actuator mask.
	auto config = GetConfig();

	if (!config.contains("device_actuator_mask_fname"))
		throw std::runtime_error("Need to provide a device actuator mask for the deformable mirror.");

	std::string device_actuator_mask_fname = config["device_actuator_mask_fname"].get<std::string>();
	FitsFile actuator_mask_fits = FitsFile(device_actuator_mask_fname);

	m_ActuatorMask = actuator_mask_fits.GetDataCasted<bool>();
	m_Shape = actuator_mask_fits.GetShape();

	// Get the number of actuators.
	m_NumActuators = 0;
	for (auto mask : m_ActuatorMask)
	{
		if (mask)
			++m_NumActuators;
	}

	// Allocate current surface.
	m_CurrentSurface = new double[m_NumActuators];

	// Get channel ids from config.
	for (auto channel_id : config["channel_ids"])
		m_ChannelIds.push_back(channel_id);

	// Create data stream for each channel.
	for (auto channel_id : m_ChannelIds)
	{
		m_ChannelStreams[channel_id] = DataStream::Create(channel_id, GetId(), DataType::DT_FLOAT64, {m_NumActuators}, 20);
	}
}

DeformableMirrorService::~DeformableMirrorService()
{
	delete[] m_CurrentSurface;
}

void DeformableMirrorService::Start()
{
	// Start monitoring channels.
	for (auto channel_id : m_ChannelIds)
	{
		m_ChannelThreads[channel_id] = std::thread(&DeformableMirrorService::MonitorChannel, this, channel_id);
	}
}

void DeformableMirrorService::Main()
{
	while (!ShouldShutDown())
	{
		Sleep(1);
	}
}

void DeformableMirrorService::Stop()
{
	for (auto &thread : m_ChannelThreads)
		thread.second.join();
}

void DeformableMirrorService::MonitorChannel(std::string channel_id)
{
	// Initialize the empty surface.
	double *prev_surface = new double[m_NumActuators];
	for (size_t i = 0; i < m_NumActuators; ++i)
		prev_surface[i] = 0;

	double *diff_surface = new double[m_NumActuators];

	std::shared_ptr<DataStream> stream = m_ChannelStreams[channel_id];

	while (!ShouldShutDown())
	{
		// Wait for the next frame.
		DataFrame frame;

		try
		{
			frame = stream->GetNextFrame(0.01);
		}
		catch (const std::exception &e)
		{
			continue;
		}

		// Compute the differential surface.
		double *new_surface = (double *)frame.GetData();

		for (size_t i = 0; i < m_NumActuators; ++i)
			diff_surface[i] = new_surface[i] - prev_surface[i];

		// Apply the surface delta to the current surface.
		ApplySurfaceDelta(diff_surface);

		// Update the previous surface.
		for (size_t i = 0; i < m_NumActuators; ++i)
			prev_surface[i] = new_surface[i];
	}
}

void DeformableMirrorService::ApplySurfaceDelta(double *surface_delta)
{
	std::lock_guard<std::mutex> lock(m_Mutex);

	// Apply the surface delta to the current surface.
	for (std::size_t i = 0; i < m_NumActuators; ++i)
		m_CurrentSurface[i] += surface_delta[i];

	// Apply the current surface to the deformable mirror.
	ApplySurface(m_CurrentSurface);
}
