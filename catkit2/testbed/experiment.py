class Experiment:
    name = 'default_experiment_name'

    def __init__(self, testbed, metadata=None, is_base_experiment=None):
        self.testbed = testbed
        self.metadata = metadata
        self.is_base_experiment = is_base_experiment

    def run(self):
        # Let testbed know that a new experiment has started.
        self.testbed.start_new_experiment(self.name, self.metadata)
        self.output_path = testbed.output_path

        try:
            # Get if we are a main experiment or not
            if self.is_base_experiment is None:
                self.is_base_experiment = self.testbed.experiment_depth == 1

            # Run actual experiment code.
            self.pre_experiment()
            self.experiment()
            self.post_experiment()
        finally:
            # Let testbed know that this experiment has ended.
            self.testbed.end_experiment()

    def pre_experiment(self):
        pass

    def experiment(self):
        pass

    def post_experiment(self):
        pass

    def reset_testbed(self):
        pass
