"""Unit tests for the consolidated NKT SuperK base class."""

import unittest
from unittest.mock import Mock, patch


class TestNktSuperk(unittest.TestCase):
    """Test the NktSuperk consolidated base class."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the Service base class
        self.mock_service = Mock()
        self.mock_service.config = {
            'port': 'COM1',
            'emission': 1,
            'nd_setpoint': 1.0,
            'swp_setpoint': 500.0,
            'lwp_setpoint': 600.0
        }

        # Mock data streams
        self.mock_stream = Mock()
        self.mock_stream.get.return_value = [0]
        self.mock_stream.get_next_frame.return_value = Mock(data=[0])

        self.mock_service.make_data_stream.return_value = self.mock_stream

    @patch('catkit2.base_services.nkt_superk.Service')
    def test_cannot_instantiate_abstract_base(self, mock_service):
        """Test that the abstract base class cannot be instantiated."""
        with patch.dict('sys.modules', {'catkit2.testbed.service': Mock()}):
            from catkit2.base_services.nkt_superk import NktSuperk

            with self.assertRaises(TypeError):
                # Should fail because abstract methods are not implemented
                NktSuperk('test')

    @patch('catkit2.base_services.nkt_superk.Service')
    def test_varia_enum(self, mock_service):
        """Test that the Varia enum is properly defined."""
        with patch.dict('sys.modules', {'catkit2.testbed.service': Mock()}):
            from catkit2.base_services.nkt_superk import Varia

            # Test that required attributes exist
            self.assertEqual(Varia.DEVICE_ID, 16)
            self.assertTrue(hasattr(Varia, 'REG_MONITOR_INPUT'))
            self.assertTrue(hasattr(Varia, 'REG_ND_SETPOINT'))
            self.assertTrue(hasattr(Varia, 'REG_SWP_SETPOINT'))
            self.assertTrue(hasattr(Varia, 'REG_LWP_SETPOINT'))
            self.assertTrue(hasattr(Varia, 'REG_STATUS_BITS'))

    @patch('catkit2.base_services.nkt_superk.Service')
    def test_register_helpers(self, mock_service):
        """Test that the register helper functions work correctly."""
        with patch.dict('sys.modules', {'catkit2.testbed.service': Mock()}):
            from catkit2.base_services.nkt_superk import read_register, write_register, Varia

            # Mock the register read/write functions
            mock_read_func = Mock()
            mock_write_func = Mock()

            # Test read_register
            getter = read_register(mock_read_func, Varia.REG_MONITOR_INPUT, ratio=0.1)
            self.assertTrue(callable(getter))

            # Test write_register
            setter = write_register(mock_write_func, Varia.REG_MONITOR_INPUT, ratio=0.1)
            self.assertTrue(callable(setter))

    def test_simulation_detection(self):
        """Test that simulation services are properly detected."""
        with patch.dict('sys.modules', {'catkit2.testbed.service': Mock()}):
            with patch('catkit2.base_services.nkt_superk.Service'):
                from catkit2.base_services.nkt_superk import NktSuperk

                # Create a concrete test implementation
                class TestNktSuperk(NktSuperk):
                    def _create_device_specific_streams(self):
                        pass
                    def _get_device_specific_funcs(self):
                        return {}
                    def _device_specific_cleanup(self):
                        pass
                    def set_emission(self, emission):
                        pass

                # Test hardware service detection
                hw_service = TestNktSuperk('nkt_superk_evo')
                self.assertFalse(hw_service.is_simulation)

                # Test simulation service detection
                sim_service = TestNktSuperk('nkt_superk_evo_sim')
                self.assertTrue(sim_service.is_simulation)

    def test_concrete_implementation_structure(self):
        """Test that concrete implementations have the required structure."""
        # Mock everything we need
        with patch.dict('sys.modules', {
            'catkit2.testbed.service': Mock(),
            'NKTP_DLL': Mock()
        }):
            with patch('catkit2.base_services.nkt_superk.Service'), \
                 patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.registerReadU16'), \
                 patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.registerWriteU16'), \
                 patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.registerReadU8'), \
                 patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.registerWriteU8'), \
                 patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.registerReadS16'), \
                 patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.openPorts'), \
                 patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.closePorts'), \
                 patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.RegisterResultTypes'), \
                 patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.registerReadU16'), \
                 patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.registerWriteU16'), \
                 patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.registerReadU8'), \
                 patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.registerWriteU8'), \
                 patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.registerReadS16'), \
                 patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.openPorts'), \
                 patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.closePorts'), \
                 patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.RegisterResultTypes'):

                from catkit2.base_services.nkt_superk import NktSuperk
                from catkit2.services.nkt_superk_evo.nkt_superk_evo import NktSuperkEvo
                from catkit2.services.nkt_superk_fianium.nkt_superk_fianium import NktSuperkFianium
                from catkit2.services.nkt_superk_evo_sim.nkt_superk_evo_sim import NktSuperkEvoSim
                from catkit2.services.nkt_superk_fianium_sim.nkt_superk_fianium_sim import NktSuperkFianiumSim

                # Test inheritance for all services
                all_services = [NktSuperkEvo, NktSuperkFianium, NktSuperkEvoSim, NktSuperkFianiumSim]
                for service_class in all_services:
                    self.assertTrue(issubclass(service_class, NktSuperk))

                # Test that abstract methods are implemented
                required_methods = [
                    '_create_device_specific_streams',
                    '_get_device_specific_funcs',
                    '_device_specific_cleanup',
                    'set_emission'
                ]

                for service_class in all_services:
                    for method in required_methods:
                        self.assertTrue(hasattr(service_class, method))

                # Test that common methods are available for all services
                common_methods = [
                    'update_varia_status', 'monitor_func', 'update_func',
                    'set_nd_setpoint', 'set_swp_setpoint', 'set_lwp_setpoint'
                ]

                for service_class in all_services:
                    for method in common_methods:
                        self.assertTrue(hasattr(service_class, method))

                # Test that hardware-specific methods are available for hardware services
                hardware_methods = [
                    'get_monitor_input', 'get_nd_setpoint', 'get_swp_setpoint',
                    'get_lwp_setpoint', 'get_varia_status_bits', 'check_result'
                ]

                for service_class in [NktSuperkEvo, NktSuperkFianium]:
                    for method in hardware_methods:
                        self.assertTrue(hasattr(service_class, method))

    def test_evo_specific_methods(self):
        """Test that EVO services have device-specific methods."""
        with patch.dict('sys.modules', {
            'catkit2.testbed.service': Mock(),
            'NKTP_DLL': Mock()
        }):
            with patch('catkit2.base_services.nkt_superk.Service'):
                # Mock necessary register functions
                with patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.registerReadU16'), \
                     patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.registerWriteU16'), \
                     patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.registerReadU8'), \
                     patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.registerWriteU8'), \
                     patch('catkit2.services.nkt_superk_evo.nkt_superk_evo.registerReadS16'):

                    from catkit2.services.nkt_superk_evo.nkt_superk_evo import NktSuperkEvo
                    from catkit2.services.nkt_superk_evo_sim.nkt_superk_evo_sim import NktSuperkEvoSim

                    # Test EVO-specific methods for both hardware and simulation
                    evo_methods = ['update_evo_status', 'set_power_setpoint', 'set_current_setpoint']

                    for method in evo_methods:
                        self.assertTrue(hasattr(NktSuperkEvo, method))
                        self.assertTrue(hasattr(NktSuperkEvoSim, method))

    def test_fianium_specific_methods(self):
        """Test that FIANIUM services have device-specific methods."""
        with patch.dict('sys.modules', {
            'catkit2.testbed.service': Mock(),
            'NKTP_DLL': Mock()
        }):
            with patch('catkit2.base_services.nkt_superk.Service'):
                # Mock necessary register functions
                with patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.registerReadU16'), \
                     patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.registerWriteU16'), \
                     patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.registerReadU8'), \
                     patch('catkit2.services.nkt_superk_fianium.nkt_superk_fianium.registerWriteU8'):

                    from catkit2.services.nkt_superk_fianium.nkt_superk_fianium import NktSuperkFianium
                    from catkit2.services.nkt_superk_fianium_sim.nkt_superk_fianium_sim import NktSuperkFianiumSim

                    # Test FIANIUM-specific methods for both hardware and simulation
                    fianium_methods = ['set_power_setpoint', 'set_pulse_picker_ratio', 'monitor_pulse_picker_ratio']

                    for method in fianium_methods:
                        self.assertTrue(hasattr(NktSuperkFianium, method))
                        self.assertTrue(hasattr(NktSuperkFianiumSim, method))


if __name__ == '__main__':
    unittest.main()
