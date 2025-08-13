"""Tests for the main OmniConfigParser."""

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pytest
import yaml

from omniconfig import OmniConfig, OmniConfigParser
from omniconfig.core.exceptions import CircularReferenceError, ConfigError


class CustomType:
    """Custom type for testing type registration."""

    def __init__(self, name: str = "custom", value: float = 1.0):
        self.name = name
        self.value = value

    def __eq__(self, other):
        if not isinstance(other, CustomType):
            return False
        return self.name == other.name and self.value == other.value

    def __repr__(self):
        return f"CustomType(name={self.name}, value={self.value})"


@dataclass
class SimpleConfig:
    """Simple configuration for basic tests."""

    name: str = "default"
    value: int = 42
    enabled: bool = True
    rate: float = 0.5


@dataclass
class AnotherSimpleConfig:
    """Another simple config for nested tests."""

    label: str = "label"
    count: int = 10
    active: bool = False


@dataclass
class NestedConfig:
    """Configuration with nested dataclass fields."""

    title: str = "nested"
    simple: SimpleConfig = field(default_factory=SimpleConfig)
    optional_simple: Optional[SimpleConfig] = None
    another: AnotherSimpleConfig = field(default_factory=AnotherSimpleConfig)


@dataclass
class DeeplyNestedConfig:
    """Configuration with multiple levels of nesting."""

    root_name: str = "root"
    nested: NestedConfig = field(default_factory=NestedConfig)
    optional_nested: Optional[NestedConfig] = None


@dataclass
class ComplexTypesConfig:
    """Configuration with complex type annotations."""

    # Dict with Config values
    config_map: Dict[str, SimpleConfig] = field(default_factory=dict)

    # List of Configs
    config_list: List[SimpleConfig] = field(default_factory=list)

    # List of Dict[str, str]
    string_map_list: List[Dict[str, str]] = field(default_factory=list)

    # Dict[str, List[int]]
    int_list_map: Dict[str, List[int]] = field(default_factory=dict)

    # Union types with configs
    config_or_dict: Union[SimpleConfig, Dict[str, Any]] = field(default_factory=dict)

    # Optional complex types
    optional_config_map: Optional[Dict[str, SimpleConfig]] = None


@dataclass
class UntypedConfig:
    """Configuration with untyped containers."""

    # Untyped dict and list
    data: Dict = field(default_factory=dict)
    items: List = field(default_factory=list)

    # Mixed type field
    mixed_value: Optional[Union[str, int, float]] = None

    # Untyped nested structures
    nested_data: Dict = field(default_factory=lambda: {"level1": {"level2": {"level3": "value"}}})


@dataclass
class ReferenceConfig:
    """Configuration for testing references."""

    base_value: str = "base"
    derived_value: str = "derived"
    reference_target: Optional[SimpleConfig] = None


@dataclass
class CustomTypeConfig:
    """Configuration with custom registered types."""

    path: Path = Path("/default/path")
    custom: CustomType = field(default_factory=CustomType)
    optional_path: Optional[Path] = None
    custom_list: List[CustomType] = field(default_factory=list)
    path_map: Dict[str, Path] = field(default_factory=dict)


@dataclass
class MixedComplexConfig:
    """Configuration mixing all complex features."""

    name: str = "mixed"
    nested: NestedConfig = field(default_factory=NestedConfig)
    complex_types: ComplexTypesConfig = field(default_factory=ComplexTypesConfig)
    untyped: UntypedConfig = field(default_factory=UntypedConfig)
    references: ReferenceConfig = field(default_factory=ReferenceConfig)


