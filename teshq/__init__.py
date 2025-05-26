# teshq/__init__.py
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0.dev0+unknown"
