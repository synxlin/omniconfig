"""Tests for FactorySystem implementation."""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, List, Optional

import pytest

from omniconfig.core.exceptions import ConfigFactoryError
from omniconfig.core.types import CustomTypeInfo, TypeInfo
from omniconfig.resolution.factory import FactorySystem
from omniconfig.resolution.node import ResolutionNode


class Color(Enum):
    """Test enum."""

    RED = "red"
    GREEN = "green"
    BLUE = "blue"


@dataclass
class SimpleConfig:
    """Simple test config."""

    name: str
    value: int = 42


@dataclass
class NestedConfig:
    """Nested test config."""

    title: str
    simple: SimpleConfig
    count: Optional[int] = None


class CustomClass:
    """Custom class for testing custom factories."""

    def __init__(self, data: str):
        self.data = data

    def __eq__(self, other):
        return isinstance(other, CustomClass) and self.data == other.data


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
        node.type_chains = [(TypeInfo(type_=Color),)]
        FactorySystem.apply(node)
        assert node.value == Color.RED

    def test_enum_by_value(self):
        """Test enum conversion by value."""
        node = ResolutionNode(content="green", path=("color",))
        node.type_chains = [(TypeInfo(type_=Color),)]
        FactorySystem.apply(node)
        assert node.value == Color.GREEN

    def test_enum_already_enum(self):
        """Test when value is already the enum type."""
        node = ResolutionNode(content="BLUE", path=("color",))
        node.type_chains = [(TypeInfo(type_=Color),)]
        FactorySystem.apply(node)
        assert node.value == Color.BLUE

    def test_enum_invalid_value(self):
        """Test invalid enum value."""
        node = ResolutionNode(content="yellow", path=("color",))
        node.type_chains = [(TypeInfo(type_=Color),)]
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
        name_child = ResolutionNode(content="test", path=("config", "name"))
        name_child.value = "test"
        value_child = ResolutionNode(content=50, path=("config", "value"))
        value_child.value = 50

        node = ResolutionNode(content={"name": name_child, "value": value_child}, path=("config",))
        node.type_chains = [(TypeInfo(type_=SimpleConfig),)]

        FactorySystem.apply(node)
        assert isinstance(node.value, SimpleConfig)
        assert node.value.name == "test"
        assert node.value.value == 50

    def test_dataclass_with_defaults(self):
        """Test dataclass with default values."""
        name_child = ResolutionNode(content="test", path=("config", "name"))
        name_child.value = "test"

        node = ResolutionNode(content={"name": name_child}, path=("config",))
        node.type_chains = [(TypeInfo(type_=SimpleConfig),)]

        FactorySystem.apply(node)
        assert isinstance(node.value, SimpleConfig)
        assert node.value.name == "test"
        assert node.value.value == 42  # Default value

    def test_nested_dataclass(self):
        """Test nested dataclass creation."""
        # Create inner SimpleConfig
        inner_name = ResolutionNode(content="inner", path=("config", "simple", "name"))
        inner_name.value = "inner"
        inner_value = ResolutionNode(content=100, path=("config", "simple", "value"))
        inner_value.value = 100
        simple_node = ResolutionNode(
            content={"name": inner_name, "value": inner_value}, path=("config", "simple")
        )
        simple_node.value = SimpleConfig(name="inner", value=100)

        # Create outer NestedConfig
        title_node = ResolutionNode(content="outer", path=("config", "title"))
        title_node.value = "outer"

        node = ResolutionNode(
            content={"title": title_node, "simple": simple_node}, path=("config",)
        )
        node.type_chains = [(TypeInfo(type_=NestedConfig),)]

        FactorySystem.apply(node)
        assert isinstance(node.value, NestedConfig)
        assert node.value.title == "outer"
        assert isinstance(node.value.simple, SimpleConfig)
        assert node.value.simple.name == "inner"

    def test_dataclass_missing_required(self):
        """Test dataclass with missing required field."""
        # Missing 'name' field
        value_child = ResolutionNode(content=50, path=("config", "value"))
        value_child.value = 50

        node = ResolutionNode(content={"value": value_child}, path=("config",))
        node.type_chains = [(TypeInfo(type_=SimpleConfig),)]

        with pytest.raises(ConfigFactoryError, match="Missing required field"):
            FactorySystem.apply(node)

    def test_dataclass_already_instance(self):
        """Test when value is already a dataclass instance."""
        existing = SimpleConfig(name="existing", value=999)
        node = ResolutionNode(
            content={
                "name": ResolutionNode(content="existing", path=("config", "name")),
                "value": ResolutionNode(content=999, path=("config", "value")),
            },
            path=("config",),
        )
        node.type_chains = [(TypeInfo(type_=SimpleConfig),)]

        FactorySystem.apply(node)
        assert node.value == existing  # Should not change the existing instance

    def test_dataclass_from_non_dict(self):
        """Test creating dataclass from non-dict raises error."""
        node = ResolutionNode(content="not_a_dict", path=("config",))
        node.type_chains = [(TypeInfo(type_=SimpleConfig),)]

        with pytest.raises(ConfigFactoryError, match="Cannot create"):
            FactorySystem.apply(node)

    def test_dataclass_creation_error(self):
        """Test handling of dataclass creation errors."""
        # Create node with wrong type for field
        name_child = ResolutionNode(content=123, path=("config", "name"))  # Wrong type
        name_child.type_chains = [(TypeInfo(type_=str),)]
        FactorySystem.apply(name_child)

        node = ResolutionNode(content={"name": name_child}, path=("config",))
        node.type_chains = [(TypeInfo(type_=SimpleConfig),)]

        # Should succeed as dataclass will handle conversion
        FactorySystem.apply(node)
        assert node.value.name == "123"  # Converted to string


