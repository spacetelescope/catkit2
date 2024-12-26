#ifndef DEFORMABLE_MIRROR_SERVICE_H
#define DEFORMABLE_MIRROR_SERVICE_H

#include "Service.h"

#include <thread>
#include <mutex>
#include <vector>
#include <map>

class DeformableMirrorService : public Service
{
public:
	DeformableMirrorService(std::string service_type, std::string service_id, int service_port, int testbed_port);
	virtual ~DeformableMirrorService();

	virtual void Start();
	virtual void Main();
	virtual void Stop();

	virtual void ApplySurface(double *surface) = 0;

private:
	void MonitorChannel(std::string channel_id);
	void ApplySurfaceDelta(double *surface_delta);

	std::mutex m_Mutex;
	double *m_CurrentSurface;

	std::vector<bool> m_ActuatorMask;
	std::vector<long> m_Shape;

	std::size_t m_NumActuators;

	std::vector<std::string> m_ChannelIds;
	std::map<std::string, std::thread> m_ChannelThreads;
	std::map<std::string, std::shared_ptr<DataStream>> m_ChannelStreams;

	std::shared_ptr<DataStream> m_TotalSurface;
};

#endif // DEFORMABLE_MIRROR_SERVICE_H
