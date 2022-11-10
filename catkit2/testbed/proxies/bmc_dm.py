from ..service_proxy import ServiceProxy

import numpy as np
from astropy.io import fits
from astropy import units
from astropy.units import Quantity
from scipy.ndimage import map_coordinates

@ServiceProxy.register_service_interface('bmc_dm')
class BmcDmProxy(ServiceProxy):
    @property
    def dm_mask(self):
        if not hasattr(self, '_dm_mask'):
            fname = self.config['dm_mask_fname']

            self._dm_mask = fits.getdata(fname).astype('bool')

        return self._dm_mask

    @property
    def num_actuators(self):
        return self.config['num_actuators']

    def dm_shapes_to_command(self, dm1_shape, dm2_shape=None):
        command = np.zeros(2048)

        if dm2_shape is None:
            command[:952] = dm1_shape[:952]
            command[1024:1024 + 952] = dm1_shape[952:]
        else:
            command[:952] = dm1_shape[self.dm_mask]
            command[1024:1024 + 952] = dm2_shape[self.dm_mask]

        return command

    def command_to_dm_shapes(self, command):
        dm1_shape = np.zeros((34, 34))
        dm2_shape = np.zeros((34, 34))

        dm1_shape[self.dm_mask] = command[:952]
        dm2_shape[self.dm_mask] = command[1024:1024 + 952]

        return dm1_shape, dm2_shape

    def apply_shape(self, channel, dm1_shape, dm2_shape=None):
        command = self.dm_shapes_to_command(dm1_shape, dm2_shape)

        getattr(self, channel).submit_data(command)


    ### POKE COMMANDS
    def make_poke_command(self, actuators, amplitude = Quantity(250, units.nanometer), dm_num = 1):
        """
        Creates a 1D array DM command that can poke actuators at a given amplitude.

        :param actuators: List of actuators, or a single actuator.
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)

        amplitude = amplitude.to(units.meter).m

        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(actuators) + 1024*(dm_num-1)] = amplitude

        return command


    def make_diagonal_f_poke_command(self, amplitude = Quantity(250, units.nanometer), dm_num = 1):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        # this version seems to have a pixel in the wrong position (need to confirm with someone)
        #
        # actuators = [529,599,669,736,799,857,424,354,284,217,154,96,526,559,592,525,658,690,721,751,780,627,692,725,753,784,814,
        #             810,838,864,888,427,394,361,328,295,263,232,202,173,326,261,228,200,169,139,143,115,89,65]

        command = np.zeros(2048)

        amplitude = amplitude.to(units.meter).m

        actuators = [529,599,669,736,799,857,424,354,284,217,154,96,526,559,592,658,690,721,751,780,627,692,725,753,784,814,
                    810,838,864,888,427,394,361,328,295,263,232,202,173,326,261,228,200,169,139,143,115,89,65,625]

        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(actuators) + 1024*(dm_num-1)] = amplitude

        return command


    def make_f_poke_command(self, amplitude=Quantity(250, units.nanometer), dm_num = 1):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)
        
        amplitude = amplitude.to(units.meter).m

        actuators = [251, 284, 318, 352, 386, 420, 454, 488, 522, 556, 557, 558, 559,
                    560, 590, 624, 658, 691, 723, 724, 725, 726, 727, 728, 729, 730,
                    731, 732]
        
        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(actuators) + 1024*(dm_num-1)] = amplitude

        return command


    def make_checkerboard_poke_command(self, amplitude=Quantity(250, units.nanometer), dm_num = 1, offset_x=0, offset_y=3, step=4):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)
        
        amplitude = amplitude.to(units.meter).m

        num_actuators_pupil=34
        checkerboard = np.zeros((num_actuators_pupil, num_actuators_pupil))
        checkerboard[offset_x::step, offset_y::step] = 1
        if self._dm_mask is not None:
            checkerboard = checkerboard[self._dm_mask]
        else:
            self.dm_mask()
            checkerboard = checkerboard[self._dm_mask]
        
        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(checkerboard) + 1024*(dm_num-1)] = amplitude

        return command
    
    
    def make_x_poke_command(self, amplitude=Quantity(250, units.nanometer), dm_num = 1):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)
        
        amplitude = amplitude.to(units.meter).m

        actuators = [492, 525, 558, 591, 624, 657, 689, 720, 750, 779, 807, 833,  # top right cross beam
                    459, 426, 393, 360, 327, 294, 262, 231, 201, 172, 144, 118,  # bottom left cross beam
                    856, 828, 798, 767, 735, 702, 668, 633, 598, 563, 528, 493,  # top left cross beam
                    458, 423, 388, 353, 318, 283, 249, 216, 184, 153, 123, 95] 
        
        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(actuators) + 1024*(dm_num-1)] = amplitude

        return command


    def make_center_poke_command(self, amplitude=Quantity(250, units.nanometer), dm_num = 1):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)
        
        amplitude = amplitude.to(units.meter).m

        actuators = [458, 459, 492, 493]
        
        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(actuators) + 1024*(dm_num-1)] = amplitude

        return command


    def make_center_plus_poke_command(self, amplitude=Quantity(250, units.nanometer), dm_num = 1):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)
        
        amplitude = amplitude.to(units.meter).m

        actuators = [493, 492, 459, 458, 789, 788, 759, 758, 193, 192, 163, 162, 502, 501, 468, 467, 484, 483, 450, 449]
        
        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(actuators) + 1024*(dm_num-1)] = amplitude

        return command


    def make_outer_poke_command(self, amplitude=Quantity(250, units.nanometer), dm_num = 1):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)
        
        amplitude = amplitude.to(units.meter).m

        actuators = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 26, 27, 46, 47, 69, 93, 119, 147, 177, 207, 239, 271,
                    305, 339, 373, 407, 441, 475, 509, 543, 577, 611, 645, 679, 711, 743, 773, 803, 831, 857,
                    881, 903, 923, 922, 939, 938, 951, 950, 949, 948, 947, 946, 945, 944, 943, 942, 941, 940,
                    925, 924, 905, 904, 882, 858, 832, 804, 774, 744, 712, 680, 646, 612, 578, 544, 510, 476,
                    442, 408, 374, 340, 306, 272, 240, 208, 178, 148, 120, 94, 70, 48, 28, 29, 12, 13]
        
        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(actuators) + 1024*(dm_num-1)] = amplitude

        return command


    def make_apodizer_struts_poke_command(self, amplitude=Quantity(250, units.nanometer), dm_num = 1):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)
        
        amplitude = amplitude.to(units.meter).m

        actuators = [699, 631, 562, 763, 823,  # top left
                    559, 626, 692, 754, 812,  # top right
                    392, 325, 259, 197, 139,  # bottom left
                    389, 320, 252, 188, 128]  # bottom right
        
        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(actuators) + 1024*(dm_num-1)] = amplitude

        return command

    
    def make_asymmetric_test_poke_command(self, amplitude=Quantity(250, units.nanometer), dm_num = 1):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)
        
        amplitude = amplitude.to(units.meter).m

        actuators = [493, 492, 459, 458, 789, 788, 759, 758, 193, 192, 163, 162, 502, 501, 468, 467, 728,
                    727, 696, 695, 663, 662, 818, 817, 770, 769, 768, 767, 766, 737, 736, 735, 738, 739]
        
        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(actuators) + 1024*(dm_num-1)] = amplitude

        return command


    def make_symmetric_dm_center_poke_command(self, amplitude=Quantity(250, units.nanometer), dm_num = 1):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)
        
        amplitude = amplitude.to(units.meter).m

        actuators = [191, 194, 295, 259, 252, 282, 360, 355, 358, 353, 428, 421, 431, 533,
                    418, 520, 530, 523, 598, 596, 593, 591, 669, 699, 692, 656, 760, 757,
                    785, 792, 159, 166,
                    217, 230, 734, 721]
        
        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(actuators) + 1024*(dm_num-1)] = amplitude

        return command

    
    def make_aplc_symmetric_dm_center_poke_command(self, amplitude=Quantity(250, units.nanometer), dm_num = 1):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)
        
        amplitude = amplitude.to(units.meter).m

        actuators = [191, 194, 329, 316, 432, 534, 519, 587, 602,
                    349, 364, 789, 162, 417, 635, 622, 760, 757] #Todo HICAT-992
        
        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(actuators) + 1024*(dm_num-1)] = amplitude

        return command  

    
    def make_sine_wave_poke_command(self, amplitude=Quantity(250, units.nanometer), dm_num = 1, offset_x=0, theta=0, period=5):
        """
        :param amplitude: Nanometers of amplitude
        :param dm_num: int, which dm to poke
        :param offset_x: int, pixel offset of sine wave in x axis
        :param theta: float, angle in degrees by which to rotate sine wave pattern
        :param period: int, period (in pixels) of sine wave pattern 

        :return: a command (2*1024 length 1d array)
        """
        command = np.zeros(2048)
        
        amplitude = amplitude.to(units.meter).m

        #create supersampled version of sine wave pattern
        n=50
        sine = np.zeros((n, n))
        theta = theta*np.pi/180
        
        x, y = np.meshgrid(np.arange(n, dtype=np.float64), np.arange(n, dtype=np.float64))
        centx, centy = n//2 - 1, n//2 - 1
        
        xp = (x-centx)*np.cos(theta) + (y-centy)*np.sin(theta) + centx
        yp = -(x-centx)*np.sin(theta) + (y-centy)*np.cos(theta) + centy
        

        sine[:, offset_x::period] = 1
        
        #rotate sine wave pattern by theta degs
        sine = np.round(map_coordinates(sine, (yp, xp), cval=0), 0)
        
        #sub sample back down to 34x34
        sine = sine[50//2-17:50//2+17,50//2-17:50//2+17]

        #apply dm_mask
        if self._dm_mask is not None:
            sine = sine[self._dm_mask]
        else:
            self.dm_mask()
            sine = sine[self._dm_mask]

        if dm_num not in [1, 2]:
            print('Not a valid DM number.')
        else:
            command[np.array(sine) + 1024*(dm_num-1)] = amplitude

        return command  