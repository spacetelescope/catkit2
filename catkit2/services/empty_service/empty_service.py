from catkit2.testbed.service import Service


class EmptyService(Service):
    def __init__(self):
        super().__init__('empty_service')

    def main(self):
        # Just wait until we're being shut down.
        while not self.should_shut_down:
            self.sleep(1)


if __name__ == '__main__':
    service = EmptyService()
    service.run()
