from catkit2.catkit_bindings import DataStream, get_timestamp

pid = input()
stream = DataStream.open(f'/{pid}.11267574fb14544c')
print('opened')
print(stream.get())
while True:
    frame = stream.get_next_frame()
    timestamp = get_timestamp()
    print(frame.id, frame.data, timestamp - frame.timestamp)