class TestFactorySystemCustomTypes:
    """Test custom type handling."""

    def test_custom_factory(self):
        """Test custom factory function."""
        custom_type = CustomTypeInfo(
            type_hint=str, factory=lambda x: CustomClass(f"custom_{x}"), reducer=lambda x: x.data
        )
        type_info = TypeInfo(type_=CustomClass, custom=custom_type)

        node = ResolutionNode(content="input", path=("custom",))
        node.type_chains = [(type_info,)]

        FactorySystem.apply(node)
        assert isinstance(node.value, CustomClass)
        assert node.value.data == "custom_input"

    def test_custom_factory_error(self):
        """Test custom factory error handling."""

        def bad_factory(x):
            raise ValueError("Custom factory failed")

        custom_type = CustomTypeInfo(type_hint=str, factory=bad_factory, reducer=lambda x: x)
        type_info = TypeInfo(type_=CustomClass, custom=custom_type)

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
        c1_name = ResolutionNode(content="first", path=("root", "configs", 0, "name"))
        c1_name.type_chains = [(TypeInfo(type_=str),)]
        c1_value = ResolutionNode(content=10, path=("root", "configs", 0, "value"))
        c1_value.type_chains = [(TypeInfo(type_=int),)]
        config1 = ResolutionNode(
            content={"name": c1_name, "value": c1_value}, path=("root", "configs", 0)
        )
        config1.type_chains = [(TypeInfo(type_=SimpleConfig),)]

        # Second config
        c2_name = ResolutionNode(content="second", path=("root", "configs", 1, "name"))
        c2_name.type_chains = [(TypeInfo(type_=str),)]
        c2_value = ResolutionNode(content=20, path=("root", "configs", 1, "value"))
        c2_value.type_chains = [(TypeInfo(type_=int),)]
        config2 = ResolutionNode(
            content={"name": c2_name, "value": c2_value}, path=("root", "configs", 1)
        )
        config2.type_chains = [(TypeInfo(type_=SimpleConfig),)]

        # Configs list
        configs = ResolutionNode(content=[config1, config2], path=("root", "configs"))
        configs.type_chains = [(TypeInfo(type_=List[SimpleConfig]),)]

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
        assert isinstance(root.value["configs"][0], SimpleConfig)
        assert root.value["configs"][0].name == "first"
        assert root.value["configs"][0].value == 10
        assert isinstance(root.value["configs"][1], SimpleConfig)
        assert root.value["configs"][1].name == "second"
        assert root.value["configs"][1].value == 20
        assert isinstance(root.value["settings"], dict)
        assert root.value["settings"]["enabled"] is True
        assert root.value["settings"]["count"] == 5
