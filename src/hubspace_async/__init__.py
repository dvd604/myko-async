__all__ = [
    "HubSpaceConnection",
    "HubSpaceState",
    "HubSpaceAuth",
    "HubSpaceDevice",
    "HubSpaceRoom",
]

import logging
from importlib.metadata import PackageNotFoundError, version

from .auth import HubSpaceAuth
from .connection import HubSpaceConnection
from .device import HubSpaceDevice, HubSpaceState
from .room import HubSpaceRoom

logger = logging.getLogger(__name__)


try:
    # Change here if project is renamed and does not equal the package name
    dist_name = "hubspace-async"
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError
