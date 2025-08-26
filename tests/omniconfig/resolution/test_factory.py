"""Tests for FactorySystem implementation."""

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Dict, List, Optional, cast

import pytest

from omniconfig.core.exceptions import ConfigFactoryError
from omniconfig.core.types import CustomTypeInfo, TypeInfo
from omniconfig.resolution.factory import FactorySystem
from omniconfig.resolution.node import ResolutionNode


class ProductColor(Enum):
    """Product color options for e-commerce system."""

    RED = "red"
    GREEN = "green"
    BLUE = "blue"


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    hostname: str
    port: int = 5432


@dataclass
class ApplicationConfig:
    """Application configuration with nested components."""

    service_name: str
    database: DatabaseConfig
    max_connections: Optional[int] = None


class EmailValidator:
    """Email validation service for testing custom factories."""

    def __init__(self, domain: str):
        self.domain = domain

    def __eq__(self, other):
        return isinstance(other, EmailValidator) and self.domain == other.domain


class TestFactorySystemPrimitives:
    """Test primitive type conversions."""

    def test_convert_to_bool(self):
        """Test boolean conversion."""
        # From string
        node = ResolutionNode(content="true", path=("flag",))
        node.type_chains = [(TypeInfo(type_=bool),)]
        FactorySystem.apply(node)
        assert node.value is True

        node = ResolutionNode(content="false", path=("flag",))
        node.type_chains = [(TypeInfo(type_=bool),)]
        FactorySystem.apply(node)
        assert node.value is False

        node = ResolutionNode(content="yes", path=("flag",))
        node.type_chains = [(TypeInfo(type_=bool),)]
        FactorySystem.apply(node)
        assert node.value is True

        node = ResolutionNode(content="no", path=("flag",))
        node.type_chains = [(TypeInfo(type_=bool),)]
        FactorySystem.apply(node)
        assert node.value is False

        # From number
        node = ResolutionNode(content=1, path=("flag",))
        node.type_chains = [(TypeInfo(type_=bool),)]
        FactorySystem.apply(node)
        assert node.value is True

        node = ResolutionNode(content=0, path=("flag",))
        node.type_chains = [(TypeInfo(type_=bool),)]
        FactorySystem.apply(node)
        assert node.value is False

        # Invalid string
        node = ResolutionNode(content="invalid", path=("flag",))
        node.type_chains = [(TypeInfo(type_=bool),)]
        with pytest.raises(ConfigFactoryError, match="Cannot convert"):
            FactorySystem.apply(node)

    def test_convert_to_int(self):
        """Test integer conversion."""
        # From string
        node = ResolutionNode(content="123", path=("num",))
        node.type_chains = [(TypeInfo(type_=int),)]
        FactorySystem.apply(node)
        assert node.value == 123

        # From float
        node = ResolutionNode(content=45.0, path=("num",))
        node.type_chains = [(TypeInfo(type_=int),)]
        FactorySystem.apply(node)
        assert node.value == 45

        # Already int
        node = ResolutionNode(content=67, path=("num",))
        node.type_chains = [(TypeInfo(type_=int),)]
        FactorySystem.apply(node)
        assert node.value == 67

        # Invalid
        node = ResolutionNode(content="not_a_number", path=("num",))
        node.type_chains = [(TypeInfo(type_=int),)]
        with pytest.raises(ConfigFactoryError, match="Cannot convert"):
            FactorySystem.apply(node)

    def test_convert_to_float(self):
        """Test float conversion."""
        # From string
        node = ResolutionNode(content="3.14", path=("pi",))
        node.type_chains = [(TypeInfo(type_=float),)]
        FactorySystem.apply(node)
        assert node.value == 3.14

        # From int
        node = ResolutionNode(content=42, path=("num",))
        node.type_chains = [(TypeInfo(type_=float),)]
        FactorySystem.apply(node)
        assert node.value == 42.0

        # Already float
        node = ResolutionNode(content=2.718, path=("e",))
        node.type_chains = [(TypeInfo(type_=float),)]
        FactorySystem.apply(node)
        assert node.value == 2.718

    def test_convert_to_str(self):
        """Test string conversion."""
        # From int
        node = ResolutionNode(content=123, path=("text",))
        node.type_chains = [(TypeInfo(type_=str),)]
        FactorySystem.apply(node)
        assert node.value == "123"

        # From bool
        node = ResolutionNode(content=True, path=("text",))
        node.type_chains = [(TypeInfo(type_=str),)]
        FactorySystem.apply(node)
        assert node.value == "True"

        # Already string
        node = ResolutionNode(content="hello", path=("text",))
        node.type_chains = [(TypeInfo(type_=str),)]
        FactorySystem.apply(node)
        assert node.value == "hello"

    def test_none_value(self):
        """Test None value handling."""
        node = ResolutionNode(content=None, path=("empty",))
        node.type_chains = [(TypeInfo(type_=Optional[str]),)]
        FactorySystem.apply(node)
        assert node.value is None

        # None with non-optional type
        node = ResolutionNode(content=None, path=("required",))
        node.type_chains = [(TypeInfo(type_=str),)]
        FactorySystem.apply(node)
        assert node.value is None  # Still returns None


