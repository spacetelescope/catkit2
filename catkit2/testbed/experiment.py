import logging
from catkit2.testbed.log_handler import CatkitLogHandler


class Experiment:
    name = 'default_experiment_name'

    log = logging.getLogger(__name__)

    def __init__(self, testbed, metadata=None, is_base_experiment=None):
        self.testbed = testbed
        self.metadata = metadata
        self.is_base_experiment = is_base_experiment

    def run(self):
        started_experiment = False
        set_up_log_handler = False

        try:
            # Let testbed know that a new experiment has started.
            self.testbed.start_new_experiment(self.name, self.metadata)
            started_experiment = True

            self.output_path = self.testbed.output_path

            # Set up log handlers, but only once
            if self.testbed.experiment_depth == 1:
                log_handler = CatkitLogHandler()
                logging.getLogger().addHandler(log_handler)
                set_up_log_handler = True

            # Get if we are a main experiment or not
            if self.is_base_experiment is None:
                self.is_base_experiment = self.testbed.experiment_depth == 1

            # Run actual experiment code.
            self.pre_experiment()
            self.experiment()
            self.post_experiment()
        finally:
            if started_experiment:
                # Let testbed know that this experiment has ended.
                self.testbed.end_experiment()

            if set_up_log_handler:
                logging.getLogger().removeHandler(log_handler)

    def pre_experiment(self):
        pass

    def experiment(self):
        pass

    def post_experiment(self):
        pass

    def reset_testbed(self):
        pass
