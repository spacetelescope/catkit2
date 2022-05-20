import os
import io
import copy
import sys

import numpy as np
import matplotlib.pyplot as plt
import asdf
import imageio
from astropy.io import fits

from .event_pb2 import Event as ProtoEvent, Tensor as ProtoTensor
from .data_logger import Event

_INDEX_FNAME = 'data_log_index.asdf'
_BINARY_FNAME = 'data_log.dat'

def _numpy_to_proto(arr, out=None):
    '''Convert a Numpy array to a ProtoTensor.

    Parameters
    ----------
    arr : ndarray
        The array to be converted.
    out : ProtoTensor
        The output object. If this is None, a new ProtoTensor will be created.

    Returns
    -------
    ProtoTensor
        The created ProtoTensor (or `out` if that was provided).
    '''
    if out is None:
        out = ProtoTensor()

    out.shape[:] = arr.shape
    out.dtype = str(arr.dtype)
    out.data = arr.tobytes()

    if arr.dtype.byteorder == '<':
        out.byte_order = 'little'
    elif arr.dtype.byteorder == '>':
        out.byte_order = 'big'
    elif arr.dtype.byteorder == '=':
        out.byte_order = sys.byteorder
    else:
        out.byte_order = '|'

    return out

def _proto_to_numpy(tensor):
    '''Convert a ProtoTensor into a Numpy array.

    Parameters
    ----------
    tensor : ProtoTensor
        The ProtoTensor to convert.

    Returns
    -------
    ndarray
        The created Numpy array.
    '''
    dtype = np.dtype(tensor.dtype).newbyteorder(tensor.byte_order)

    arr = np.frombuffer(tensor.data, dtype=dtype)
    arr = arr.reshape(tensor.shape)

    return arr

class SerializableEvent(Event):
    '''A serializable version of an Event.
    '''
    def serialize(self, log_dir):
        '''Serialize an Event to a tree and binary blob.

        The binary blob is created using protobuffers.

        Parameters
        ----------
        log_dir : string
            The log directory. This is used to resolve absolute paths into relative paths.

        Returns
        -------
        tree : dictionary
            A tree containing all information on this event.
        serialized_bytes : bytes
            A raw binary blob containing binarizable values and ids.
        '''
        tree = {'wall_time': self.wall_time, 'value_type': self.value_type, 'tag': self.tag}

        event_proto = ProtoEvent()
        event_proto.wall_time = self.wall_time
        event_proto.tag = self.tag
        event_proto.value_type = self.value_type

        if self.value_type == 'scalar':
            if isinstance(self.value, np.ndarray):
                self.value = self.value.item()

            event_proto.scalar = self.value
        elif self.value_type == 'tensor':
            _numpy_to_proto(self.value, out=event_proto.tensor)
        elif self.value_type == 'curve':
            _numpy_to_proto(self.value['x'], out=event_proto.curve.x)
            _numpy_to_proto(self.value['y'], out=event_proto.curve.y)
        elif self.value_type == 'figure':
            buf = io.BytesIO()
            imageio.imwrite(buf, self.value, 'png')

            event_proto.figure.png = buf.getvalue()
        elif self.value_type == 'fits_file':
            start = os.path.abspath(log_dir)

            if self._log_dir is None:
                # The value is an absolute path.
                path = self._value
            else:
                # The value is a path relative to the log directory.
                path = os.path.abspath(os.path.join(self._log_dir, self._value))

            event_proto.fits_file.uri = os.path.relpath(path, start=start)
        else:
            tree['value'] = self.value

        serialized_bytes = event_proto.SerializeToString()
        tree['serialized_length'] = len(serialized_bytes)

        return tree, serialized_bytes

    @classmethod
    def deserialize(cls, tree, binary_file, offset, log_dir, load_in_memory=False):
        '''Load a SerializableEvent from a tree and a binary file.

        Parameters
        ----------
        tree : dictionary
            The dictionary containing all information about this event.
        binary_file : file object
            The file containing the binary data for this event.
        offset : integer
            The offset inside the `binary_file` where the binary data is located.
        log_dir : string
            The log directory. This is used to resolve absolute paths into relative paths.
        load_in_memory : boolean
            Whether to load big values in memory. If this is False, only small (anything that
            is not a tensor or fits file) values are loaded in memory.

        Returns
        -------
        SerializedEvent
            The event that is read from the tree and binary file.
        '''
        event = cls(tree['wall_time'], tree['tag'], None, tree['value_type'])

        event._binary_file = binary_file
        event._offset = offset
        event._serialized_length = tree['serialized_length']
        event._log_dir = log_dir

        if 'value' in tree:
            # The value is not contained in the binary file. This also releases the binary file handle.
            event.value = tree['value']
        else:
            event._value = None

            # Convert relative filenames to absolute filenames.
            if load_in_memory or event.value_type not in ['tensor', 'fits_file']:
                # This loads the event value in memory and releases the binary file handle.
                event.value = event.value

        return event

    @property
    def value(self):
        # Check if the value is not set
        if self._value is None:
            if self._binary_file is None:
                # Value is actually set, but is None
                return None

            # Lazy load the value from the binary data file.
            self._binary_file.seek(self._offset)
            serialized_bytes = self._binary_file.read(self._serialized_length)

            event = ProtoEvent()
            event.ParseFromString(serialized_bytes)

            if self.value_type == 'scalar':
                return event.scalar
            elif self.value_type == 'tensor':
                return _proto_to_numpy(event.tensor)
            elif self.value_type == 'curve':
                return {'x': _proto_to_numpy(event.curve.x),
                        'y': _proto_to_numpy(event.curve.y)}
            elif self.value_type == 'figure':
                return imageio.imread(event.figure.png)
            elif self.value_type == 'fits_file':
                with fits.open(os.path.join(self._log_dir, event.fits_file.uri)) as hdu_list:
                    hdu_list_copy = copy.deepcopy(hdu_list)
                return hdu_list_copy
            else:
                raise RuntimeError('No value was present. This should never happen.')
        else:
            return self._value

    @value.setter
    def value(self, value):
        self._value = value

        # Release handles of data file.
        self._binary_file = None
        self._offset = None
        self._serialized_length = None
        self._log_dir = None