class TestFactorySystemEnums:
    """Test enum conversions."""

    def test_enum_by_name(self):
        """Test enum conversion by name."""
        node = ResolutionNode(content="RED", path=("color",))
        node.type_chains = [(TypeInfo(type_=ProductColor),)]
        FactorySystem.apply(node)
        assert node.value == ProductColor.RED

    def test_enum_by_value(self):
        """Test enum conversion by value."""
        node = ResolutionNode(content="green", path=("color",))
        node.type_chains = [(TypeInfo(type_=ProductColor),)]
        FactorySystem.apply(node)
        assert node.value == ProductColor.GREEN

    def test_enum_already_enum(self):
        """Test when value is already the enum type."""
        node = ResolutionNode(content="BLUE", path=("color",))
        node.type_chains = [(TypeInfo(type_=ProductColor),)]
        FactorySystem.apply(node)
        assert node.value == ProductColor.BLUE

    def test_enum_invalid_value(self):
        """Test invalid enum value."""
        node = ResolutionNode(content="yellow", path=("color",))
        node.type_chains = [(TypeInfo(type_=ProductColor),)]
        with pytest.raises(ConfigFactoryError, match="Cannot convert"):
            FactorySystem.apply(node)


class TestFactorySystemContainers:
    """Test container type conversions."""

    def test_list_conversion(self):
        """Test list conversion."""
        # From list
        child1 = ResolutionNode(content="a", path=("items", 0))
        child2 = ResolutionNode(content="b", path=("items", 1))
        node = ResolutionNode(content=[child1, child2], path=("items",))
        node.type_chains = [(TypeInfo(type_=list),)]

        FactorySystem.apply(node)
        assert node.value == ["a", "b"]

        # From tuple
        node2 = ResolutionNode(content=[child1, child2], path=("items",))
        node2.type_chains = [(TypeInfo(type_=List[str]),)]
        # Mock as tuple for testing
        child1.value = "a"
        child2.value = "b"
        FactorySystem.apply(node2)
        assert isinstance(node2.value, list)

    def test_dict_conversion(self):
        """Test dict conversion."""
        child1 = ResolutionNode(content="v1", path=("map", "k1"))
        child2 = ResolutionNode(content="v2", path=("map", "k2"))
        node = ResolutionNode(content={"k1": child1, "k2": child2}, path=("map",))
        node.type_chains = [(TypeInfo(type_=dict),)]

        FactorySystem.apply(node)
        assert node.value == {"k1": "v1", "k2": "v2"}

    def test_set_conversion(self):
        """Test set conversion."""
        child1 = ResolutionNode(content="a", path=("items", 0))
        child2 = ResolutionNode(content="b", path=("items", 1))
        child3 = ResolutionNode(content="a", path=("items", 2))  # Duplicate
        node = ResolutionNode(content=[child1, child2, child3], path=("items",))
        node.type_chains = [(TypeInfo(type_=set),)]

        FactorySystem.apply(node)
        assert node.value == {"a", "b"}

    def test_tuple_conversion(self):
        """Test tuple conversion."""
        child1 = ResolutionNode(content=1, path=("coords", 0))
        child2 = ResolutionNode(content=2, path=("coords", 1))
        node = ResolutionNode(content=[child1, child2], path=("coords",))
        node.type_chains = [(TypeInfo(type_=tuple),)]

        FactorySystem.apply(node)
        assert node.value == (1, 2)

    def test_frozenset_conversion(self):
        """Test frozenset conversion."""
        child1 = ResolutionNode(content="x", path=("items", 0))
        child2 = ResolutionNode(content="y", path=("items", 1))
        node = ResolutionNode(content=[child1, child2], path=("items",))
        node.type_chains = [(TypeInfo(type_=frozenset),)]

        FactorySystem.apply(node)
        assert node.value == frozenset({"x", "y"})

    def test_mapping_proxy_conversion(self):
        """Test MappingProxyType conversion."""
        child1 = ResolutionNode(content=1, path=("map", "a"))
        child2 = ResolutionNode(content=2, path=("map", "b"))
        node = ResolutionNode(content={"a": child1, "b": child2}, path=("map",))
        node.type_chains = [(TypeInfo(type_=MappingProxyType),)]

        FactorySystem.apply(node)
        assert isinstance(node.value, MappingProxyType)
        assert dict(node.value) == {"a": 1, "b": 2}

    def test_container_type_mismatch(self):
        """Test container type mismatches."""
        # Try to create list from dict
        node = ResolutionNode(
            content={"key": ResolutionNode(content="value", path=("items", "key"))},
            path=("items",),
        )
        node.type_chains = [(TypeInfo(type_=list),)]
        with pytest.raises(ConfigFactoryError, match="Cannot create list"):
            FactorySystem.apply(node)

        # Try to create dict from list
        node = ResolutionNode(
            content=[
                ResolutionNode(content="a", path=("map", 0)),
                ResolutionNode(content="b", path=("map", 1)),
            ],
            path=("map",),
        )
        node.type_chains = [(TypeInfo(type_=dict),)]
        with pytest.raises(ConfigFactoryError, match="Cannot create dict"):
            FactorySystem.apply(node)


