import numpy as np
import matplotlib.pyplot as plt
import os
from astropy.io import fits
import shutil

import catkit2.datalogging


def test_data_log_interface(tmpdir):
    logger = catkit2.datalogging.get_logger(__name__)

    # Make sure this doesn't crash, even though nothing should be written out.
    logger.log_scalar('tag', 5)

    with catkit2.datalogging.DataLogWriter(tmpdir):
        logger.log_scalar('tag2', 10)


def test_data_log_retrieval(tmpdir):
    logger = catkit2.datalogging.get_logger(__name__)

    with catkit2.datalogging.DataLogWriter(tmpdir) as writer:
        catkit2.datalogging.DataLogger.add_writer(writer)

        scalar = float(np.random.randn(1))
        tensor = np.random.randn(100, 250)
        curve_x = np.random.randn(30)
        curve_y = np.random.randn(30)

        plt.plot(curve_x, curve_y)

        hdu = fits.PrimaryHDU(tensor)
        fits_fname = os.path.join(tmpdir, 'tensor.fits')
        hdu.writeto(fits_fname)

        logger.log_scalar('a', scalar)
        logger.log_scalar('a', scalar * 2)
        logger.log_scalar('a', scalar * -0.5)

        logger.log_tensor('b', tensor)

        logger.log_curve('c', curve_x, curve_y)

        logger.log_figure('d')

        logger.log_fits_file('e', fits_fname)

        # Unregister writer
        catkit2.datalogging.DataLogger.remove_writer(writer)

    with catkit2.datalogging.DataLogReader(tmpdir) as reader:

        wall_time, scalars = reader.get('a')
        assert np.allclose(scalars[0], scalar)
        assert len(scalars) == 3

        wall_time, scalars = reader.get('a', slice(1,None))
        assert len(scalars) == 2
        assert len(wall_time) == 2

        wall_time, tensors = reader.get('b')
        assert np.allclose(tensors[0], tensor)

        wall_time, curve = reader.get('c')
        assert np.allclose(curve[0]['x'], curve_x)
        assert np.allclose(curve[0]['y'], curve_y)

        wall_time, figs = reader.get('d')
        assert figs[0].ndim == 3

        wall_time, fits_files = reader.get('e')
        assert np.allclose(fits_files[0][0].data, tensor)
