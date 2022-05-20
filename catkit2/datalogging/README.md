This PR introduces three classes:

class DataLogger
---
This class is used to create log events. If you want to push something to the data log, you create an instance of this class with:

```
data_log = datalogging.get_logger(__name__)
```

The name is there to mimic the Python logging library interface. The name should be `__name__` but is currently not used by any code. It's mostly there so that, if we decide to use it in the future and transition towards being more conformal to the Python logging library API, then we would not have to add this name everywhere.

After creating the logger, you can push data to the data log using any of the `log_*()` functions. For example:

```
data_log.log_scalar('dark_zone_contrast', 1e-10) # woohoo
data_log.log_curve('contrast_curve', r, contrast)
data_log.log_fits_file('pupil_image', os.path.join(output_path, 'pupil_image.fits'))
```

In these functions, the first parameter is a tag of the value that you are pushing. This should describe what you are pushing and serves as the identifier to retrieve values written to a data log. The wall clock time (as a Unix timestamp) is also logged with your value, so you can reconstruct a time series later on.

You can also add general Python variables to the data log using the generic `log()` function:

```
data_log.log('params', parameter_dict)
```

These values are stored in a less efficient way, so in case your data is a scalar, tensor (= a Numpy array), curve (x and y Numpy arrays), Matplotlib figure, or external fits file, it is preferred to add those using the special functions instead.

So far, unless you are inside an `Experiment`, you won't see this value appearing in the data log just yet. Similarly to how the Python logging library works, if there is no handler attached to a log, it is silently ignored. We'll come to that later. catkit automatically starts a writer for you at the start of an `Experiment` and attaches it to the DataLogger object, so most of the time, you won't have to worry about this.

class DataLogWriter
---

This class actually writes the log events, created by the `DataLogger` to disk. It uses an index in the form of an ASDF file, and a sequential raw binary file for data storage. General Python variables are stored in the ASDF file and are therefore less efficient.

Every time a log event is recieved, it immediately writes its data to the binary file. The index is only written every few events, as there is a large cost associated with that. (My first version used threading to alleviate that cost and still write every event, but this had some problems with stopping the writer thread when an Exception occurred in the main thread.)

Writers can be added to the `DataLogger` using:

```
writer = datalogging.DataLogWriter(log_dir)
datalogging.DataLogger.add_writer(writer)
```
where `log_dir` is a path to the log directory. An exception will be raised if the log directory already contains a data log file. catkit already creates a writer in the experiment directory at the start of an experiment.

The writer can be closed by removing it from the data logger and closing it.
```
datalogging.DataLogger.remove_writer(writer)
writer.close()
```
catkit will do this automatically at the end of an experiment, even when an exception is thrown inside the experiment.

class DataLogReader
---

This class is used to read back a data log written by `DataLogReader`. It can read from data log files that are still being written to by a DataLogWriter, so it's safe to open a DataLogReader on another process while a DataLogWriter is still writing to the data log. To read all values with a tag:

```
reader = datalogging.DataLogReader(log_dir)
wall_time, dark_zone_contrasts = reader.get('dark_zone_contrast)
```
where `log_dir` is the directory of the log file. Large objects are not loaded in memory yet, but stay in the binary data file until requested. Fits files are returned as an in-memory `astropy.io.fits.HDUList` to avoid leaking open files.

You can also retrieve subsets, both using a time interval in wall clock time, or using indices, which usually correspond to iteration number.

```
wall_time, final_dark_zone_contrast = reader.get('dark_zone_contrast', -1)
wall_time, temperature_during_last_hour = reader.get('temperature', time.time() - 3600, time.time())
```

Underlying implementation details
---

The binary file contains serialized protobuffers, each of which is described by the `event.proto` file. The offset and length of each of these event serialized bytes is stored in the index ASDF file. The `event.proto` file is compiled into the `event_pb2.py` file so that it creates a Python object and serialization functions. Protobuffers are made to enable forward and backward compatibility without manual version control. So adding additional specialized types, while still being able to read old data log files, should be relatively easy.

Scalars are directly parsable by protobuffers and are added directly as a double precision float. If an integer is required, this should be casted back manually by the user.

Tensors are stored as a raw byte buffer, and an accompanying data type description. This data type also contains the endianness (called byte order by Numpy, so I retained that name), so the buffer can be read between different machines (although I don't know of any computers that are big-endian nowadays, except for IP, which we don't care about).

Curves are written as two Tensors. No shape checking is performed; this is the responsibility of the user. Upon reading, the curve is converted into a dictionary as `{'x': x_values, 'y': y_values}`.

Matplotlib figures are converted to an image as a Numpy array (so its shape is `(M, N, 4)` with RGBA values for each pixel). This is stored in the binary file as a compressed png image to reduce file size. Upon reading in the figure, it is decompressed and converted back into a Numpy array.

Fits files are relatively hard to parse. They should be added using an absolute path, or a path relative to the current working directory. This path is then converted into a path relative to the data log file, to enable moving of the data log directory to other folders. Then, upon reading in the data log file, this path is converted back into an absolute path, and the fits file is read from that directory using astropy.