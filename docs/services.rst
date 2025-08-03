Services
========

Using a service
---------------

Each service to be used with a testbed needs its own entry in the configuration file ``services.yml``. The config entry
of each service contains two blocks:
    - The **general** setup block
    - The **service-specific** parameter block

The **service-specific parameter block** contains any parameters specific to the service in question

The **general setup block** contains four standardized entries, although not all of them are mandatory:

    - `service_type`
    - `simulated_service_type`
    - `interface`
    - `requires_safety`

An example for such a general setup block, in this case for a camera, is given here:

.. code-block:: YAML

    science_camera:
      service_type: zwo_camera
      simulated_service_type: camera_sim
      interface: camera
      requires_safety: false

      ... # -> specific parameter block

The "name" of a service, in the above example ``science_camera``, is called the ``service_id`` and needs to be unique
across all services. You can have several services use the same ``service_type``, for example all of ``cam1``, ``cam2``
and ``cam3`` using ``service_type: zwo_camera``, but you cannot duplicate service IDs.

You can find example service configurations for each service type in the documentation of the built-in services.

.. note::
    The config keys ``service_type`` and ``requires_safety`` are mandatory, the others are not. You need at least the ``service_type`` when running on hardware, which will be interpreted as the simulated service type when running in simulated mode if the latter hasn’t been set explicitly. The ``interface`` (service proxy) is optional.

The key ``requires_safety`` is a simple boolean that defines whether safety is checked while the service is running, and
whether changes in the safety reports will influence the running service.

The key ``simulated_service_type`` designates which service is used when running the testbed in simulated mode.
Simulated services are also "just" services, implemented in the same way. The crucial difference is that they do not
talk to hardware, instead they talk to the testbed simulator stored in the object ``self.testbed.simulator``. And it is
the simulator that holds an instance of the optical model, saved in ``self.model``.

The key ``interface`` specifies which service proxy is used for a service. Service proxies, and hence this key, are optional.

Launching and Debugging a service
-------------------

Services can be started both by the Testbed upon requests from a TestbedProxy, or manually from the command line. The latter might be advantageous when debugging a service since not all the output of a service is logged. Services can be started manually from the command line using

.. code-block:: python

    python service_type.py --id <service_id> --port <service_port> --tesbed_port <testbed_port>

or

.. code-block:: python

    service_type.exe --id <service_id> --port <service_port> --tesbed_port <testbed_port>

where ``<service_id>``, ``<service_port>`` and ``<testbed_port>`` are replaced by their correct values. Services will
register themselves with the testbed. After registration, you can use them from any TestbedProxy as usual. Note that
even in this case, the ``service_id`` needs to be an entry in the ``services.yml`` configuration file. Otherwise, the
testbed does not have a configuration to provide to the service. Services running in the terminal can be interrupted
using Ctrl+C, or by stopping them using a separate TestbedProxy or ServiceProxy.

File structure and launching
----------------------------

All services have an associated service type. This service type corresponds to a directory, containing all the code used to run that specific service. This can be either a Python script (named ``<service_type>.py``), or a fully compiled binary application (named ``<service_type>.exe`` or ``<service_type>``).

To start a service, you need to know its name. The service name corresponds to an entry in the ``services.yml`` configuration file. Inside this configuration entry, there should be a key ``service_type``. The service type should correspond to a directory in one of the service paths that were passed to the server upon startup.

Service state
-------------

The state of the service is managed by the testbed and the service. It keeps track of what the service is currently doing. The service states are:

* *Closed*. This means that no process for this service is running.
* *Initializing*. This means that a process has been started, but it's still initializing and has not started opening the service yet.
* *Opening*. This means that the ``open()`` method is being called and that connections with hardware or other services are being established.
* *Running*. This means that the service is operational, the ``main()`` functions is being called and that the service is responding to requests on its server.
* *Closing*. This means that the ``close()`` method is being called and that the service is being shut down safely.
* *Unresponsive*. This means that the service process has stopped sending heartbeats, but is still running.
* *Crashed*. This means that the service has crashed. The service may have raised an exception during its operation or may have crashed outright without even shutting down safely.
* *Fail_safe*. This means that the service was safely closed because of safety violations. 

The allowed transitions for a service state are displayed in the below diagram.

.. image:: services_flowchart.png
  :alt: A flow chart for the state of a service.

Handling a service
------------------

You can check the state of a service in the following way:

.. code-block:: python

    print(testbed.science_camera.state)
    print(testbed.science_camera.is_running)  # whether the service state is RUNNING
    print(testbed.science_camera.is_alive)  # whether the service state is any of the alive states (ie. not CRASHED, FAIL_SAFE or CLOSED)

For stopping and starting a service:

.. code-block:: python

    testbed.science_camera.stop()
    testbed.science_camera.start()

A service is also started automatically if you try to access an attribute (property or method or datastream) on a service. If the service has crashed, or is in failsafe mode, then the service will refuse to start by itself or via the service proxy alone. This is to avoid an infinite loop of the service crashing and restarting, which is not what we want. Instead, you can ask the testbed server to start a `CRASHED`/`FAIL_SAFE`/`CLOSED` service:

.. code-block:: python

    testbed.start_service('science_camera')

Creating your own service
-------------------------

