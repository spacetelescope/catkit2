#ifndef MODULE_H
#define MODULE_H

#include <zmq.hpp>

#include <memory>
#include <vector>
#include <string>
#include <map>
#include <thread>

#include "Serialization.h"
#include "Property.h"
#include "DataStream.h"
#include "Command.h"

class Module
{
public:
	Module(std::string name, int port);
	virtual ~Module();

	void Run();

	std::string GetName();

	virtual void MainThread();
	virtual void ShutDown();

	std::shared_ptr<Property> GetProperty(const std::string &property_name);
	std::shared_ptr<Command> GetCommand(const std::string &command_name);
	std::shared_ptr<DataStream> GetDataStream(const std::string &stream_name);

protected:
	void RegisterProperty(std::shared_ptr<Property> property);
	void RegisterCommand(std::shared_ptr<Command> command);
	void RegisterDataStream(std::shared_ptr<DataStream> stream);

private:
	void HandleExecuteCommandRequest(const SerializedMessage &request, SerializedMessage &reply);

	void HandleGetPropertyRequest(const SerializedMessage &request, SerializedMessage &reply);
	void HandleSetPropertyRequest(const SerializedMessage &request, SerializedMessage &reply);

	void HandleListAllPropertiesRequest(const SerializedMessage &request, SerializedMessage &reply);
	void HandleListAllCommandsRequest(const SerializedMessage &request, SerializedMessage &reply);
	void HandleListAllDataStreamsRequest(const SerializedMessage &request, SerializedMessage &reply);

	void HandleShutdownRequest(const SerializedMessage &request, SerializedMessage &reply);

	void SendReplyMessage(const std::string &type, const SerializedMessage &message);
	void SendBroadcastMessage(const std::string &type, const SerializedMessage &message);

	zmq::context_t *m_Context;
	zmq::socket_t *m_Shell;
	zmq::socket_t *m_Broadcast;

	std::string m_Name;
	int m_Port;
	bool m_IsRunning;

	std::thread m_MainThread;

	typedef std::function<void(const SerializedMessage &, SerializedMessage &)> MessageHandler;
	std::map<std::string, MessageHandler> m_MessageHandlers;

	std::map<std::string, std::shared_ptr<Property>> m_Properties;
	std::map<std::string, std::shared_ptr<Command>> m_Commands;
	std::map<std::string, std::shared_ptr<DataStream>> m_DataStreams;
};

#endif // MODULE_H
