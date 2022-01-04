Services
========

File structure and launching
----------------------------

All services have an associated service type. This service type corresponds to a directory, containing all the code used to run that specific service. This can be either a Python script (named ``<service_type>.py``), or a fully compiled binary application (named ``<service_type>.exe`` or ``<service_type>``).



To start a service, you need to know its name. The service name corresponds to an entry in the ``services.yml`` configuration file. Inside this configuration entry, there should be a key ``service_type``. The service type should correspond to a directory in one of the service paths that were passed to the server upon startup.

Creating your own service
-------------------------

Debugging a service
-------------------
