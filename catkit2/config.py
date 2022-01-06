import yaml
import re
import os
import collections.abc

def _deep_update(original, update):
    if not isinstance(original, collections.abc.Mapping):
        return update

    for key, value in update.items():
        if isinstance(value, collections.abc.Mapping):
            original[key] = _deep_update(original.get(key, {}), value)
        else:
            original[key] = value

    return original

def _get_yaml_loader(config_path):
    def path_constructor(loader, node):
        path = loader.construct_scalar(node)
        path = os.path.expanduser(path)

        if not os.path.isabs(path):
            path = os.path.abspath(os.path.join(config_path, path))

        return path

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_constructor('!path', path_constructor)
    return Loader

def _read_config_file(config_file):
    config = {}

    contents = config_file.read_text()
    loader = _get_yaml_loader(config_file.parent)

    conf = yaml.load(contents, Loader=loader)
    config[os.path.splitext(config_file.name)[0]] = conf

    return config

def read_config_files(config_files):
    '''Read all configuration files and return a single configuration.

    `config_files` is an ordered list. Files later in this list will overwrite
    the read in values from files earlier in the list. Each file creates its own
    section in the returned configuration dictionary, named after its filename
    without file extension.

    Parameters
    ----------
    config_files : list of Path objects
        A list of configuration files to be read in.

    Returns
    -------
    dict
        A dictionary containing all configuration as read in from the files.
    '''
    config = {}

    for config_file in config_files:
        config = _deep_update(config, _read_config_file(config_file))

    return config
