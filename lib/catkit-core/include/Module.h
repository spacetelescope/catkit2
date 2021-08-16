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

	Property *GetProperty(const std::string &property_name);
	Command *GetCommand(const std::string &command_name);
	DataStream *GetDataStream(const std::string &stream_name);

protected:
	void RegisterProperty(Property *property);
	void RegisterCommand(Command *command);
	void RegisterDataStream(DataStream *stream);

private:
	void Run();
	void ShutDown();

	void HandleExecuteCommandRequest(const SerializedMessage &request, SerializedMessage &reply);

	void HandleGetPropertyRequest(const SerializedMessage &request, SerializedMessage &reply);
	void HandleSetPropertyRequest(const SerializedMessage &request, SerializedMessage &reply);

	void HandleListAllPropertiesRequest(const SerializedMessage &request, SerializedMessage &reply);
	void HandleListAllCommandsRequest(const SerializedMessage &request, SerializedMessage &reply);
	void HandleListAllDataStreamsRequest(const SerializedMessage &request, SerializedMessage &reply);

	void SendReplyMessage(const std::string &type, const SerializedMessage &message);
	void SendBroadcastMessage(const std::string &type, const SerializedMessage &message);

	zmq::context_t *m_Context;
	zmq::socket_t *m_Shell;
	zmq::socket_t *m_Broadcast;

	std::string m_Name;
	int m_Port;
	bool m_IsRunning;

	std::thread m_MonitoringThread;

	typedef std::function<void(const SerializedMessage &, SerializedMessage &)> MessageHandler;
	std::map<std::string, MessageHandler> m_MessageHandlers;

	std::map<std::string, Property *> m_Properties;
	std::map<std::string, Command *> m_Commands;
	std::map<std::string, DataStream *> m_DataStreams;
};

#endif // MODULE_H
