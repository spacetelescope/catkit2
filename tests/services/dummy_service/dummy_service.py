from catkit2 import Service

class DummyService(Service):
    def __init__(self):
        super().__init__('dummy_service')

        self.readonly_property = self.config['readonly_property']
        self.readwrite_property = 1

    def open(self):
        self.make_property('readonly_property', self.get_readonly)
        self.make_property('readwrite_property', self.get_readwrite, self.set_readwrite)

        self.make_command('add', self.add)

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        pass

    def get_readonly(self):
        return self.readonly_property

    def get_readwrite(self):
        return self.readwrite_property

    def set_readwrite(self, value):
        self.readwrite_property = value

    def add(self, a, b):
        return a + b

if __name__ == '__main__':
    service = DummyService()
    service.run()