class DataLogWriter(object):
    '''A writer to write events to a binary log file.

    This produces a binary log file composed of a binary file containing
    protobuffers for each event, and an ASDF file as an index to this file,
    which also contains any values that cannot be written to the binary file.

    Parameters
    ----------
    log_dir : string
        The path where the log files are written.
    flush_every : integer
        The number of events can be written before the index is rewritten
        to disk.
    index_fname : string
        The filename (without path) of the index file. If this is None, the default
        index filename will be used (preferred).
    '''
    def __init__(self, log_dir, flush_every=10, index_fname=None):
        self.log_dir = log_dir
        self.flush_every = flush_every

        if index_fname is None:
            index_fname = _INDEX_FNAME

        os.makedirs(self.log_dir, exist_ok=True)

        self.index_path = os.path.join(log_dir, index_fname)

        if os.path.exists(self.index_path):
            raise ValueError('A data log file already exists in this directory.')

        self.index_file = asdf.AsdfFile({'events': {}, 'binary_fname': _BINARY_FNAME})
        self.index_file.write_to(self.index_path)

        self.binary_file = open(os.path.join(log_dir, _BINARY_FNAME), 'wb')

        self._n = 0
        self._closed = False

    def __enter__(self):
        # TODO: Should/can this ADD itself to catkit.datalogging?
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # TODO: Should/can this REMOVE itself to catkit.datalogging?
        return self.close()

    def log(self, wall_time, tag, value, value_type):
        '''Add an event to the log file.

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

        Raises
        ------
        RuntimeError
            If attempted to log to a closed DataLogWriter.
        '''
        if self._closed:
            raise RuntimeError('Cannot add events to a closed DataLogWriter.')

        event = SerializableEvent(wall_time, tag, value, value_type)
        tree, serialized_bytes = event.serialize(os.path.dirname(self.index_path))

        if tag not in self.index_file.tree['events']:
            event_dict = {'wall_time': np.array([], dtype='float'),
                          'value_type': value_type,
                          'offset_in_binary_file': np.array([], dtype='int'),
                          'serialized_length': np.array([], dtype='int')}

            if 'value' in tree:
                event_dict['values'] = []

            self.index_file.tree['events'][tag] = event_dict

        records = self.index_file.tree['events'][tag]

        if records['value_type'] != value_type:
            raise ValueError('A tag must always have the same value type.')

        records['wall_time'] = np.append(records['wall_time'], event.wall_time)
        records['offset_in_binary_file'] = np.append(records['offset_in_binary_file'], self.binary_file.tell())
        records['serialized_length'] = np.append(records['serialized_length'], len(serialized_bytes))

        if 'value' in tree:
            records['values'].append(value)

        self.binary_file.write(serialized_bytes)

        self._n += 1
        if self._n >= self.flush_every:
            self.flush()

    def flush(self):
        '''Flush the data log.

        This refreshes the index file on disk, and flushes the binary data file,
        to ensure that no data is lost in case the program crashes.
        '''
        if self._n > 0:
            self.index_file.write_to(self.index_path)
            self.binary_file.flush()

        self._n = 0

    def close(self):
        '''Closes the data log.

        This flushes all files and closes the binary file.
        '''
        self.flush()

        self.binary_file.close()
        self.binary_file = None

        self._closed = True