class TestFactorySystemDataclasses:
    """Test dataclass creation."""

    def test_simple_dataclass(self):
        """Test simple dataclass creation."""
        hostname_child = ResolutionNode(content="localhost", path=("config", "hostname"))
        hostname_child.value = "localhost"
        port_child = ResolutionNode(content=5432, path=("config", "port"))
        port_child.value = 5432

        node = ResolutionNode(
            content={"hostname": hostname_child, "port": port_child}, path=("config",)
        )
        node.type_chains = [(TypeInfo(type_=DatabaseConfig),)]

        FactorySystem.apply(node)
        assert isinstance(node.value, DatabaseConfig)
        assert node.value.hostname == "localhost"
        assert node.value.port == 5432

    def test_dataclass_with_defaults(self):
        """Test dataclass with default values."""
        hostname_child = ResolutionNode(content="localhost", path=("config", "hostname"))
        hostname_child.value = "localhost"

        node = ResolutionNode(content={"hostname": hostname_child}, path=("config",))
        node.type_chains = [(TypeInfo(type_=DatabaseConfig),)]

        FactorySystem.apply(node)
        assert isinstance(node.value, DatabaseConfig)
        assert node.value.hostname == "localhost"
        assert node.value.port == 5432  # Default value

    def test_nested_dataclass(self):
        """Test nested dataclass creation."""
        # Create inner DatabaseConfig
        inner_hostname = ResolutionNode(
            content="db.internal", path=("config", "database", "hostname")
        )
        inner_hostname.value = "db.internal"
        inner_port = ResolutionNode(content=3306, path=("config", "database", "port"))
        inner_port.value = 3306
        database_node = ResolutionNode(
            content={"hostname": inner_hostname, "port": inner_port}, path=("config", "database")
        )
        database_node.value = DatabaseConfig(hostname="db.internal", port=3306)

        # Create outer ApplicationConfig
        service_name_node = ResolutionNode(content="api-service", path=("config", "service_name"))
        service_name_node.value = "api-service"

        node = ResolutionNode(
            content={"service_name": service_name_node, "database": database_node},
            path=("config",),
        )
        node.type_chains = [(TypeInfo(type_=ApplicationConfig),)]

        FactorySystem.apply(node)
        assert isinstance(node.value, ApplicationConfig)
        assert node.value.service_name == "api-service"
        assert isinstance(node.value.database, DatabaseConfig)
        assert node.value.database.hostname == "db.internal"

    def test_dataclass_missing_required(self):
        """Test dataclass with missing required field."""
        # Missing 'hostname' field
        port_child = ResolutionNode(content=5432, path=("config", "port"))
        port_child.value = 5432

        node = ResolutionNode(content={"port": port_child}, path=("config",))
        node.type_chains = [(TypeInfo(type_=DatabaseConfig),)]

        with pytest.raises(ConfigFactoryError, match="Missing required field"):
            FactorySystem.apply(node)

    def test_dataclass_already_instance(self):
        """Test when value is already a dataclass instance."""
        existing = DatabaseConfig(hostname="db.example.com", port=3306)
        node = ResolutionNode(
            content={
                "hostname": ResolutionNode(content="db.example.com", path=("config", "hostname")),
                "port": ResolutionNode(content=3306, path=("config", "port")),
            },
            path=("config",),
        )
        node.type_chains = [(TypeInfo(type_=DatabaseConfig),)]

        FactorySystem.apply(node)
        assert node.value == existing  # Should not change the existing instance

    def test_dataclass_from_non_dict(self):
        """Test creating dataclass from non-dict raises error."""
        node = ResolutionNode(content="not_a_dict", path=("config",))
        node.type_chains = [(TypeInfo(type_=DatabaseConfig),)]

        with pytest.raises(ConfigFactoryError, match="Cannot create"):
            FactorySystem.apply(node)

    def test_dataclass_creation_error(self):
        """Test handling of dataclass creation errors."""
        # Create node with wrong type for field
        hostname_child = ResolutionNode(content=123, path=("config", "hostname"))  # Wrong type
        hostname_child.type_chains = [(TypeInfo(type_=str),)]
        FactorySystem.apply(hostname_child)

        node = ResolutionNode(content={"hostname": hostname_child}, path=("config",))
        node.type_chains = [(TypeInfo(type_=DatabaseConfig),)]

        # Should succeed as dataclass will handle conversion
        FactorySystem.apply(node)
        assert node.value.hostname == "123"  # Converted to string


