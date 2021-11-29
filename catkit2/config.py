import yaml
import pkg_resources

def read_config(config_file=None):
    if config_file is None:
        config_file = pkg_resources.resource_stream('catkit2', 'config.yaml')

    try:
        contents = config_file.read()
    except AttributeError:
        # `config_file` is not a file object, so treat it as a filename.
        with open(config_file) as f:
            contents = f.read()

    conf = yaml.safe_load(contents)
    return conf
