Getting started with your own testbed
=====================================

``catkit2`` includes a `Cookiecutter  <https://github.com/audreyfeldroy/cookiecutter-pypackage>`__ template that
generates a starter catkit2-based testbed repository from the command line. This provides a starting point for building
your own testbed. Cookiecutter creates the basic project structure automatically, including configuration files,
installation metadata, a ``pyproject.toml``, template documentation, and a minimal simulator service and a camera so
that you can start a testbed server immediately.

Generating a Testbed Repository
-------------------------------

You can generate a testbed either directly from GitHub or from a local clone of the ``catkit2`` repository.

Run Cookiecutter from the directory containing the repository:

.. code-block:: shell

   cookiecutter catkit2/cookiecutter-testbed

Cookiecutter will launch an interactive setup process in your terminal. You will be prompted for values such as:

- project name
- package name
- author information
- version number

Press **Enter** to accept the default value shown in parentheses, or type your own value and press Enter.

Answering the Cookiecutter Prompts
----------------------------------

After running the command, you will see prompts similar to:

::

   [1/9] full_name:
   [2/9] email:
   [3/9] github_username:
   [4/9] pypi_package_name:
   [5/9] project_name:
   [6/9] project_slug:
   ...

Key fields:

**pypi_package_name**
   The technical package name. This determines:

   - the Python package directory
   - the import name
   - the command used to start the server

   Example::

      pypi_package_name: my_testbed

   Later commands will use this name::

      cd my_testbed
      my_testbed start server --simulated

**project_name**
   Human-readable title used in documentation and metadata.

**project_slug**
   A filesystem-friendly name, usually derived automatically from
   ``pypi_package_name``. In most cases the default is correct.

.. note::

   The generated directory name and command-line entry point are based on
   ``pypi_package_name`` (and typically ``project_slug``), not on
   ``project_name``.

When the prompts are complete, Cookiecutter creates a new project directory using the selected package name.

Starting the Testbed Server
---------------------------

After generation, install your project - make sure you have followed the :doc:`installation instructions <installation>` for catkit2 first
and are in the same conda environment:

.. code-block:: shell

   cd my_testbed
   pip install -e .

You are now ready to fire up your very own testbed server. To do so without having to have prepared any hardware,
you can start the server in simulated mode using the following command:

.. code-block:: shell

   my_testbed start server --simulated

where you replace ``my_testbed`` with the value you provided for ``pypi_package_name``.

When started with ``--simulated``, the server automatically runs the simulator service defined by the testbed configuration,
and uses the simulated service type defined for each individual service..

Next steps
----------

``my_testbed`` will be your testbed repo, installed in editable mode. The generated repository includes:
**CODE_OF_CONDUCT.md**, **README.md**, **pyproject.toml** with metadata and dependencies, a **src/** directory containing the package code, and a **docs/** directory with template documentation. The package includes a minimal simulator service and simulated camera service that runs when the server starts in simulated mode. You can modify or replace this service to implement your own testbed functionality.

After confirming the server starts successfully, you can:

- Explore the generated **directory structure**
- Inspect the **simulator service** and **optical model**
- Modify, replace or **add services** with your own implementations
- Add hardware service types when moving beyond simulation

What to expect when running in simulated mode
---------------------------------------------

When you run the server with ``--simulated``, you should see log output in the server terminal window indicating that
the server has started and that the simulator service is running. The server will be listening for incoming requests,
and the simulator will be generating simulated data according to its configuration.

To quit the server, you can typically press ``Ctrl+C`` or ``CMD+C`` in the terminal where it is running. This will
gracefully shut down the server and any running services. Watch out for incoming log messages if the server is still
processing requests when you attempt to shut it down, as this can sometimes delay the shutdown process.

By default, the ``my_testbed`` package includes a simple simulator service that runs when the server starts in simulated mode.
Instead of calling the hardware services defined by the hardware service type in each service configuration section,
the simulator service calls on the sample optical model defined in ``my_testbed_optical_model.py``. This optical model
simulates a simple pupil mask and a camera, and its parameters are read from ``config/simulator.yml``. By talking to the
simulated camear, can access the simulated camera images generated by the optical model.


Example: Access Camera Images
---------------------------------------------------------------

You can interact with the simulated camera in exactly the same way like you would with a real hardware camera. The camera
has a data stream that holds camera images, in this case generated by the optical model.

To access camera image through the camera service proxy, you can run the following from a python terminal:

.. code-block:: python

   from catkit2 import TestbedProxy

   testbed = TestbedProxy('127.0.0.1', 1234)
   cam = testbed.sample_camera
   image = np.mean(list(cam.take_raw_exposures(5)), axis=0)

This will have the camera acquire 5 raw exposures and return the average image.

How to transition to hardware
-----------------------------

To transition from simulation to hardware, you can start by modifying the camera service to interface with your actual
hardware camera model instead of the simulated version. For this, you need to update the ``sample_camera`` section in the
``services.yml`` config file to reflect your specific setup. See :doc:`Services <services>` for details on the service config entries.

Once you have made the necessary changes, you can start the server without the ``--simulated`` flag to run it in hardware mode:

.. code-block:: shell

   my_testbed start server

It is recommended to add and calibrate hardware services one by one, testing each service by running the server without
the ``--simulated`` flag to ensure that it is functioning correctly with the real hardware. You might also want to debug
each service in its own terminal window to monitor its output and ensure it is communicating correctly with the hardware and the testbed server.
You can find instructions for launching and debugging services in the :ref:`Launching and Debugging a service <launch-debug-service>` documentation.

Extending your optical model
----------------------------
Even as you transition to hardware, you can continue to use the simulated mode for testing and development. You can
extend your optical model to include additional features or to better match the behavior of your testbed. This allows
you to maintain a simulated environment for testing while you are developing and calibrating your hardware setup.