class TestFactorySystemCustomTypes:
    """Test custom type handling."""

    def test_custom_factory(self):
        """Test custom factory function."""
        custom_type = CustomTypeInfo(
            type_hint=str,
            factory=lambda x: EmailValidator(f"{x}.example.com"),
            reducer=lambda x: x.domain,
        )
        type_info = TypeInfo(type_=EmailValidator, custom=custom_type)

        node = ResolutionNode(content="noreply", path=("custom",))
        node.type_chains = [(type_info,)]

        FactorySystem.apply(node)
        assert isinstance(node.value, EmailValidator)
        assert node.value.domain == "noreply.example.com"

    def test_custom_factory_error(self):
        """Test custom factory error handling."""

        def bad_factory(x):
            raise ValueError("Custom factory failed")

        custom_type = CustomTypeInfo(type_hint=str, factory=bad_factory, reducer=lambda x: x)
        type_info = TypeInfo(type_=EmailValidator, custom=custom_type)

        node = ResolutionNode(content="input", path=("custom",))
        node.type_chains = [(type_info,)]

        with pytest.raises(ConfigFactoryError, match="Custom factory failed"):
            FactorySystem.apply(node)


class TestFactorySystemTypeChains:
    """Test type chain processing."""

    def test_multiple_type_chains(self):
        """Test trying multiple type chains."""
        # First chain will fail, second should succeed
        node = ResolutionNode(content="123", path=("value",))
        node.type_chains = [
            (TypeInfo(type_=bool),),  # Will fail
            (TypeInfo(type_=int),),  # Should succeed
            (TypeInfo(type_=str),),  # Won't be tried
        ]

        FactorySystem.apply(node)
        assert node.value == 123
        assert node.type_chains == [(TypeInfo(type_=int),)]  # Only successful chain kept

    def test_any_type_fallback(self):
        """Test fallback to Any type."""
        node = ResolutionNode(
            content={"complex": ResolutionNode(content="data", path=("value", "complex"))},
            path=("value",),
        )
        node.type_chains = [
            (TypeInfo(type_=int),),  # Will fail
            (TypeInfo(type_=Any),),  # Fallback
        ]

        FactorySystem.apply(node)
        assert node.value == {"complex": "data"}
        assert node.type_chains == [(TypeInfo(type_=Any),)]

    def test_empty_type_chains(self):
        """Test with no type chains."""
        node = ResolutionNode(content="untyped", path=("value",))
        node.type_chains = []

        FactorySystem.apply(node)
        assert node.value == "untyped"

    def test_chain_transformations(self):
        """Test chain of transformations."""

        # Create a chain that transforms through multiple types
        def to_upper(x):
            return x.upper()

        custom = CustomTypeInfo(type_hint=str, factory=to_upper, reducer=lambda x: x)
        node = ResolutionNode(content="hello", path=("text",))
        node.type_chains = [(TypeInfo(type_=str), TypeInfo(type_=str, custom=custom))]

        FactorySystem.apply(node)
        assert node.value == "HELLO"

    def test_all_chains_fail(self):
        """Test when all type chains fail."""
        node = ResolutionNode(content="text", path=("value",))
        node.type_chains = [
            (TypeInfo(type_=int),),  # Will fail
            (TypeInfo(type_=float),),  # Will fail
            (TypeInfo(type_=bool),),  # Will fail
        ]

        with pytest.raises(ConfigFactoryError, match="Failed to apply any type chain"):
            FactorySystem.apply(node)


