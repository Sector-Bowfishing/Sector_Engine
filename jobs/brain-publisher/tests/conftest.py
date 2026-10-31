import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, ".."), os.path.join(HERE, "..", "..", "brain_platform"), os.path.join(HERE, "..", "..", "brain_platform", "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)
