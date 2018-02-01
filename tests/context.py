"""
Sets the path so the tests can find the module.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# PEP8 complains here with E402. But they can't be earlier.
import geocode  # noqa
import geocode.requests as requests  # noqa

import service.service as service  # noqa
