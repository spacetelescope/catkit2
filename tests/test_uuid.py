from catkit2.catkit_bindings import Uuid
import uuid

def test_uuid_generation():
    # Generate a UUID using the catkit2 library
    catkit_uuid = Uuid.generate()

    # Validate if the generated UUID is a valid UUID
    uuid_obj = uuid.UUID(str(catkit_uuid))
    assert uuid_obj.version == 4, "Generated UUID is not a valid UUID4"
    assert str(catkit_uuid) == str(uuid_obj), "Generated UUID does not match the expected format"
