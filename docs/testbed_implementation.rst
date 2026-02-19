Testbed Implementation
======================

catkit2 includes code to generate a sample catkit2-based testbed package from the command line using `cookiecutter <https://github.com/audreyfeldroy/cookiecutter-pypackage>`__.
This is meant to provide a starting place from which to build out your own full testbed repository. Cookiecutter automatically generates all configuration and installation files, a
pyproject.toml, template docs, and a sample simulated service to be able to start running your own testbed server.

To generate the testbed repository, from the command line run:

.. code-block:: shell

   cookiecutter catkit2/cookiecutter-testbed

You will then be prompted with a series of questions answered by typing directly in the console. One of these will specify the testbed name (e.g. ``my_testbed``).

You can then start the server for ``my_testbed`` by running:

.. code-block:: shell

   cd my_testbed
   pip install -e .
   my_testbed start server --simulated
