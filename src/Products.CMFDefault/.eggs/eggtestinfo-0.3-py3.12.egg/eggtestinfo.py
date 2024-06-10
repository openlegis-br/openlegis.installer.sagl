"""setuptools entry point to capture test info in the .egg-info directory

After installing this egg, rerun 'setup.py egg_info' to get the new file
written into the .egg-info directory of your checkouts.
"""
from pkg_resources import yield_lines

_TEMPLATE = """\
test_module = %s
test_suite = %s
test_loader = %s
tests_require = %s
"""

def write_test_info(cmd, basename, filename):
    dist = cmd.distribution
    test_module = getattr(dist, 'test_module', '')
    test_suite = getattr(dist, 'test_suite', '')
    test_loader = getattr(dist, 'test_loader', '')
    tests_require = '\n   '.join(
        yield_lines(getattr(dist, 'tests_require', '') or ()))
    cmd.write_or_delete_file("test_info", filename,
                             _TEMPLATE % (test_module,
                                          test_suite,
                                          test_loader,
                                          tests_require,
                                         ))
