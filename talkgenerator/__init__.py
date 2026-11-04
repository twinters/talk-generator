from importlib.metadata import PackageNotFoundError, version

name = "talkgenerator"

try:
    __version__ = version("talkgenerator")
except PackageNotFoundError:  # running from a source checkout that isn't installed
    __version__ = "0+unknown"
