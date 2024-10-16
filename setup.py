import setuptools
import os
import re
import sys
import glob
import shutil
import platform
import subprocess

from distutils.version import LooseVersion
from setuptools import setup, Extension
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

    python_path = os.path.join(source_dir, 'catkit2', 'proto')
    cpp_path = os.path.join(source_dir, 'catkit_core', 'proto')

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
            build_args += ['-j', '4']

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
    entry_points={
        'catkit2.services': [
            'aimtti_plp_device = catkit2.services.aimtti_plp_device.aimtti_plp_device',
            'aimtti_plp_device_sim = catkit2.services.aimtti_plp_device_sim.aimtti_plp_device_sim',
            'allied_vision_camera = catkit2.services.allied_vision_camera.allied_vision_camera',
            'bmc_deformable_mirror_hardware = catkit2.services.bmc_deformable_mirror_hardware.bmc_deformable_mirror_hardware',
            'bmc_deformable_mirror_sim = catkit2.services.bmc_deformable_mirror_sim.bmc_deformable_mirror_sim',
            'bmc_dm = catkit2.services.bmc_dm.bmc_dm',
            'bmc_dm_sim = catkit2.services.bmc_dm_sim.bmc_dm_sim',
            'camera_sim = catkit2.services.camera_sim.camera_sim',
            'dummy_camera = catkit2.services.dummy_camera.dummy_camera',
            'empty_service = catkit2.services.empty_service.empty_service',
            'flir_camera = catkit2.services.flir_camera.flir_camera',
            'hamamatsu_camera = catkit2.services.hamamatsu_camera.hamamatsu_camera',
            'newport_picomotor = catkit2.services.newport_picomotor.newport_picomotor',
            'newport_picomotor_sim = catkit2.services.newport_picomotor_sim.newport_picomotor_sim',
            'newport_xps_q8 = catkit2.services.newport_xps_q8.newport_xps_q8',
            'newport_xps_q8_sim = catkit2.services.newport_xps_q8_sim.newport_xps_q8_sim',
            'ni_daq = catkit2.services.ni_daq.ni_daq',
            'ni_daq_sim = catkit2.services.ni_daq_sim.ni_daq_sim',
            'nkt_superk = catkit2.services.nkt_superk.nkt_superk',
            'nkt_superk_sim = catkit2.services.nkt_superk_sim.nkt_superk_sim',
            'oceanoptics_spectrometer = catkit2.services.oceanoptics_spectrometer.oceanoptics_spectrometer',
            'oceanoptics_spectrometer_sim = catkit2.services.oceanoptics_spectrometer_sim.oceanoptics_spectrometer_sim',
            'omega_ithx_w3 = catkit2.services.omega_ithx_w3.omega_ithx_w3',
            'omega_ithx_w3_sim = catkit2.services.omega_ithx_w3_sim.omega_ithx_w3_sim',
            'safety_manual_check = catkit2.services.safety_manual_check.safety_manual_check',
            'safety_monitor = catkit2.services.safety_monitor.safety_monitor',
            'simple_simulator = catkit2.services.simple_simulator.simple_simulator',
            'snmp_ups = catkit2.services.snmp_ups.snmp_ups',
            'snmp_ups_sim = catkit2.services.snmp_ups_sim.snmp_ups_sim',
            'thorlabs_cld101x = catkit2.services.thorlabs_cld101x.thorlabs_cld101x',
            'thorlabs_cld101x_sim = catkit2.services.thorlabs_cld101x_sim.thorlabs_cld101x_sim',
            'thorlabs_cube_motor_kinesis = catkit2.services.thorlabs_cube_motor_kinesis.thorlabs_cube_motor_kinesis',
            'thorlabs_cube_motor_kinesis_sim = catkit2.services.thorlabs_cube_motor_kinesis_sim.thorlabs_cube_motor_kinesis_sim',
            'thorlabs_fw102c = catkit2.services.thorlabs_fw102c.thorlabs_fw102c',
            'thorlabs_mcls1 = catkit2.services.thorlabs_mcls1.thorlabs_mcls1',
            'thorlabs_mcls1_sim = catkit2.services.thorlabs_mcls1_sim.thorlabs_mcls1_sim',
            'thorlabs_mff101 = catkit2.services.thorlabs_mff101.thorlabs_mff101',
            'thorlabs_mff101_sim = catkit2.services.thorlabs_mff101_sim.thorlabs_mff101_sim',
            'thorlabs_pm = catkit2.services.thorlabs_pm.thorlabs_pm',
            'thorlabs_pm_sim = catkit2.services.thorlabs_pm_sim.thorlabs_pm_sim',
            'thorlabs_tsp01 = catkit2.services.thorlabs_tsp01.thorlabs_tsp01',
            'thorlabs_tsp01_sim = catkit2.services.thorlabs_tsp01_sim.thorlabs_tsp01_sim',
            'web_power_switch = catkit2.services.web_power_switch.web_power_switch',
            'web_power_switch_sim = catkit2.services.web_power_switch_sim.web_power_switch_sim',
            'zwo_camera = catkit2.services.zwo_camera.zwo_camera',
        ],
        'catkit2.proxies': [
            'bmc_dm = catkit2.testbed.proxies.bmc_dm:BmcDmProxy',
            'camera = catkit2.testbed.proxies.camera:CameraProxy',
            'deformable_mirror = catkit2.testbed.proxies.deformable_mirror:DeformableMirrorProxy',
            'flip_mount = catkit2.testbed.proxies.flip_mount:FlipMountProxy',
            'newport_picomotor = catkit2.testbed.proxies.newport_picomotor:NewportPicomotorProxy',
            'newport_xps_q8 = catkit2.testbed.proxies.newport_xps:NewportXpsQ8Proxy',
            'ni_daq = catkit2.testbed.proxies.ni_daq:NiDaqProxy',
            'nkt_superk = catkit2.testbed.proxies.nkt_superk:NktSuperkProxy',
            'oceanoptics_spectrometer = catkit2.testbed.proxies.oceanoptics_spectrometer:OceanopticsSpectroProxy',
            'thorlabs_cube_motor_kinesis = catkit2.testbed.proxies.thorlabs_cube_motor_kinesis:ThorlabsCubeMotorKinesisProxy',
            'thorlabs_mcls1 = catkit2.testbed.proxies.thorlabs_mcls1:ThorlabsMcls1',
            'web_power_switch = catkit2.testbed.proxies.web_power_switch:WebPowerSwitchProxy'
        ]
    }
)
