import pathlib
import os
import importlib.resources

import catkit2.config

class _Path:
    def __init__(self, package, resource):
        self.package = package
        self.resource = resource
        self.name = resource
        self.parent = os.path.dirname(__file__)

    def read_text(self, encoding=None, errors=None):
        return importlib.resources.read_text(
            self.package,
            self.resource,
            encoding=encoding,
            errors=errors
        )

def read_config(additional_config_paths=None):
    files = []

    if additional_config_paths is None:
        additional_config_paths = []

    for fname in importlib.resources.contents(__package__):
        if fname.endswith('.yml'):
            files.append(_Path(__package__, fname))

    for dirname in additional_config_paths:
        path = pathlib.Path(dirname)
        path = path.resolve()

        files.extend(path.glob('*.yml'))

    return catkit2.config.read_config_files(files)