class TestFactorySystemRecursion:
    """Test recursive factory application."""

    def test_apply_to_children_first(self):
        """Test that children are factoried before parent."""
        # Create nested structure
        grandchild = ResolutionNode(content=42, path=("root", "child", "value"))
        grandchild.type_chains = [(TypeInfo(type_=int),)]

        child = ResolutionNode(content={"value": grandchild}, path=("root", "child"))
        child.type_chains = [(TypeInfo(type_=dict),)]

        root = ResolutionNode(content={"child": child}, path=("root",))
        root.type_chains = [(TypeInfo(type_=dict),)]

        FactorySystem.apply(root)

        # All nodes should be factoried
        assert root.is_factoried
        assert child.is_factoried
        assert grandchild.is_factoried

        # Values should be correct
        assert grandchild.value == 42
        assert child.value == {"value": 42}
        assert root.value == {"child": {"value": 42}}

    def test_list_children_factory(self):
        """Test factory application to list children."""
        item1 = ResolutionNode(content="1", path=("items", 0))
        item1.type_chains = [(TypeInfo(type_=int),)]

        item2 = ResolutionNode(content="2", path=("items", 1))
        item2.type_chains = [(TypeInfo(type_=int),)]

        items = ResolutionNode(content=[item1, item2], path=("items",))
        items.type_chains = [(TypeInfo(type_=list),)]

        FactorySystem.apply(items)

        assert item1.value == 1
        assert item2.value == 2
        assert items.value == [1, 2]

    def test_already_factoried(self):
        """Test that already factoried nodes are skipped."""
        node = ResolutionNode(content="test", path=("value",))
        node.value = "already_set"

        FactorySystem.apply(node)
        assert node.value == "already_set"  # Should not change

    def test_reference_node_error(self):
        """Test that reference nodes cannot be factoried."""
        node = ResolutionNode(content="ref", reference="::target", path=("ref",))

        with pytest.raises(ConfigFactoryError, match="Cannot apply factory to reference"):
            FactorySystem.apply(node)


