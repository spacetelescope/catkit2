from catkit2.catkit_bindings import DataStream

stream = DataStream.open('20212.boston_dm.correction_howfs')
print('opened')
print(stream.get())
