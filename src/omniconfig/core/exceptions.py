"""Custom exceptions for OmniConfig."""


class ConfigError(Exception):
    """Base exception for all OmniConfig errors."""

    pass


class ConfigParseError(ConfigError):
    """Raised when parsing configuration values fails."""

    pass


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""

    pass


class CircularReferenceError(ConfigError):
    """Raised when circular references are detected."""

    pass


class ConfigReferenceError(ConfigError):
    """Raised when a reference cannot be resolved."""

    pass


class ConfigFactoryError(ConfigError):
    """Raised when factory application fails."""

    pass


class TypeRegistrationError(ConfigError):
    """Raised when type registration conflicts occur."""

    pass