class DataLogReader(object):
    '''A reader for data log files produced by `DataLogWriter`.

    Parameters
    ----------
    log_dir : string
        The path where the log files are written.
    load_in_memory : boolean
        Whether to load big values in memory upon loading of the data log. Default: False.
    index_fname : string
        The filename (without path) of the index file. If this is None, the default
        index filename will be used (preferred).
    '''
    def __init__(self, log_dir, load_in_memory=False, index_fname=None):
        if index_fname is None:
            index_fname = _INDEX_FNAME

        self.log_dir = log_dir
        self.index_path = os.path.join(log_dir, index_fname)

        if not os.path.exists(self.index_path):
            raise ValueError('A data log file does not exist in this directory.')

        self.load_in_memory = load_in_memory
        self._last_modified = 0

        self.reload()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.close()

    def reload(self, force=False):
        '''Reload the data log from disk.

        This reloads all events from the index and binary files if the index
        file on disk is newer than the one in memory, or if `force` is True.

        Parameters
        ----------
        force : boolean
            Force reloading even when the log file on disk is current with the
            events in memory.
        '''
        last_modified = os.path.getmtime(self.index_path)

        # Don't reload if the version in memory is current.
        if last_modified <= self._last_modified and not force:
            return

        self.events = {}

        with asdf.open(self.index_path, copy_arrays=True) as f:
            binary_file = open(os.path.join(self.log_dir, f.tree['binary_fname']), 'rb')

            for tag, events_for_tag in f.tree['events'].items():
                wall_times = events_for_tag['wall_time']
                offsets = events_for_tag['offset_in_binary_file']
                lengths = events_for_tag['serialized_length']
                value_type = events_for_tag['value_type']

                event_objects = []

                for i, (wall_time, offset, length) in enumerate(zip(wall_times, offsets, lengths)):
                    ev = {'wall_time': wall_time,
                          'tag': tag,
                          'value_type': value_type,
                          'serialized_length': length}

                    if 'values' in events_for_tag:
                        ev['value'] = events_for_tag['values'][i]

                    event = SerializableEvent.deserialize(ev, binary_file, offset,
                                                          os.path.dirname(self.index_path),
                                                          load_in_memory=self.load_in_memory)
                    event_objects.append(event)

                self.events[tag] = event_objects

        self._last_modified = os.path.getmtime(self.index_path)

    def get(self, tag, indices=slice(None), wall_time_min=0, wall_time_max=np.inf):
        '''Get all events for 'tag' with indices `indices` and within the specified time interval.

        .. warning::
            This loads all event values in memory for this tag within the specified
            ranges. If these values are large, this can overwhelm your memory capacity.

        Parameters
        ----------
        tag : string
            The identifier for the values to retrieve.
        indices : integer, slice, binary mask or None
            The indices to retrieve. Default: retrieve all.
        wall_time_min : float
            The minimum wall time as a Unix timestamp to retrieve events for.
            Default: since the dawn of time.
        wall_time_max : float
            The maximum wall time as a Unix timestamp to retrieve events for.
            Default: until the end of days.

        Returns
        -------
        wall_time : ndarray
            The wall time for all retrieved events.
        values : list
            The list of all values for all retrieved events.
        '''
        wall_time = np.array([ev.wall_time for ev in self.events[tag]])

        mask = np.zeros(len(wall_time), dtype='bool')
        mask[indices] = True

        # Inclusive on the minimum time and exclusive on the maximum time to avoid misses.
        mask = np.logical_and(mask, wall_time >= wall_time_min)
        mask = np.logical_and(mask, wall_time < wall_time_max)

        values = [ev.value for i, ev in enumerate(self.events[tag]) if mask[i]]
        wall_time = wall_time[mask]

        return wall_time, values

    def close(self):
        '''Close the log reader.
        '''
        self.events = {}
        self._last_modified = 0
