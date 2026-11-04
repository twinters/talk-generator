import os

# Tests talk to the live services (or to fakes), never to responses cached by earlier runs
os.environ.setdefault("DISABLE_CACHE", "1")