class TestOmniConfigParser:
    """Test suite for OmniConfigParser."""

    def setup_method(self):
        """Setup test environment."""
        # Register custom types
        OmniConfig.register_type(
            Path, type_hint=str, factory=lambda x: Path(x), reducer=lambda x: str(x)
        )

        OmniConfig.register_type(
            CustomType,
            type_hint=Dict[str, Union[str, float]],
            factory=lambda x: CustomType(**x) if isinstance(x, dict) else CustomType(),
            reducer=lambda x: {"name": x.name, "value": x.value},
        )

    def teardown_method(self):
        """Clean up after tests."""
        OmniConfig.clear_type_registry()

    # Basic Parser Tests

    def test_simple_config_registration(self):
        """Test registering a simple configuration."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="simple")

        # Parse with defaults
        config, _, _, _, _, _ = parser.parse_known_args([])
        assert config.simple.name == "default"
        assert config.simple.value == 42
        assert config.simple.enabled is True

    def test_multiple_config_registration(self):
        """Test registering multiple configurations."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="simple")
        parser.add_config(AnotherSimpleConfig, scope="another")

        config, _, _, _, _, _ = parser.parse_known_args([])
        assert config.simple.name == "default"
        assert config.another.label == "label"

    def test_empty_scope_config(self):
        """Test configuration with empty scope."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="")

        config, _, _, used, unused, _ = parser.parse_known_args([])
        assert config[""].name == "default"
        assert config[""].value == 42
        assert config[""].enabled is True

    def test_empty_scope_exclusive(self):
        """Test that empty scope must be exclusive."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="")

        with pytest.raises(ConfigError, match="Cannot add non-empty scope"):
            parser.add_config(AnotherSimpleConfig, scope="another")

    # Nested Configuration Tests

    def test_nested_config_basic(self):
        """Test basic nested configuration."""
        parser = OmniConfigParser()
        parser.add_config(NestedConfig, scope="nested")

        config, _, _, _, _, _ = parser.parse_known_args([])
        assert config.nested.title == "nested"
        assert config.nested.simple.name == "default"
        assert config.nested.simple.value == 42
        assert config.nested.another.label == "label"

    def test_deeply_nested_config(self):
        """Test deeply nested configuration."""
        parser = OmniConfigParser()
        parser.add_config(DeeplyNestedConfig, scope="deep")

        config, _, _, _, _, _ = parser.parse_known_args([])
        assert config.deep.root_name == "root"
        assert config.deep.nested.title == "nested"
        assert config.deep.nested.simple.name == "default"
        assert config.deep.nested.simple.value == 42

    def test_nested_config_cli_override(self):
        """Test CLI override of nested configuration."""
        parser = OmniConfigParser()
        parser.add_config(NestedConfig, scope="nested")

        args = [
            "--nested-title=custom_title",
            "--nested-simple-name=custom_name",
            "--nested-simple-value=100",
            "--nested-another-count=50",
        ]

        config, _, _, _, _, _ = parser.parse_known_args(args)
        assert config.nested.title == "custom_title"
        assert config.nested.simple.name == "custom_name"
        assert config.nested.simple.value == 100
        assert config.nested.another.count == 50

    # Complex Types Tests

    def test_dict_of_configs(self):
        """Test Dict[str, Config] type handling."""
        parser = OmniConfigParser()
        parser.add_config(ComplexTypesConfig, scope="complex")

        # Create temp file with config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "complex": {
                    "config_map": {
                        "first": {"name": "first_config", "value": 1},
                        "second": {"name": "second_config", "value": 2},
                    }
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert len(config.complex.config_map) == 2
            assert config.complex.config_map["first"].name == "first_config"
            assert config.complex.config_map["first"].value == 1
            assert config.complex.config_map["second"].name == "second_config"
            assert config.complex.config_map["second"].value == 2
        finally:
            Path(temp_file).unlink()

    def test_list_of_configs(self):
        """Test List[Config] type handling."""
        parser = OmniConfigParser()
        parser.add_config(ComplexTypesConfig, scope="complex")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "complex": {
                    "config_list": [
                        {"name": "item1", "value": 10},
                        {"name": "item2", "value": 20},
                        {"name": "item3", "value": 30},
                    ]
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert len(config.complex.config_list) == 3
            assert config.complex.config_list[0].name == "item1"
            assert config.complex.config_list[1].value == 20
            assert config.complex.config_list[2].name == "item3"
        finally:
            Path(temp_file).unlink()

    def test_list_of_dict_str_str(self):
        """Test List[Dict[str, str]] type handling."""
        parser = OmniConfigParser()
        parser.add_config(ComplexTypesConfig, scope="complex")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {
                "complex": {
                    "string_map_list": [
                        {"key1": "value1", "key2": "value2"},
                        {"key3": "value3", "key4": "value4"},
                    ]
                }
            }
            json.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert len(config.complex.string_map_list) == 2
            assert config.complex.string_map_list[0]["key1"] == "value1"
            assert config.complex.string_map_list[1]["key3"] == "value3"
        finally:
            Path(temp_file).unlink()

    def test_dict_of_lists(self):
        """Test Dict[str, List[int]] type handling."""
        parser = OmniConfigParser()
        parser.add_config(ComplexTypesConfig, scope="complex")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "complex": {
                    "int_list_map": {
                        "odds": [1, 3, 5, 7],
                        "evens": [2, 4, 6, 8],
                        "primes": [2, 3, 5, 7, 11],
                    }
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert config.complex.int_list_map["odds"] == [1, 3, 5, 7]
            assert config.complex.int_list_map["evens"] == [2, 4, 6, 8]
            assert config.complex.int_list_map["primes"] == [2, 3, 5, 7, 11]
        finally:
            Path(temp_file).unlink()

    # Untyped Container Tests

    def test_untyped_dict(self):
        """Test untyped Dict handling."""
        parser = OmniConfigParser()
        parser.add_config(UntypedConfig, scope="untyped")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "untyped": {
                    "data": {
                        "string_key": "string_value",
                        "int_key": 42,
                        "list_key": [1, 2, 3],
                        "nested_key": {"inner": "value"},
                    }
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert config.untyped.data["string_key"] == "string_value"
            assert config.untyped.data["int_key"] == 42
            assert config.untyped.data["list_key"] == [1, 2, 3]
            assert config.untyped.data["nested_key"]["inner"] == "value"
        finally:
            Path(temp_file).unlink()

    def test_untyped_list(self):
        """Test untyped List handling."""
        parser = OmniConfigParser()
        parser.add_config(UntypedConfig, scope="untyped")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {"untyped": {"items": ["string", 42, 3.14, True, {"key": "value"}, [1, 2, 3]]}}
            json.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert config.untyped.items[0] == "string"
            assert config.untyped.items[1] == 42
            assert config.untyped.items[2] == 3.14
            assert config.untyped.items[3] is True
            assert config.untyped.items[4] == {"key": "value"}
            assert config.untyped.items[5] == [1, 2, 3]
        finally:
            Path(temp_file).unlink()

    def test_mixed_type(self):
        """Test mixed Union type handling."""
        parser = OmniConfigParser()
        parser.add_config(UntypedConfig, scope="untyped")

        # Test with different types
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"untyped": {"mixed_value": "string_value"}}
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert config.untyped.mixed_value == "string_value"
        finally:
            Path(temp_file).unlink()

        # Test with numeric value
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"untyped": {"mixed_value": 42}}
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert config.untyped.mixed_value == 42
        finally:
            Path(temp_file).unlink()

    # Reference Tests

    def test_complete_reference(self):
        """Test complete reference resolution."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="base")
        parser.add_config(ReferenceConfig, scope="ref")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "base": {"name": "base_name", "value": 100},
                "ref": {"base_value": "custom_base", "reference_target": "::base"},
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert config.ref.reference_target.name == "base_name"
            assert config.ref.reference_target.value == 100
        finally:
            Path(temp_file).unlink()

    def test_reference_with_partial_update(self):
        """Test reference with partial field updates."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="base")
        parser.add_config(ReferenceConfig, scope="ref")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "base": {"name": "original", "value": 50, "enabled": False},
                "ref": {
                    "reference_target": {
                        "_reference_": "::base",
                        "name": "updated",
                        "enabled": True,
                    }
                },
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            # Check that reference was resolved with updates
            assert config.ref.reference_target.name == "updated"
            assert config.ref.reference_target.value == 50  # Inherited from base
            assert config.ref.reference_target.enabled is True  # Updated
        finally:
            Path(temp_file).unlink()

    def test_nested_references(self):
        """Test nested reference resolution."""
        parser = OmniConfigParser()
        parser.add_config(NestedConfig, scope="nested1")
        parser.add_config(NestedConfig, scope="nested2")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "nested1": {"title": "first", "simple": {"name": "simple1", "value": 10}},
                "nested2": {
                    "title": "second",
                    "simple": {"_reference_": "::nested1::simple", "value": 20},
                },
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert config.nested2.simple.name == "simple1"  # From reference
            assert config.nested2.simple.value == 20  # Updated
        finally:
            Path(temp_file).unlink()

    def test_cross_scope_references(self):
        """Test references across different scopes."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="scope1")
        parser.add_config(SimpleConfig, scope="scope2")
        parser.add_config(SimpleConfig, scope="scope3")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "scope1": {"name": "first", "value": 1},
                "scope2": "::scope1",
                "scope3": {"_reference_": "::scope2", "name": "third"},
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert config.scope2.name == "first"
            assert config.scope2.value == 1
            assert config.scope3.name == "third"
            assert config.scope3.value == 1
        finally:
            Path(temp_file).unlink()

    # File Loading with CLI Tests

    def test_load_yaml_with_cli_override(self):
        """Test loading YAML file with CLI overrides."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="simple")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"simple": {"name": "from_file", "value": 99}}
            yaml.dump(data, f)
            temp_file = f.name

        try:
            args = [temp_file, "--simple-name=from_cli", "--simple-enabled=false"]
            config, _, _, _, _, _ = parser.parse_known_args(args)
            assert config.simple.name == "from_cli"  # CLI override
            assert config.simple.value == 99  # From file
            assert config.simple.enabled is False  # CLI override
        finally:
            Path(temp_file).unlink()

    def test_load_json_with_cli_override(self):
        """Test loading JSON file with CLI overrides."""
        parser = OmniConfigParser()
        parser.add_config(AnotherSimpleConfig, scope="another")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {"another": {"label": "json_label", "count": 25}}
            json.dump(data, f)
            temp_file = f.name

        try:
            args = [temp_file, "--another-active=true"]
            config, _, _, _, _, _ = parser.parse_known_args(args)
            assert config.another.label == "json_label"  # From file
            assert config.another.count == 25  # From file
            assert config.another.active is True  # CLI override
        finally:
            Path(temp_file).unlink()

    def test_load_multiple_files(self):
        """Test loading multiple configuration files."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="simple")
        parser.add_config(AnotherSimpleConfig, scope="another")

        # Create first file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"simple": {"name": "file1", "value": 10}}
            yaml.dump(data, f)
            file1 = f.name

        # Create second file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {"another": {"label": "file2", "count": 20}}
            json.dump(data, f)
            file2 = f.name

        try:
            args = [file1, file2]
            config, _, _, _, _, _ = parser.parse_known_args(args)
            assert config.simple.name == "file1"
            assert config.simple.value == 10
            assert config.another.label == "file2"
            assert config.another.count == 20
        finally:
            Path(file1).unlink()
            Path(file2).unlink()

    def test_file_priority_order(self):
        """Test priority order: CLI > later files > earlier files."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="simple")

        # Create first file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"simple": {"name": "first", "value": 1, "enabled": True}}
            yaml.dump(data, f)
            file1 = f.name

        # Create second file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"simple": {"name": "second", "value": 2}}
            yaml.dump(data, f)
            file2 = f.name

        try:
            args = [file1, file2, "--simple-name=cli"]
            config, _, _, _, _, _ = parser.parse_known_args(args)
            assert config.simple.name == "cli"  # CLI has highest priority
            assert config.simple.value == 2  # From second file
            assert config.simple.enabled is True  # From first file (not overridden)
        finally:
            Path(file1).unlink()
            Path(file2).unlink()

    # Custom Type Tests

    def test_custom_type_basic(self):
        """Test custom registered type handling."""
        parser = OmniConfigParser()
        parser.add_config(CustomTypeConfig, scope="custom")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "custom": {
                    "path": "/custom/path",
                    "custom": {"name": "test_custom", "value": 3.14},
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert config.custom.path == Path("/custom/path")
            assert config.custom.custom.name == "test_custom"
            assert config.custom.custom.value == 3.14
        finally:
            Path(temp_file).unlink()

    def test_custom_type_in_containers(self):
        """Test custom types in containers."""
        parser = OmniConfigParser()
        parser.add_config(CustomTypeConfig, scope="custom")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "custom": {
                    "custom_list": [
                        {"name": "item1", "value": 1.0},
                        {"name": "item2", "value": 2.0},
                    ],
                    "path_map": {"home": "/home/user", "work": "/work/projects"},
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert len(config.custom.custom_list) == 2
            assert config.custom.custom_list[0].name == "item1"
            assert config.custom.custom_list[1].value == 2.0
            assert config.custom.path_map["home"] == Path("/home/user")
            assert config.custom.path_map["work"] == Path("/work/projects")
        finally:
            Path(temp_file).unlink()

    # Integration Tests

    def test_mixed_complex_config(self):
        """Test configuration mixing all complex features."""
        parser = OmniConfigParser()
        parser.add_config(MixedComplexConfig, scope="mixed")
        parser.add_config(SimpleConfig, scope="shared")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "shared": {"name": "shared_config", "value": 42},
                "mixed": {
                    "name": "complex_test",
                    "nested": {
                        "title": "nested_title",
                        "simple": {"_reference_": "::shared", "value": 100},
                    },
                    "complex_types": {
                        "config_map": {
                            "key1": {"name": "config1", "value": 1},
                            "key2": "::shared",
                        },
                        "config_list": [{"name": "list_item", "value": 5}, "::shared"],
                    },
                    "untyped": {
                        "data": {"any": "value", "nested": {"deep": True}},
                        "items": [1, "two", 3.0, {"four": 4}],
                    },
                },
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            args = [temp_file, "--mixed-name=overridden"]
            config, _, _, _, _, _ = parser.parse_known_args(args)

            # Check basic override
            assert config.mixed.name == "overridden"

            # Check nested reference resolution
            assert config.mixed.nested.simple.name == "shared_config"
            assert config.mixed.nested.simple.value == 100  # Updated

            # Check complex types with references
            assert config.mixed.complex_types.config_map["key1"].name == "config1"
            assert config.mixed.complex_types.config_map["key2"].name == "shared_config"
            assert config.mixed.complex_types.config_list[0].name == "list_item"
            assert config.mixed.complex_types.config_list[1].value == 42

            # Check untyped data
            assert config.mixed.untyped.data["any"] == "value"
            assert config.mixed.untyped.data["nested"]["deep"] is True
            assert config.mixed.untyped.items[1] == "two"
        finally:
            Path(temp_file).unlink()

    def test_empty_scope_with_references(self):
        """Test empty scope configuration with references."""
        parser = OmniConfigParser()
        parser.add_config(NestedConfig, scope="")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # For empty scope, the config is at root level
            data = {
                "title": "root_level",
                "simple": {"name": "simple_at_root", "value": 123},
                "another": {"label": "another_at_root", "count": 456},
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            # Use empty scope reference format
            args = [temp_file, "--simple-name=cli_override"]
            config, _, _, _, _, _ = parser.parse_known_args(args)

            assert config[""].title == "root_level"
            assert config[""].simple.name == "cli_override"
            assert config[""].simple.value == 123
            assert config[""].another.count == 456
        finally:
            Path(temp_file).unlink()

    def test_circular_reference_detection(self):
        """Test that circular references are detected."""
        parser = OmniConfigParser()
        parser.add_config(ReferenceConfig, scope="ref1")
        parser.add_config(ReferenceConfig, scope="ref2")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "ref1": {"base_value": "::ref2::derived_value"},
                "ref2": {"derived_value": "::ref1::base_value"},
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            with pytest.raises(CircularReferenceError):
                parser.parse_known_args([temp_file])
        finally:
            Path(temp_file).unlink()

    def test_dump_defaults(self):
        """Test dumping default values."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="simple")
        parser.add_config(NestedConfig, scope="nested")

        defaults = parser.dump_defaults()

        # Check structure
        assert "simple" in defaults
        assert "nested" in defaults

        # Check simple defaults
        assert defaults["simple"]["name"] == "default"
        assert defaults["simple"]["value"] == 42
        assert defaults["simple"]["enabled"] is True

        # Check nested defaults
        assert defaults["nested"]["title"] == "nested"
        assert defaults["nested"]["simple"]["name"] == "default"
        assert defaults["nested"]["optional_simple"] is None

    def test_dump_defaults_to_file(self):
        """Test dumping defaults to file."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="simple")

        # Test YAML output
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_file = f.name

        try:
            parser.dump_defaults(yaml_file)
            with open(yaml_file, "r") as f:
                loaded = yaml.safe_load(f)
            assert loaded["simple"]["name"] == "default"
        finally:
            Path(yaml_file).unlink()

        # Test JSON output
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json_file = f.name

        try:
            parser.dump_defaults(json_file)
            with open(json_file, "r") as f:
                loaded = json.load(f)
            assert loaded["simple"]["name"] == "default"
        finally:
            Path(json_file).unlink()

    def test_unknown_arguments(self):
        """Test handling of unknown arguments."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="simple")

        args = ["--simple-name=test", "--unknown=value"]
        config, _, _, _, _, unknown = parser.parse_known_args(args)

        assert config.simple.name == "test"
        assert "--unknown=value" in unknown

    def test_extra_arguments(self):
        """Test handling of extra arguments."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="simple")
        parser.add_extra_argument("--extra", type=int, default=0)

        args = ["--simple-name=test", "--extra=42"]
        config, extra, _, _, _, _ = parser.parse_known_args(args)

        assert config.simple.name == "test"
        assert extra.extra == 42

    def test_used_and_unused_data(self):
        """Test tracking of used and unused configuration data."""
        parser = OmniConfigParser()
        parser.add_config(SimpleConfig, scope="simple")
        parser.add_config(AnotherSimpleConfig, scope="another")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Add extra fields that don't exist in the config
            data = {
                "simple": {"name": "used", "value": 10, "extra_field": "ignored"},
                "another": {"label": "test"},
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, used, unused, _ = parser.parse_known_args([temp_file])

            # Check used data
            assert "simple" in used
            assert used["simple"]["name"] == "used"
            assert used["simple"]["value"] == 10

            # Check unused data
            assert "simple" in unused
            assert unused["simple"]["extra_field"] == "ignored"
        finally:
            Path(temp_file).unlink()
