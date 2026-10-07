import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def pytest_configure(config):
    config.addinivalue_line("markers", "network: needs NOAA AWS + IEM (run with -m network)")
