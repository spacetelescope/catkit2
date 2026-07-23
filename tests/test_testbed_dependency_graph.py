import pytest

from catkit2.testbed.testbed import Testbed


def compute(nodes, safety_service_id=None):
    return Testbed._compute_reverse_dependencies(nodes, safety_service_id)


def test_simple_graph():
    nodes = {
        'camera': ([], False),
        'controller': (['camera'], False),
        'script': (['controller', 'camera'], False)
    }

    graph = compute(nodes)

    assert graph == {
        'camera': ['controller', 'script'],
        'controller': ['script'],
        'script': []
    }


def test_safety_edges():
    nodes = {
        'safety': ([], False),
        'dm': ([], True),
        'camera': ([], False)
    }

    graph = compute(nodes, safety_service_id='safety')

    assert graph['safety'] == ['dm']
    assert graph['dm'] == []
    assert graph['camera'] == []


def test_unknown_dependency_is_ignored():
    nodes = {
        'camera': (['nonexistent'], False)
    }

    graph = compute(nodes)

    assert graph == {'camera': []}


def test_requires_safety_without_safety_service_raises():
    nodes = {
        'dm': ([], True)
    }

    with pytest.raises(RuntimeError, match='requires safety'):
        compute(nodes, safety_service_id=None)


def test_safety_service_not_in_services_raises():
    nodes = {
        'dm': ([], True)
    }

    with pytest.raises(RuntimeError, match='safety service'):
        compute(nodes, safety_service_id='safety')


def test_circular_dependencies_raise():
    nodes = {
        'a': (['b'], False),
        'b': (['a'], False)
    }

    with pytest.raises(RuntimeError, match='[Cc]ircular'):
        compute(nodes)


def test_self_dependency_raises():
    nodes = {
        'a': (['a'], False)
    }

    with pytest.raises(RuntimeError, match='[Cc]ircular'):
        compute(nodes)


def test_graph_is_independent_of_state():
    # _compute_reverse_dependencies() must not modify its inputs.
    dependencies = ['camera']
    nodes = {
        'camera': ([], False),
        'controller': (dependencies, False)
    }

    compute(nodes)

    assert dependencies == ['camera']
    assert set(nodes.keys()) == {'camera', 'controller'}
