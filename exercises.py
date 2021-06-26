from pytest_perf.deco import extras, deps


@extras('testing')
@deps('path')
def sample_test_perf():
    "sample test"
    import abc
    # exercise
    dir(abc)
