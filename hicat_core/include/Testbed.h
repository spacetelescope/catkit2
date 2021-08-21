#ifndef TESTBED_H
#define TESTBED_H

class Testbed
{
public:
    Testbed();


};

#endif // TESTBED_H

/*
TestbedServer
- Python only
- init(tesbed_server_port)
- starts processes for each requested module
- restarts processes if the module has crashed
- replies to requests of module access (starts them when necessary)
- monitors safety, initiates shutdown (upon request)
- REP socket
- Communicates using simple JSON only, with multiple Testbed objects, no binary data

Testbed
- C++ and Python (separate implementations)
- init(testbed_server_port)
- communicates with TestbedServer to start/retrieve devices
- acts as the device cache
- Also reads and distributes the config file (it gets the config, in json, from the testbed server).
- REQ socket
- Communicates using simple JSON only, with a TestbedServer, no binary data

Module
- C++ with Python wrapper
- REP socket
- Communicates using SerializedMessages with multiple ModuleProxy objects

ModuleProxy
- C++ and Python (separate implementations)
- init(module_port)
- communicates with Module to get/set properties, execute commands and access its datastreams
- obtained from a Testbed
- REQ socket
- Communicates using SerializedMessages with a Module

Each module process is started with:
* a name (corresponding to a section in the config file)
* a module_port
* the testbed_server_port.

*/
