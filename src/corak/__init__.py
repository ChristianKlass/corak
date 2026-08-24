"""corak -- procedurally generated geometric wallpapers.

Nothing here is downloaded; every image is drawn from a seed.
"""

from importlib.metadata import PackageNotFoundError, version

# Read from the installed metadata rather than written here as well. Two copies
# drift, and the one that drifts is the one the user is shown: 0.1.1 shipped
# reporting itself as 0.1.0.
try:
    __version__ = version("corak")
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0.0.0+unknown"
