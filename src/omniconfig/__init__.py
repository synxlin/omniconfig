"""OmniConfig - A decorator-based configuration management library.

This library provides seamless integration of command-line arguments,
configuration files (YAML/JSON), and environment variables.
"""

from .core.exceptions import (
    CircularReferenceError,
    ConfigError,
    ConfigFactoryError,
    ConfigParseError,
    ConfigReferenceError,
    ConfigValidationError,
    TypeRegistrationError,
)
from .core.registry import RegistryABC, RegistryABCMeta, RegistryMeta, RegistryMixin
from .namespace import OmniConfigNamespace
from .parser import OmniConfigParser
from .registry import OmniConfig, OmniRegistry
from .version import __version__

__all__ = [
    "OmniConfigParser",
    "OmniConfigNamespace",
    "OmniConfig",
    "OmniRegistry",
    "RegistryABC",
    "RegistryABCMeta",
    "RegistryMeta",
    "RegistryMixin",
    "ConfigError",
    "ConfigParseError",
    "ConfigValidationError",
    "CircularReferenceError",
    "ConfigReferenceError",
    "ConfigFactoryError",
    "TypeRegistrationError",
]
