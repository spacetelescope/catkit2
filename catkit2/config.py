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

        if not os.path.isabs(path):
            path = os.path.abspath(os.path.join(config_path, path))

        return path

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_constructor('!path', path_constructor)
    return Loader

def _read_config_files_from_path(config_path):
    filenames = os.listdir(config_path)
    filenames = [fname for fname in filenames if fname.endswith('.yml')]

    config = {}
    for fname in filenames:
        with open(os.path.join(config_path, fname)) as f:
            contents = f.read()

        conf = yaml.load(contents, Loader=_get_yaml_loader(config_path))
        config[fname[:-4]] = conf

    return config

def read_config_files(config_paths):
    config = {}

    for config_path in config_paths:
        config = _deep_update(config, _read_config_files_from_path(config_path))

    return config
