Testbed Implementation
======================

``catkit2`` includes a `Cookiecutter  <https://github.com/audreyfeldroy/cookiecutter-pypackage>`__ template that generates a starter catkit2-based testbed repository from the command line. This provides a starting point for building your own testbed. Cookiecutter creates the basic project structure automatically, including configuration files, installation metadata, a ``pyproject.toml``, template documentation, and a minimal simulator service so that you can start a testbed server immediately.


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

After generation, install the project and start the testbed server:

.. code-block:: shell

   cd my_testbed 
   pip install -e .
   my_testbed start server --simulated

Replace ``my_testbed`` with the value you provided for
``pypi_package_name``.

This will:

1. Install the package in editable mode.
2. Start the testbed server.

When started with ``--simulated``, the server automatically runs the simulator service defined by the testbed configuration.

Next Steps
----------

After confirming the server starts successfully, you can:

- explore the generated directory structure
- inspect the simulator service and optical model
- modify or replace services with your own implementations
- add hardware-backed services when moving beyond simulation