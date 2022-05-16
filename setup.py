import setuptools
import os
import re
import sys
import glob
import shutil
import platform
import subprocess
from pathlib import Path

from distutils.version import LooseVersion
from setuptools import setup, find_packages, Extension
from setuptools.command.build_ext import build_ext
from distutils.spawn import find_executable

# Find the Protocol Compiler.
if 'PROTOC' in os.environ and os.path.exists(os.environ['PROTOC']):
    protoc = os.environ['PROTOC']
else:
    protoc = find_executable("protoc")

if protoc is None:
    sys.stderr.write(
    "protoc is not installed nor found in ../src.  Please compile it "
    "or install the binary package.\n")
    sys.exit(-1)

def generate_protos(source_dir):
    '''Invokes the Protobuf Compiler to generate C++ and Python source files
    from all .proto files in the proto directory. Does nothing if the output
    already exists and is newer than the input.
    '''
    proto_path = os.path.join(source_dir, 'proto')

    files = glob.glob(os.path.join(proto_path, '**.proto'))
    files = [os.path.relpath(f, proto_path) for f in files]

    python_path = os.path.join(proto_path, 'gen/python')
    cpp_path = os.path.join(proto_path, 'gen/cpp')

    os.makedirs(python_path, exist_ok=True)
    os.makedirs(cpp_path, exist_ok=True)

    for f in files:
        src_time = os.path.getmtime(os.path.join(proto_path, f))

        python_output = os.path.splitext(os.path.join(python_path, f))[0] + '_pb2.py'
        cpp_h_output = os.path.splitext(os.path.join(cpp_path, f))[0] + '.pb.h'
        cpp_cc_output = os.path.splitext(os.path.join(cpp_path, f))[0] + '.pb.cc'

        try:
            dest_time_python = os.path.getmtime(python_output)
            dest_time_cpp_h = os.path.getmtime(cpp_h_output)
            dest_time_cpp_cc = os.path.getmtime(cpp_cc_output)

            should_compile = min(dest_time_python, dest_time_cpp_h, dest_time_cpp_cc) < src_time
        except OSError:
            # Either the Python or C++ did not exist.
            should_compile = True

        if should_compile:
            protoc_command = [
                protoc,
                '--proto_path', proto_path,
                '--python_out', python_path,
                '--cpp_out', cpp_path,
                f]

            if subprocess.run(protoc_command).returncode != 0:
                sys.exit(-1)

class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=''):
        Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)

class CMakeBuild(build_ext):
    def run(self):
        try:
            out = subprocess.check_output(['cmake', '--version'])
        except OSError:
            raise RuntimeError(
                "CMake must be installed to build the following extensions: " +
                ", ".join(e.name for e in self.extensions))

        if platform.system() == "Windows":
            cmake_version = LooseVersion(re.search(r'version\s*([\d.]+)',
                                         out.decode()).group(1))
            if cmake_version < '3.1.0':
                raise RuntimeError("CMake >= 3.1.0 is required on Windows")

        for ext in self.extensions:
            self.build_extension(ext)

    def build_extension(self, ext):
        cmake_args = ['-DPYTHON_EXECUTABLE=' + sys.executable]

        cfg = 'Debug' if self.debug else 'Release'
        build_args = ['--config', cfg]

        if platform.system() == "Windows":
            if sys.maxsize > 2**32:
                cmake_args += ['-A', 'x64']
        else:
            cmake_args += ['-DCMAKE_BUILD_TYPE=' + cfg]
            build_args += ['--', '-j4']

        env = os.environ.copy()
        env['CXXFLAGS'] = '{} -DVERSION_INFO=\\"{}\\"'.format(env.get('CXXFLAGS', ''), self.distribution.get_version())

        install_dir = os.path.join(ext.sourcedir, 'build')

        os.makedirs(self.build_temp, exist_ok=True)
        os.makedirs(install_dir, exist_ok=True)

        print('Compiling protobuffers...')
        generate_protos(ext.sourcedir)

        subprocess.check_call(['cmake', ext.sourcedir] + cmake_args, cwd=self.build_temp, env=env)
        subprocess.check_call(['cmake', '--build', '.'] + build_args, cwd=self.build_temp)
        subprocess.check_call(['cmake', '--install', '.', '--prefix', install_dir], cwd=self.build_temp)

        for f in glob.glob(os.path.join(install_dir, 'lib', 'catkit_bindings*')):
            shutil.copy(f, os.path.join(ext.sourcedir, 'catkit2'))

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="catkit2",
    version="0.0.1",
    author="Emiel Por",
    author_email="epor@stsci.edu",
    description="A library for controlling testbed hardware",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    package_data={'catkit2': ['user_interface/assets/*']},
    classifiers=[
        "Programming Language :: Python :: 3"
    ],
    ext_modules=[CMakeExtension('catkit_bindings')],
    python_requires='>=3.6',
    cmdclass=dict(build_ext=CMakeBuild),
    zip_safe=False,
    install_requires=[],
)
