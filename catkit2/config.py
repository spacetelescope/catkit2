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

def _read_config_file(config_file):
    config = {}

    contents = config_file.read_text()
    loader = _get_yaml_loader(config_file.parent)

    conf = yaml.load(contents, Loader=loader)
    config[config_file.name[:-4]] = conf

    return config

def read_config_files(config_files):
    config = {}

    for config_file in config_files:
        config = _deep_update(config, _read_config_file(config_file))

    return config
