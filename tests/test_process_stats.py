from catkit2.catkit_bindings import ProcessStats


def test_process_stats():
    stats = ProcessStats()
    stats.update()

    assert stats.memory_usage > 0
    assert stats.cpu_usage >= 0
