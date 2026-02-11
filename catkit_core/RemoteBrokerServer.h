#ifndef REMOTE_BROKER_SERVER_H
#define REMOTE_BROKER_SERVER_H

#include "Server.h"
#include "MessageBroker.h"

#include <string>

class RemoteBrokerServer
{
public:
	RemoteBrokerServer(std::shared_ptr<MessageBroker> broker, uint16_t port, int num_workers = 4);
	~RemoteBrokerServer();

	void Start();
	void Stop();

	bool IsRunning() const;

private:
	std::shared_ptr<MessageBroker> m_Broker;
	Server m_Server;

	// Request handlers
	std::string HandlePublish(const std::string& request_data);
	std::string HandleGetNext(const std::string& request_data);
	std::string HandleGetCurrent(const std::string& request_data);
	std::string HandleGetRate(const std::string& request_data);
	std::string HandleListTopics(const std::string& request_data);

	// Serialization helpers
	std::string SerializeMessage(const Message& msg);
	std::optional<Message> DeserializeMessage(const std::string& data);

	// Helper to parse GetNext request
	struct GetNextParams
	{
		std::string topic;
		uint64_t preferred_frame_id;
		MessageSubscriptionMode mode;
		double timeout_seconds;
	};
	GetNextParams ParseGetNextRequest(const std::string& data);
};

#endif // REMOTE_BROKER_SERVER_H
