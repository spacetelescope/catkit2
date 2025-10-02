from setuptools import setup, find_packages

setup(name="benchlet",
      version="0.1.0",
      author="The CATKit2 team",
      description="Control code and simulator for an example catkit2 testbed.",
      url="https://github.com/spacetelescope/catkit2",
      packages=find_packages(),
      package_data={'benchlet': ['user_interface/assets/*']},
      classifiers=[
                        "Programming Language :: Python :: 3"
                  ],
      python_requires='>=3.6',
      zip_safe=False,
      install_requires=[],
      entry_points={
            "console_scripts": [
                  "benchlet=benchlet.cli_interface:main"
            ],
            "catkit2.services": [
                  'benchlet_simulator = benchlet.services.benchlet_simulator.benchlet_simulator',
            ],
      },
      )
