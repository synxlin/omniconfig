"""Tests for OmniConfig serialize and deserialize methods."""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional, Self

import pytest
import yaml

from omniconfig import OmniConfig, OmniRegistry
from omniconfig.core.registry import RegistryMixin


# Test dataclasses
@dataclass
class SimpleConfig:
    """Simple configuration for basic tests."""

    name: str = "default"
    value: int = 42
    enabled: bool = True
    ratio: float = 3.14


@dataclass
class NestedConfig:
    """Nested configuration for nested tests."""

    title: str = "nested"
    simple: SimpleConfig = field(default_factory=SimpleConfig)
    optional_simple: Optional[SimpleConfig] = None


@dataclass
class DeeplyNestedConfig:
    """Deeply nested configuration for multi-level tests."""

    level: str = "deep"
    nested: NestedConfig = field(default_factory=NestedConfig)
    backup_nested: Optional[NestedConfig] = None


# Custom types for testing
class CustomConnection:
    """Custom connection type for testing type registration."""

    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port

    def __eq__(self, other):
        if not isinstance(other, CustomConnection):
            return False
        return self.host == other.host and self.port == other.port

    def __repr__(self):
        return f"CustomConnection(host={self.host}, port={self.port})"


@dataclass
class CustomTypeConfig:
    """Configuration with custom registered types."""

    path: Path = Path("/tmp")
    connection: CustomConnection = field(default_factory=CustomConnection)
    optional_path: Optional[Path] = None


