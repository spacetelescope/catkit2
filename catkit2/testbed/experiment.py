import logging
import os
import socket
import time
import datetime
import asdf
import yaml

from .logging import CatkitLogHandler, LogWriter
from ..catkit_bindings import LogForwarder

class Experiment:
    name = None

    log = logging.getLogger(__name__)
    _running_experiments = []

    def __init__(self, testbed, metadata=None, is_base_experiment=None):
        if metadata is None:
            metadata = {}

        if self.name is None:
            raise RuntimeError('Your experiment should have a name.')

        self.testbed = testbed
        self.metadata = metadata
        self.is_base_experiment = is_base_experiment

        self.config = testbed.config
        self.is_simulated = testbed.is_simulated

        self.child_experiment_id = 0

    def run(self):
        started_experiment = False

        log_handler = None
        log_forwarder = None
        self._log_writer = None

        try:
            # Add myself to the list of running experiments.
            Experiment._running_experiments.append(self)
            started_experiment = True

            # Figure out if we are a base experiment, unless overridden.
            if self.is_base_experiment is None:
                self.is_base_experiment = len(Experiment._running_experiments) == 1

            # Compute and make output path.
            self.output_path = self._compute_output_path()
            os.makedirs(self.output_path, exist_ok=True)

            # Write out metadata to this output path.
            af = asdf.AsdfFile(self.metadata)
            af.write_to(os.path.join(self.output_path, 'metadata.asdf'))

            # Write out full testbed config to this output path.
            with open(os.path.join(self.output_path, 'config.yml'), 'w') as f:
                yaml.dump(self.testbed.config, f)

            # Set up log handlers, but only once
            if len(Experiment._running_experiments) == 1:
                # Set up handler for distributing our Python log messages.
                log_handler = CatkitLogHandler()
                logging.getLogger().addHandler(log_handler)
                logging.getLogger().setLevel(logging.DEBUG)

                # Set up log forwarder.
                log_forwarder = LogForwarder('experiment', f'tcp://{self.testbed.host}:{self.testbed.logging_ingress_port}')

                # Set up log writer.
                self._log_writer = LogWriter(self.testbed.host, self.testbed.logging_egress_port)
                self._log_writer.start()

            log_writer = Experiment._running_experiments[0]._log_writer

            # Log the start of this new experiment.
            self.log.info(f'Starting new experiment {self.name}.')
            self.log.info(f'All output of this experiment is stored in {self.output_path}.')

            # Compute log filename.
            log_filename = os.path.join(self.output_path, 'experiment.log')

            with log_writer.output_to(log_filename):
                # Run actual experiment code.
                try:
                    self.pre_experiment()
                except Exception as e:
                    self.log.critical('An exception occurred during the pre-experiment.')
                    self.log.critical(str(e))

                    raise

                try:
                    self.experiment()
                except Exception as e:
                    self.log.critical('An exception occurred during the experiment.')
                    self.log.critical(str(e))

                    raise

                try:
                    self.post_experiment()
                except Exception as e:
                    self.log.critical('An exception occurred during the post-experiment.')
                    self.log.critical(str(e))

                    raise
        finally:
            # Tear down log handler.
            if self._log_writer is not None:
                self._log_writer.stop()

            if log_forwarder is not None:
                log_forwarder = None

            if log_handler is not None:
                logging.getLogger().removeHandler(log_handler)

            # Remove myself from the list of running experiments.
            if started_experiment:
                Experiment._running_experiments.pop()

    def _compute_output_path(self):
        experiment_depth = len(Experiment._running_experiments)

        if experiment_depth > 1:
            parent_experiment = Experiment._running_experiments[-2]
        else:
            parent_experiment = None

        # Compute the base data path.
        if experiment_depth == 1:
            # Get the base data path from scratch.
            if 'CATKIT_DATA_PATH' in os.environ:
                base_data_path = os.environ['CATKIT_DATA_PATH']
            elif 'base_data_path' in self.config['testbed']:
                conf = self.config['testbed']['base_data_path']
                base_data_path = conf['default']

                if 'by_hostname' in conf:
                    hostname = socket.gethostname()
                    if hostname in conf['by_hostname']:
                        self.base_data_path = conf['by_hostname'][hostname]
            else:
                raise RuntimeError('No data path could be found in the config files nor as an environment variable.')
        else:
            base_data_path = parent_experiment.output_path

        # Compute the experiment path.
        if experiment_depth == 1:
            experiment_path_template = self.config['testbed']['base_experiment_path']
        else:
            experiment_path_template = self.config['testbed']['sub_experiment_path']

        # Compute experiment id.
        if experiment_depth == 1:
            experiment_id = 0
        else:
            experiment_id = parent_experiment.child_experiment_id
            parent_experiment.child_experiment_id += 1

        # Get current date and time as a string.
        time_stamp = time.time()
        date_and_time = datetime.datetime.fromtimestamp(time_stamp).strftime("%Y-%m-%dT%H-%M-%S")

        # Populate template variables.
        format_dict = {
            'simulator_or_hardware': 'simulator' if self.is_simulated else 'hardware',
            'date_and_time': date_and_time,
            'experiment_name': self.name,
            'experiment_id': experiment_id
        }

        # Compute the output path.
        experiment_path = experiment_path_template.format(**format_dict)
        output_path = os.path.join(base_data_path, experiment_path)

        return output_path

    def pre_experiment(self):
        pass

    def experiment(self):
        pass

    def post_experiment(self):
        pass
