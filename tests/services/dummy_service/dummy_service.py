from catkit2 import Service

import numpy as np

N = 16

class DummyService(Service):
    def __init__(self):
        super().__init__('dummy_service')

        self.readonly_property = self.config['readonly_property']
        self.readwrite_property = 1
        
        # Storage for slot values
        self.json_slot_value = {"initial": True}
        self.raw_slot_value = b"initial"
        self.array_slot_value = np.zeros((N, N), dtype='float64')
        self.writable_json_slot_value = {"initialized": True}

    def open(self):
        self.make_property('readonly_property', self.get_readonly)
        self.make_property('readwrite_property', self.get_readwrite, self.set_readwrite)

        self.make_command('add', self.add)
        self.make_command('push_on_stream', self.push_on_stream)
        self.make_command('publish_json_slot', self.publish_json_slot)
        self.make_command('publish_raw_slot', self.publish_raw_slot)
        self.make_command('publish_array_slot', self.publish_array_slot)

        self.stream = self.make_data_stream('stream', 'float64', [N, N], 20)
        self.push_on_stream()

        # Create read-write slots with setters
        self.json_slot = self.make_json_slot(
            'json_slot',
            self.on_json_slot_set
        )
        self.raw_slot = self.make_raw_slot(
            'raw_slot',
            self.on_raw_slot_set
        )
        self.array_slot = self.make_array_slot(
            'array_slot',
            self.on_array_slot_set
        )
        
        # Create a read-only raw slot (no setter)
        self.readonly_raw_slot = self.make_raw_slot('readonly_raw_slot')

    def on_json_slot_set(self, value, context):
        """Setter callback for json_slot."""
        self.json_slot_value = value
        # Confirm the set by publishing back
        context.publish_json(value)

    def on_raw_slot_set(self, value, context):
        """Setter callback for raw_slot."""
        self.raw_slot_value = bytes(value)
        # Confirm the set by publishing back
        context.publish_raw(value)

    def on_array_slot_set(self, value, context):
        """Setter callback for array_slot."""
        # value is a numpy array
        self.array_slot_value = value.copy()
        # Confirm the set by publishing back
        context.publish_array(value)

    def main(self):
        while not self.should_shut_down:
            self.sleep(0.1)

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

    def push_on_stream(self):
        arr = np.random.randn(N, N).astype('float64')
        self.stream.submit_data(arr)

    def publish_json_slot(self, data):
        """Publish JSON data to json_slot."""
        self.json_slot.publish(data)
        return True

    def publish_raw_slot(self, data):
        """Publish raw bytes to raw_slot."""
        # data comes as a string from JSON, convert to bytes
        if isinstance(data, str):
            data = data.encode('utf-8')
        elif isinstance(data, dict) and 'bytes' in data:
            # Handle case where bytes are passed specially
            data = data['bytes'].encode('utf-8') if isinstance(data['bytes'], str) else bytes(data['bytes'])
        self.raw_slot.publish(data)
        return True

    def publish_array_slot(self, data=None):
        """Publish numpy array to array_slot."""
        if data is None:
            arr = np.random.randn(N, N).astype('float64')
        else:
            arr = np.array(data).astype('float64')
        self.array_slot.publish(arr)
        return True

if __name__ == '__main__':
    service = DummyService()
    service.run()
