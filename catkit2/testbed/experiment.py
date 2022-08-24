import logging
import os
import socket
import time
import datetime

from catkit2.testbed.logging import CatkitLogHandler


class Experiment:
    name = 'default_experiment_name'

    log = logging.getLogger(__name__)
    _running_experiments = []

    def __init__(self, testbed, metadata=None, is_base_experiment=None):
        self.testbed = testbed
        self.metadata = metadata
        self.is_base_experiment = is_base_experiment

        self.config = testbed.config
        self.is_simulated = testbed.is_simulated

        self.child_experiment_id = 0

    def run(self):
        started_experiment = False
        set_up_log_handler = False

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

            # Set up log handlers, but only once
            if len(Experiment._running_experiments) == 1:
                # Set up handler for distributing our Python log messages.
                log_handler = CatkitLogHandler()
                logging.getLogger().addHandler(log_handler)
                logging.getLogger().setLevel(logging.DEBUG)
                set_up_log_handler = True

            # Run actual experiment code.
            self.pre_experiment()
            self.experiment()
            self.post_experiment()
        finally:
            # Tear down log handler.
            if set_up_log_handler:
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

    def reset_testbed(self):
        pass
