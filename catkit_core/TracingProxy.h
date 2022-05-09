#ifndef TRACING_PROXY_H
#define TRACING_PROXY_H

#include "TestbedProxy.h"

#include <zmq.hpp>

#include <thread>

class TracingProxy
{
public:
    TracingProxy(std::shared_ptr<TestbedProxy> testbed);
    ~TracingProxy();

    void TraceBegin(std::string func, std::string what);
    void TraceEnd(std::string func);

    void TraceInterval(std::string func, std::string what, uint64_t timestamp_start, uint64_t timestamp_end);

    void TraceCounter(std::string func, double counter);

    void TraceProcessName(std::string process_name);
    void TraceThreadName(std::string thread_name);

private:
    void SendTraceMessage(std::string contents);

    void MessageLoop();
    void ShutDown();

    std::thread m_MessageLoopThread;
    std::atomic_bool m_ShutDown;

    std::queue<std::string> m_TraceMessages;
    std::mutex m_Mutex;
    std::condition_variable m_ConditionVariable;

    std::string m_Host;
    int m_Port;
};

#endif // TRACING_PROXY_H
