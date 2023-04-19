import pytest

def test_service_property(test_service):
    # We should be able to read and write to a property.
    test_service.readwrite_property = 2
    assert test_service.readwrite_property == 2

def test_service_property_readonly(test_service):
    expected_value = test_service.config['readonly_property']

    # We should be able to read from a readonly property.
    assert test_service.readonly_property == expected_value

    # Writing to a readonly property should yield an exception.
    with pytest.raises(RuntimeError):
        test_service.readonly_property = 3

def test_service_command(test_service):
    a = 'a'
    b = 'b'

    assert test_service.add(a=a, b=b) == a + b
