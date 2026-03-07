Configuration
=============

Overview
--------

Configuration files are read by the testbed server upon startup. The testbed state serves as the authoritative representation of the configuration, and all systems reference this authoritative copy to receive their relevant portions. The configuration consists of nested key-value pairs and lists, similar to JSON. This similarity is not surprising because JSON serves as the underlying format for distributing the configuration from the server to services and clients.

Configuration files are stored as YAML files across multiple directories. These directories are provided as an ordered list during server startup, with directories later in the list overriding settings from earlier directories. This enables local customization of configurations through a layering mechanism.

Each YAML configuration file becomes a section in the final configuration dictionary, named after the filename. Section names can be any valid YAML/JSON string. Several section names have special significance for testbed server operation.

YAML files support comments starting with ``#``. Comments exist only in the YAML files and are not available to services or clients.

Path Handling
-------------

Paths can be either relative or absolute. Relative paths may be prefixed with ``!path`` to resolve them relative to the YAML file's directory:

.. code-block:: yaml

    gain_map_fname: !path ../data/boston/gain_map_140V_2020-03-02T16-29-41.fits
    ffmpeg_path: "C:/ffmpeg/bin/ffmpeg.exe"

Relative paths are preferred for cross-platform compatibility.

Special Sections
----------------

Several sections are reserved for internal use by the testbed service and simulator:

services.yml
~~~~~~~~~~~~

Contains information and configuration for all services, enabling the server to start them. This includes IP addresses, motor names, default camera subarrays, serial numbers, and any other JSON-serializable data.

testbed.yaml
~~~~~~~~~~~~

Defines parameters for testbed server operation, including:

* Default port number
* Service type search paths
* Output directory paths for experiment data
* Service types for the simulator and testbed safety services

simulator.yml
~~~~~~~~~~~~~

Contains simulator-specific parameters used to align the simulator with testbed hardware (optical magnifications, coronagraph mask parameters, optical element inclinations, camera pixel sizes, focal lengths of mirrors and lenses). This maintains a clear separation between hardware and simulator configurations.

Distribution
------------

The full configuration is available through any testbed proxy:

.. code-block:: python

    testbed = TestbedProxy('127.0.0.1', 8080)
    print(testbed.configuration)
    # Prints {'services': ['boston_dm': ....]}

When a service starts, it receives its configuration from the server during the connection handshake. The configuration is accessible within the service via ``self.config``. Services have direct access only to their own configuration values. This design prevents accidental dependencies on other services' configurations.

If access to other services' configurations is necessary (not recommended), use the testbed proxy:

.. code-block:: python

    class OwnService(Service):
        def __init__(self, ...):
            ...

        def func(self):
            print(self.config)
            # Prints only the configuration for our service

            print(self.testbed.config)
            # Prints the whole configuration.

Since configuration files are distributed across multiple directories, use testbed proxies rather than reading configuration files directly.
