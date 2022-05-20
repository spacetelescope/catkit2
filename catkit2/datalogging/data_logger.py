import time
import io
import os

import matplotlib.pyplot as plt
import numpy as np

def get_logger(name):
    '''Get a data logger with name `name`.

    Parameters
    ----------
    name : string
        The name of the data logger to retrieve.

    Returns
    -------
    DataLogger
        The retrieved data logger object.
    '''
    return DataLogger(name)

def _matplotlib_figure_to_image(fig, dpi=None):
    '''Convert a Matplotlib figure to an image as Numpy array.

    Parameters
    ----------
    fig : Matplotlib Figure
        The figure to convert.
    dpi : float
        The dpi of the converted image. If this is None, the default Matplotlib dpi will be used.

    Returns
    -------
    ndarray
        The image of of the Matplotlib figure.
    '''
    if dpi is not None:
        fig.dpi = dpi

    buf = io.BytesIO()
    fig.savefig(buf, format='rgba', dpi=dpi)

    width, height = fig.canvas.get_width_height()

    image = np.frombuffer(buf.getvalue(), np.uint8).reshape((height, width, -1))
    return image

class Event(object):
    '''An event containing data from an Experiment.

    This is a dumb data container object.

    Parameters
    ----------
    wall_time : float
        A Unix timestamp of when the event was created.
    tag : string
        An identifier for the logged value.
    value : any
        The value to be written to the log.
    value_type : string
        A string identifying the data type of value.
    '''
    def __init__(self, wall_time, tag, value, value_type):
        self.wall_time = wall_time
        self.tag = tag
        self.value = value
        self.value_type = value_type

    def __repr__(self):
        tree = {'wall_time': self.wall_time, 'value_type': self.value_type, 'tag': self.tag, 'value': self.value}

        return 'Event(' + repr(tree) + ')'

    def __str__(self):
        tree = {'wall_time': self.wall_time, 'value_type': self.value_type, 'tag': self.tag, 'value': self.value}

        return 'Event(' + str(tree) + ')'

class DataLogger(object):
    '''A logger for logging data from an `Experiment`.

    The name is currently not used, but might in the future. It is meant to follow the
    standard Python logging library, and it is therefore recommended to create a DataLogger
    with the name `__name__`:

    ```
    datalogging.get_logger(__name__).
    ```

    .. note::
        This class does not actually write the logged data to a file. This is done by adding a
        writer with `DataLogger.add_writer(writer)`.

    Parameters
    ----------
    name : string
        The name of the data logger.
    '''
    def __init__(self, name):
        # Saving the name for potential future use.
        self.name = name

    _writers = []

    @classmethod
    def add_writer(cls, writer):
        '''Add a writer to the data logging.

        This writer will be called using `writer.log(wall_time, tag, value, value_type)` whenever
        an data log event is triggered.

        Parameters
        ----------
        writer : class object
            An object capable of handling data log events.
        '''
        cls._writers.append(writer)

    @classmethod
    def remove_writer(cls, writer):
        '''Remove a writer from the data logging.

        Parameters
        ----------
        writer : class object
            The writer to remove from the list of writers.
        '''
        cls._writers.remove(writer)

    def log(self, tag, value, value_type=None):
        '''Add an event to the data log.

        Parameters
        ----------
        tag : string
            An identifier for the logged value.
        value : any
            The value to be written to the log.
        value_type : string
            A string identifying the data type of value. If this is None (default),
            the type will be set to a stringified version of the Python type
            of `value`.
        '''
        if value_type is None:
            value_type = str(type(value))

        wall_time = time.time_ns() / 1e9

        for writer in self._writers:
            writer.log(wall_time, tag, value, value_type)

    def log_scalar(self, tag, scalar):
        '''Add a scalar to the data log.

        Parameters
        ----------
        tag : string
            An identifier for the logged value.
        scalar : float
            The value to be written to the log.
        '''
        self.log(tag, scalar, 'scalar')

    def log_tensor(self, tag, tensor):
        '''Add a Numpy array to the data log.

        Parameters
        ----------
        tag : string
            An identifier for the logged value.
        tensor : array_like
            The value to be written to the log. This will be casted
            to a Numpy ndarray.
        '''
        self.log(tag, np.array(tensor), 'tensor')

    def log_curve(self, tag, x, y):
        '''Add a curve to the data log.

        A curve is a combination of an x and y Numpy array.

        Parameters
        ----------
        tag : string
            An identifier for the logged value.
        x : array_like
            The x-value of the curve. This will be casted to a
            Numpy ndarray.
        y : array_like
            The y-value of the curve. This will be casted to a
            Numpy ndarray.
        '''
        self.log(tag, {'x': np.array(x), 'y': np.array(y)}, 'curve')

    def log_figure(self, tag, fig=None, dpi=None, close=False):
        '''Add a Matplotlib figure to the data log.

        Parameters
        ----------
        tag : string
            An identifier for the logged value.
        fig : Matplotlib Figure or None
            The figure to write to the log. If this is None, the current Matplotlib Figure will be used.
        dpi : float
            The dpi of the converted image. If this is None, the default Matplotlib dpi will be used.
        close : boolean
            Whether to close the Figure after writing to the log. Default: False.
        '''
        if fig is None:
            fig = plt.gcf()

        value = _matplotlib_figure_to_image(fig, dpi=dpi)
        self.log(tag, value, 'figure')

        if close:
            plt.close(fig)

    def log_fits_file(self, tag, uri):
        '''Add a Numpy array to the data log.

        Parameters
        ----------
        tag : string
            An identifier for the logged value.
        uri : string
            The path to the fits file relative to the current working directory or an absolute path.
        '''
        self.log(tag, os.path.abspath(uri), 'fits_file')
