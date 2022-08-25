Configuration
=============

Overview
--------

All configuration files are read in by the testbed server upon startup. The testbed state is the authorative representation of a configuration and all systems refer to this authorative copy to receive their relevant portion of the configuration. The configuration is a nested key-value pairs and arrays, similar to JSON. This is no coincidence as JSON is used as the underlying format for distribution of the configuration from the server to services or clients.

The configuration files themselves live as YAML files spread out over a number of directories. These directories are given as an ordered list on server startup, with directories later in the list overwriting individual settings earlier on the list. This allows the user to locally overwrite configurations made by earlier configuration directories. This behaviour is akin to configuration layering.

Each individual configuration YAML file gets its own section in the final configuration dictionary, named after the filename of the YAML file. Section names can be any arbitrary string (as allowed within YAML/JSON). Several section names are special and are used for testbed server operation.

Comments are allowed in YAML files, and start with ``#``. Comments are not available from services or clients, and only appear in the original YAML files.

Path names can be both relative or absolute paths. You can prepend relative paths with a ``!path`` directive to resolve the path relative to the directory of the YAML configuration file. An example:

.. code-block:: YAML

    gain_map_fname: !path ../data/boston/gain_map_140V_2020-03-02T16-29-41.fits
    ffmpeg_path: "C:/ffmpeg/bin/ffmpeg.exe"

Of course, relative paths are prefered due to their compatibility on the computers of other users of the testbed.

Special sections
-----------------

Several sections are used internally by the testbed service and simulator. These are:

- ``services.yml``. This section describes all information and accompanying configuration for all services, so that the server can start them. This information may include ip addresses, motor names, default camera subarrays, serial numbers, etc... Anything that can be kept in a JSON format can be put in the configuration.

- ``testbed.yaml``. This section defines all parameters for operation of the testbed server. This includes, among other things, the default port number, the paths where service types can be found, and directory paths for output of experiment data. Additionally, this is used to signify the service types of the simulator and the testbed safety services.

- ``simulator.yml``. This special directory is used by the simulator and typically contains all parameters used to match testbed hardware with the simulator (eg. optical magnifications, coronagraph mask parameters, inclinations of optical elements, camera pixel sizes and focal lengths of mirrors and lenses). This provides a clear separation between hardware and simulator.

Distribution
------------

The full configuration, including all sections, is available from any testbed client.

.. code-block:: Python

    testbed = TestbedProxy('127.0.0.1', 8080)
    print(testbed.configuration)
    # Prints {'services': ['boston_dm': ....]}

Whenever a service starts, it receives its own configuration from the server as part of the connection handshake. It therefore has no access to any configuration values from other services. This is an intentional decision to make it harder to use configuration values defined outside of your own service. If access to those is required (again, not recommended), a service can create its own testbed client to obtain it.

.. code-block:: Python

    class OwnService(Service):
        def __init__(self, ...):
            ...

        def func(self):
            print(self.config)
            # Prints only the configuration for our service

            testbed = TestbedProxy('127.0.0.1', self.server_port)
            print(testbed.config)
            # Prints the whole configuration.

As the configuration files are distributed over a number of directories, it is strongly recommended that no process obtains the testbed configuration directly from those files, rather than from the testbed server.