class TestOmniConfigSerializeDeserialize:
    """Test suite for OmniConfig serialize and deserialize methods."""

    def setup_method(self):
        """Setup test environment."""
        # Clear any existing type registrations
        OmniConfig.clear_type_registry()
        OmniRegistry.clear_registry()

    def teardown_method(self):
        """Cleanup after each test."""
        OmniConfig.clear_type_registry()
        OmniRegistry.clear_registry()

    # Simple case tests
    def test_serialize_simple_dataclass(self):
        """Test serialization of a simple dataclass."""
        config = SimpleConfig(name="test", value=100, enabled=False, ratio=2.71)

        result = OmniConfig.serialize(config)

        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert result["value"] == 100
        assert result["enabled"] is False
        assert result["ratio"] == 2.71

    def test_deserialize_simple_dataclass(self):
        """Test deserialization of a simple dataclass from dict."""
        data = {"name": "custom", "value": 200, "enabled": True, "ratio": 1.618}

        result = OmniConfig.deserialize(SimpleConfig, data)

        assert isinstance(result, SimpleConfig)
        assert result.name == "custom"
        assert result.value == 200
        assert result.enabled is True
        assert result.ratio == 1.618

    def test_deserialize_simple_with_defaults(self):
        """Test deserialization with missing fields uses defaults."""
        data = {"name": "partial"}

        result = OmniConfig.deserialize(SimpleConfig, data)

        assert isinstance(result, SimpleConfig)
        assert result.name == "partial"
        assert result.value == 42  # default
        assert result.enabled is True  # default
        assert result.ratio == 3.14  # default

    def test_deserialize_from_json_string(self):
        """Test deserialization from JSON string."""
        json_str = '{"name": "from_json", "value": 99, "enabled": false, "ratio": 0.5}'

        result = OmniConfig.deserialize(SimpleConfig, json_str)

        assert isinstance(result, SimpleConfig)
        assert result.name == "from_json"
        assert result.value == 99
        assert result.enabled is False
        assert result.ratio == 0.5

    def test_deserialize_from_yaml_string(self):
        """Test deserialization from YAML string."""
        yaml_str = """
        name: from_yaml
        value: 77
        enabled: true
        ratio: 9.99
        """

        result = OmniConfig.deserialize(SimpleConfig, yaml_str)

        assert isinstance(result, SimpleConfig)
        assert result.name == "from_yaml"
        assert result.value == 77
        assert result.enabled is True
        assert result.ratio == 9.99

    def test_deserialize_from_file(self):
        """Test deserialization from file path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"name": "from_file", "value": 555, "enabled": False, "ratio": 123.456}
            yaml.dump(data, f)
            temp_file = f.name

        try:
            result = OmniConfig.deserialize(SimpleConfig, temp_file)

            assert isinstance(result, SimpleConfig)
            assert result.name == "from_file"
            assert result.value == 555
            assert result.enabled is False
            assert result.ratio == 123.456
        finally:
            Path(temp_file).unlink()

    # Nested case tests
    def test_serialize_nested_dataclass(self):
        """Test serialization of nested dataclass."""
        config = NestedConfig(
            title="parent",
            simple=SimpleConfig(name="child", value=10),
            optional_simple=SimpleConfig(name="optional", value=20),
        )

        result = OmniConfig.serialize(config)

        assert isinstance(result, dict)
        assert result["title"] == "parent"
        assert result["simple"]["name"] == "child"
        assert result["simple"]["value"] == 10
        assert result["optional_simple"]["name"] == "optional"
        assert result["optional_simple"]["value"] == 20

    def test_deserialize_nested_dataclass(self):
        """Test deserialization of nested dataclass."""
        data = {
            "title": "outer",
            "simple": {"name": "inner", "value": 33, "enabled": False, "ratio": 7.7},
        }

        result = OmniConfig.deserialize(NestedConfig, data)

        assert isinstance(result, NestedConfig)
        assert result.title == "outer"
        assert result.simple.name == "inner"
        assert result.simple.value == 33
        assert result.simple.enabled is False
        assert result.simple.ratio == 7.7
        assert result.optional_simple is None

    def test_serialize_deeply_nested_dataclass(self):
        """Test serialization of deeply nested dataclass."""
        config = DeeplyNestedConfig(
            level="top",
            nested=NestedConfig(title="middle", simple=SimpleConfig(name="bottom", value=999)),
            backup_nested=NestedConfig(title="backup"),
        )

        result = OmniConfig.serialize(config)

        assert result["level"] == "top"
        assert result["nested"]["title"] == "middle"
        assert result["nested"]["simple"]["name"] == "bottom"
        assert result["nested"]["simple"]["value"] == 999
        assert result["backup_nested"]["title"] == "backup"

    def test_deserialize_deeply_nested_dataclass(self):
        """Test deserialization of deeply nested dataclass."""
        data = {
            "level": "L1",
            "nested": {
                "title": "L2",
                "simple": {"name": "L3", "value": 789},
                "optional_simple": {"name": "L3_optional", "value": 456},
            },
        }

        result = OmniConfig.deserialize(DeeplyNestedConfig, data)

        assert result.level == "L1"
        assert result.nested.title == "L2"
        assert result.nested.simple.name == "L3"
        assert result.nested.simple.value == 789
        assert result.nested.optional_simple is not None
        assert result.nested.optional_simple.name == "L3_optional"
        assert result.nested.optional_simple.value == 456
        assert result.backup_nested is None

    # Custom types tests
    def test_dataclass_with_custom_types(self):
        """Test with custom registered types."""
        # Register Path type
        OmniConfig.register_type(Path, type_hint=str, factory=Path, reducer=str)

        # Register CustomConnection type
        OmniConfig.register_type(
            CustomConnection,
            type_hint=Dict[str, Any],
            factory=lambda d: CustomConnection(**d),
            reducer=lambda x: {"host": x.host, "port": x.port},
        )

        # Test deserialization
        data = {
            "path": "/home/user/data",
            "connection": {"host": "api.example.com", "port": 443},
            "optional_path": "/backup/path",
        }

        result = OmniConfig.deserialize(CustomTypeConfig, data)

        assert isinstance(result.path, Path)
        assert str(result.path) == "/home/user/data"

        assert isinstance(result.connection, CustomConnection)
        assert result.connection.host == "api.example.com"
        assert result.connection.port == 443

        assert isinstance(result.optional_path, Path)
        assert str(result.optional_path) == "/backup/path"

        # Test serialization
        config = CustomTypeConfig(
            path=Path("/test/path"),
            connection=CustomConnection("test.com", 8080),
            optional_path=Path("/opt/app"),
        )

        serialized = OmniConfig.serialize(config)

        assert serialized["path"] == "/test/path"
        assert serialized["connection"]["host"] == "test.com"
        assert serialized["connection"]["port"] == 8080
        assert serialized["optional_path"] == "/opt/app"

    # Registry-based config tests
    def test_registry_based_config(self):
        """Test with registry-based polymorphic configurations."""

        # Base registry class
        class ServiceConfig(RegistryMixin):
            _REGISTRY_NAME_FIELD: ClassVar[str] = "service_type"

            @classmethod
            def _factory(cls, kwargs: Dict[str, Any]) -> Self:
                service_type = kwargs.pop(cls._REGISTRY_NAME_FIELD, None)
                if service_type:
                    rcls = cls.retrieve(name=service_type)
                    if rcls:
                        return rcls(**kwargs)
                raise ValueError("Service type not specified")

            @classmethod
            def _reducer(cls, value: Self) -> dict[str, Any]:
                keys = cls.identify(value.__class__)
                if keys:
                    name = next(iter(keys))[1]
                    results = OmniConfig.serialize(value)
                    results[cls._REGISTRY_NAME_FIELD] = name
                    return results
                raise ValueError("Unable to determine service type")

        # Register with OmniConfig
        OmniConfig.register_type(
            ServiceConfig,
            type_hint=Dict[str, Any],
            factory=ServiceConfig._factory,
            reducer=ServiceConfig._reducer,
        )

        # Register implementations
        @ServiceConfig.register(name="database")
        @dataclass
        class DatabaseConfig(ServiceConfig):
            host: str = "localhost"
            port: int = 5432
            db_name: str = "test"

        @ServiceConfig.register(name="cache")
        @dataclass
        class CacheConfig(ServiceConfig):
            host: str = "localhost"
            port: int = 6379
            ttl: int = 3600

        @dataclass
        class SystemConfig:
            primary_db: ServiceConfig
            cache_layer: ServiceConfig

        # Test deserialization
        data = {
            "primary_db": {
                "service_type": "database",
                "host": "db.example.com",
                "port": 5433,
                "db_name": "production",
            },
            "cache_layer": {"service_type": "cache", "host": "cache.example.com", "ttl": 7200},
        }

        result = OmniConfig.deserialize(SystemConfig, data)

        assert isinstance(result.primary_db, DatabaseConfig)
        assert result.primary_db.host == "db.example.com"
        assert result.primary_db.port == 5433
        assert result.primary_db.db_name == "production"

        assert isinstance(result.cache_layer, CacheConfig)
        assert result.cache_layer.host == "cache.example.com"
        assert result.cache_layer.port == 6379  # default
        assert result.cache_layer.ttl == 7200

        # Test serialization
        serialized = OmniConfig.serialize(result)
        assert serialized["primary_db"]["service_type"] == "database"
        assert serialized["cache_layer"]["service_type"] == "cache"

    def test_deserialize_invalid_type_error(self):
        """Test deserialize raises error for invalid type."""
        with pytest.raises(TypeError, match="Invalid dataclass type"):
            OmniConfig.deserialize(str, {"key": "value"})

    def test_deserialize_invalid_string_error(self):
        """Test deserialize raises error for invalid string format."""
        with pytest.raises(ValueError, match="Invalid data format"):
            OmniConfig.deserialize(SimpleConfig, "not valid json or yaml }")

    def test_deserialize_invalid_data_format_error(self):
        """Test deserialize raises error for non-dict data."""
        with pytest.raises(ValueError, match="Invalid data format"):
            OmniConfig.deserialize(SimpleConfig, ["not", "a", "dict"])  # type: ignore