class TestFactorySystemRegistry:
    """Test registry-based configurations with FactorySystem."""

    def test_registry_config_factory(self):
        """Test factory application with registry-based configs."""

        from omniconfig import OmniConfig
        from omniconfig.core.registry import RegistryMixin

        # Define a custom class to register
        class NetworkEndpoint:
            def __init__(self, port: int):
                self.address = f"192.168.0.1:{port}"

            def to_port(self) -> int:
                return int(self.address.split(":")[-1])

            def __eq__(self, other):
                return isinstance(other, NetworkEndpoint) and self.address == other.address

        # Register the custom type
        OmniConfig.register_type(
            NetworkEndpoint,
            type_hint=int,
            factory=NetworkEndpoint,
            reducer=lambda x: x.to_port(),
        )

        # Define FeatureFlagsConfig for optional fields
        @dataclass
        class FeatureFlagsConfig:
            feature_flags: dict[str, bool] = field(default_factory=dict)

        # Create a registry-based configuration
        class BaseServiceConfig(RegistryMixin):
            _REGISTRY_NAME_FIELD: ClassVar[str] = "service_type"
            _REGISTRY_SUBREGISTRY_FIELD: ClassVar[str] = "environment"

            @staticmethod
            def from_dict(kwargs: Dict[str, Any]):
                service_type = kwargs.pop(BaseServiceConfig._REGISTRY_NAME_FIELD, None)
                environment = kwargs.pop(BaseServiceConfig._REGISTRY_SUBREGISTRY_FIELD, "")

                if service_type:
                    cls = BaseServiceConfig.retrieve(name=service_type, subregistry=environment)
                    cls = cast(type[BaseServiceConfig], cls)
                    # Support dynamic skip field mixing
                    if "feature_flags" in kwargs:
                        cls = dataclass(
                            type(f"Feature{cls.__name__}", (FeatureFlagsConfig, cls), {}),
                            kw_only=True,
                        )
                    return cls(**kwargs)
                raise ValueError("Service type not specified")

        # Register with OmniConfig
        OmniConfig.register_type(
            BaseServiceConfig,
            type_hint=Dict,
            factory=BaseServiceConfig.from_dict,
            reducer=lambda x: {"service_type": type(x).__name__.replace("Feature", "")},
        )

        # Define and register a concrete implementation
        @BaseServiceConfig.register(name="http")
        @dataclass
        class HttpServiceConfig(BaseServiceConfig):
            endpoint: NetworkEndpoint
            timeout_seconds: int = 30

        # Build the node tree using ResolutionNode.build
        data = {
            "config": {
                "service_type": "http",
                "endpoint": 8080,
                "timeout_seconds": 60,
                "feature_flags": {"validation": True, "logging": False},
            }
        }

        # Build the tree
        root = ResolutionNode.build(
            data,
            type_infos={("config",): OmniConfig.retrieve_type_info(BaseServiceConfig)},  # type: ignore
        )

        # Apply factory to the tree
        FactorySystem.apply(root)

        # Verify the results
        assert root.is_factoried
        assert isinstance(root.content, dict)
        assert "config" in root.content

        config_node = root.content["config"]
        assert config_node.is_factoried
        # The actual class will be SkipHttpServiceConfig
        assert isinstance(config_node.value, HttpServiceConfig)
        assert isinstance(config_node.value.endpoint, NetworkEndpoint)
        assert config_node.value.endpoint.address == "192.168.0.1:8080"
        assert config_node.value.timeout_seconds == 60
        # Check mixed-in skip fields
        assert isinstance(config_node.value, FeatureFlagsConfig)
        assert config_node.value.feature_flags["validation"] is True
        assert config_node.value.feature_flags["logging"] is False

        # Cleanup
        OmniConfig.clear_type_registry()

    def test_registry_dataclass_factory(self):
        """Test factory application with registry-based dataclass."""

        from omniconfig import OmniConfig
        from omniconfig.core.registry import RegistryMixin

        # Define a custom class to register
        class NetworkEndpoint:
            def __init__(self, port: int):
                self.address = f"192.168.0.1:{port}"

            def to_port(self) -> int:
                return int(self.address.split(":")[-1])

            def __eq__(self, other):
                return isinstance(other, NetworkEndpoint) and self.address == other.address

        # Register the custom type
        OmniConfig.register_type(
            NetworkEndpoint,
            type_hint=int,
            factory=NetworkEndpoint,
            reducer=lambda x: x.to_port(),
        )

        # Define FeatureFlagsConfig for optional fields
        @dataclass
        class FeatureFlagsConfig:
            feature_flags: dict[str, bool] = field(default_factory=dict)

        # Create a registry-based configuration
        @dataclass
        class BaseServiceConfig(RegistryMixin):
            _REGISTRY_NAME_FIELD: ClassVar[str] = "service_type"
            _REGISTRY_SUBREGISTRY_FIELD: ClassVar[str] = "environment"

            name: str

            @staticmethod
            def from_dict(kwargs: Dict[str, Any]):
                service_type = kwargs.pop(BaseServiceConfig._REGISTRY_NAME_FIELD, None)
                environment = kwargs.pop(BaseServiceConfig._REGISTRY_SUBREGISTRY_FIELD, "")

                if service_type:
                    cls = BaseServiceConfig.retrieve(name=service_type, subregistry=environment)
                    cls = cast(type[BaseServiceConfig], cls)
                    # Support dynamic skip field mixing
                    if "feature_flags" in kwargs:
                        cls = dataclass(
                            type(f"Feature{cls.__name__}", (FeatureFlagsConfig, cls), {}),
                            kw_only=True,
                        )
                    return cls(**kwargs)
                raise ValueError("Service type not specified")

        # Register with OmniConfig
        OmniConfig.register_type(
            BaseServiceConfig,
            type_hint=Dict,
            factory=BaseServiceConfig.from_dict,
            reducer=lambda x: {"service_type": type(x).__name__.replace("Feature", "")},
        )

        # Define and register a concrete implementation
        @BaseServiceConfig.register(name="http")
        @dataclass
        class HttpServiceConfig(BaseServiceConfig):
            endpoint: NetworkEndpoint
            timeout_seconds: int = 30

        # Build the node tree using ResolutionNode.build
        data = {
            "config": {
                "service_type": "http",
                "name": "server",
                "endpoint": 8080,
                "timeout_seconds": 60,
                "feature_flags": {"validation": True, "logging": False},
            }
        }

        # Build the tree
        root = ResolutionNode.build(
            data,
            type_infos={("config",): OmniConfig.retrieve_type_info(BaseServiceConfig)},  # type: ignore
        )

        # Apply factory to the tree
        FactorySystem.apply(root)

        # Verify the results
        assert root.is_factoried
        assert isinstance(root.content, dict)
        assert "config" in root.content

        config_node = root.content["config"]
        assert config_node.is_factoried
        # The actual class will be SkipHttpServiceConfig
        assert isinstance(config_node.value, HttpServiceConfig)
        assert isinstance(config_node.value.name, str)
        assert isinstance(config_node.value.endpoint, NetworkEndpoint)
        assert config_node.value.name == "server"
        assert config_node.value.endpoint.address == "192.168.0.1:8080"
        assert config_node.value.timeout_seconds == 60
        # Check mixed-in skip fields
        assert isinstance(config_node.value, FeatureFlagsConfig)
        assert config_node.value.feature_flags["validation"] is True
        assert config_node.value.feature_flags["logging"] is False

        # Cleanup
        OmniConfig.clear_type_registry()


