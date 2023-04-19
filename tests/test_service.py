def test_service_property(test_service):
    test_service.readwrite_property = 2
    assert test_service.readwrite_property == 2

def test_service_command(test_service):
    a = 'a'
    b = 'b'

    assert test_service.add(a=a, b=b) == a + b
