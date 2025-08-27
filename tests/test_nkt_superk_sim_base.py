"""Unit tests for the NKT SuperK simulation base class."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np


class TestNktSuperkSimBase(unittest.TestCase):
    """Test the NktSuperkSimBase abstract class."""

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

    @patch('catkit2.base_services.nkt_superk_sim_base.Service')
    def test_cannot_instantiate_abstract_base(self, mock_service):
        """Test that the abstract base class cannot be instantiated."""
        with patch.dict('sys.modules', {'catkit2.testbed.service': Mock()}):
            from catkit2.base_services.nkt_superk_sim_base import NktSuperkSimBase
            
            with self.assertRaises(TypeError):
                # Should fail because abstract methods are not implemented
                NktSuperkSimBase('test')

    def test_concrete_simulation_implementation_structure(self):
        """Test that concrete simulation implementations have the required structure."""
        # Mock everything we need
        with patch.dict('sys.modules', {'catkit2.testbed.service': Mock()}):
            with patch('catkit2.base_services.nkt_superk_sim_base.Service'):
                
                from catkit2.base_services.nkt_superk_sim_base import NktSuperkSimBase
                from catkit2.services.nkt_superk_evo_sim.nkt_superk_evo_sim import NktSuperkEvoSim
                from catkit2.services.nkt_superk_fianium_sim.nkt_superk_fianium_sim import NktSuperkFianiumSim
                
                # Test inheritance
                self.assertTrue(issubclass(NktSuperkEvoSim, NktSuperkSimBase))
                self.assertTrue(issubclass(NktSuperkFianiumSim, NktSuperkSimBase))
                
                # Test that abstract methods are implemented
                required_methods = [
                    '_create_device_specific_streams',
                    '_get_device_specific_funcs', 
                    '_device_specific_cleanup',
                    'set_emission'
                ]
                
                for method in required_methods:
                    self.assertTrue(hasattr(NktSuperkEvoSim, method))
                    self.assertTrue(hasattr(NktSuperkFianiumSim, method))
                
                # Test that common methods are available
                common_methods = [
                    'set_nd_setpoint', 'set_swp_setpoint', 'set_lwp_setpoint',
                    'update_varia_status', 'monitor_func', 'update_func'
                ]
                
                for method in common_methods:
                    self.assertTrue(hasattr(NktSuperkEvoSim, method))
                    self.assertTrue(hasattr(NktSuperkFianiumSim, method))

    def test_evo_sim_specific_methods(self):
        """Test that EVO simulation has device-specific methods."""
        with patch.dict('sys.modules', {'catkit2.testbed.service': Mock()}):
            with patch('catkit2.base_services.nkt_superk_sim_base.Service'):
                from catkit2.services.nkt_superk_evo_sim.nkt_superk_evo_sim import NktSuperkEvoSim
                
                # Test EVO-specific methods
                evo_methods = ['update_evo_status', 'set_power_setpoint', 'set_current_setpoint']
                
                for method in evo_methods:
                    self.assertTrue(hasattr(NktSuperkEvoSim, method))

    def test_fianium_sim_specific_methods(self):
        """Test that FIANIUM simulation has device-specific methods."""
        with patch.dict('sys.modules', {'catkit2.testbed.service': Mock()}):
            with patch('catkit2.base_services.nkt_superk_sim_base.Service'):
                from catkit2.services.nkt_superk_fianium_sim.nkt_superk_fianium_sim import NktSuperkFianiumSim
                
                # Test FIANIUM-specific methods
                fianium_methods = ['set_power_setpoint', 'set_pulse_picker_ratio', 'monitor_pulse_picker_ratio']
                
                for method in fianium_methods:
                    self.assertTrue(hasattr(NktSuperkFianiumSim, method))


if __name__ == '__main__':
    unittest.main()