class TestFactorySystemIntegration:
    """Integration tests for FactorySystem."""

    def test_complex_nested_structure(self):
        """Test complex nested structure with mixed types."""
        # Build complex structure
        # {
        #   "configs": [
        #     {"name": "first", "value": 10},
        #     {"name": "second", "value": 20}
        #   ],
        #   "settings": {
        #     "enabled": "true",
        #     "count": "5"
        #   }
        # }

        # First config
        c1_hostname = ResolutionNode(content="primary.db", path=("root", "configs", 0, "hostname"))
        c1_hostname.type_chains = [(TypeInfo(type_=str),)]
        c1_port = ResolutionNode(content=5432, path=("root", "configs", 0, "port"))
        c1_port.type_chains = [(TypeInfo(type_=int),)]
        config1 = ResolutionNode(
            content={"hostname": c1_hostname, "port": c1_port}, path=("root", "configs", 0)
        )
        config1.type_chains = [(TypeInfo(type_=DatabaseConfig),)]

        # Second config
        c2_hostname = ResolutionNode(content="replica.db", path=("root", "configs", 1, "hostname"))
        c2_hostname.type_chains = [(TypeInfo(type_=str),)]
        c2_port = ResolutionNode(content=5433, path=("root", "configs", 1, "port"))
        c2_port.type_chains = [(TypeInfo(type_=int),)]
        config2 = ResolutionNode(
            content={"hostname": c2_hostname, "port": c2_port}, path=("root", "configs", 1)
        )
        config2.type_chains = [(TypeInfo(type_=DatabaseConfig),)]

        # Configs list
        configs = ResolutionNode(content=[config1, config2], path=("root", "configs"))
        configs.type_chains = [(TypeInfo(type_=List[DatabaseConfig]),)]

        # Settings
        enabled = ResolutionNode(content="true", path=("root", "settings", "enabled"))
        enabled.type_chains = [(TypeInfo(type_=bool),)]
        count = ResolutionNode(content="5", path=("root", "settings", "count"))
        count.type_chains = [(TypeInfo(type_=int),)]
        settings = ResolutionNode(
            content={"enabled": enabled, "count": count}, path=("root", "settings")
        )
        settings.type_chains = [(TypeInfo(type_=dict),)]

        # Root
        root = ResolutionNode(content={"configs": configs, "settings": settings}, path=("root",))
        root.type_chains = [(TypeInfo(type_=dict),)]

        # Apply factory
        FactorySystem.apply(root)

        # Verify results
        assert isinstance(root.value, dict)
        assert isinstance(root.value["configs"], list)
        assert len(root.value["configs"]) == 2
        assert isinstance(root.value["configs"][0], DatabaseConfig)
        assert root.value["configs"][0].hostname == "primary.db"
        assert root.value["configs"][0].port == 5432
        assert isinstance(root.value["configs"][1], DatabaseConfig)
        assert root.value["configs"][1].hostname == "replica.db"
        assert root.value["configs"][1].port == 5433
        assert isinstance(root.value["settings"], dict)
        assert root.value["settings"]["enabled"] is True
        assert root.value["settings"]["count"] == 5
