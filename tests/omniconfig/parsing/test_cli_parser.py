"""Tests for CLI argument parsing."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

from omniconfig import OmniConfig
from omniconfig.parsing.cli_parser import CLIParser


class CustomClass:
    """Custom class for testing."""

    def __init__(self, name: str = "", value: int = 0):
        self.name = name
        self.value = value

    def __repr__(self):
        return f"CustomClass(name={self.name}, value={self.value})"


@dataclass
class SimpleConfig:
    """Simple test config."""

    name: str = "default"
    value: int = 42
    enabled: bool = False


@dataclass
class UnionConfig:
    """Config with union type."""

    typing_union: Union[str, int] = "0"
    types_union: str | int = "310"
    typing_optional: Optional[float] = None
    types_optional: float | None = None


@dataclass
class ContainerConfig:
    """Config with containers."""

    str_seq: List[str] = field(default_factory=list)
    int_map: Dict[str, int] = field(default_factory=dict)
    union_seq: List[Union[str, int]] = field(default_factory=list)
    union_map: Dict[str, Union[str, int]] = field(default_factory=dict)
    seq_or_map: Union[List[str], Dict[str, int]] = field(default_factory=list)
    untyped_seq: List = field(default_factory=list)
    untyped_map: Dict = field(default_factory=dict)
    untyped_seq_or_map: Union[List, Dict] = field(default_factory=list)
    mixed_seq_or_map: Union[List, Dict[str, int]] = field(default_factory=list)


@dataclass
class CustomConfig:
    """Config with custom class."""

    path: Path = Path("/default/path")
    custom: CustomClass = field(default_factory=CustomClass)
    optional_path: Optional[Path] = None
    optional_custom: Optional[CustomClass] = None
    union: Union[Path, CustomClass] = field(default_factory=CustomClass)


@dataclass
class NestedConfig:
    """Config with nested configclass."""

    name: str = "test"
    simple: SimpleConfig = field(default_factory=SimpleConfig)
    optional: Optional[SimpleConfig] = None
    union: Union[CustomConfig, SimpleConfig] = field(default_factory=SimpleConfig)


class TestCLIParser:
    """Test CLI argument parsing."""

    def setup_method(self):
        """Setup for tests."""
        OmniConfig.register_type(
            Path,
            type_hint=str,
            factory=lambda value: Path(value),
            reducer=lambda value: str(value),
        )

        OmniConfig.register_type(
            CustomClass,
            type_hint=Dict[str, Union[str, int]],
            factory=lambda value: CustomClass(**value),
            reducer=lambda value: {"name": value.name, "value": value.value},
        )

    # Tests for SimpleConfig
    def test_simple_config_basic(self):
        """Test basic SimpleConfig parsing."""
        parser = CLIParser()
        parser.add_config(SimpleConfig, scope="simple")

        args = parser._parser.parse_args(
            [
                "--simple-name",
                "test",
                "--simple-value",
                "100",
                "--simple-enabled",
                "true",
            ]
        )

        result = parser.parse_namespace(args)
        assert result == {"simple": {"name": "test", "value": 100, "enabled": True}}

    def test_simple_config_partial(self):
        """Test SimpleConfig with partial arguments."""
        parser = CLIParser()
        parser.add_config(SimpleConfig, scope="simple")

        args = parser._parser.parse_args(["--simple-name", "test"])

        result = parser.parse_namespace(args)
        assert result == {"simple": {"name": "test"}}

    def test_simple_config_empty_flag(self):
        """Test SimpleConfig with empty flag."""
        parser = CLIParser()
        parser.add_config(SimpleConfig, scope="simple", flag_name="")

        args = parser._parser.parse_args(["--name", "test", "--value", "100"])

        result = parser.parse_namespace(args)
        assert result == {"simple": {"name": "test", "value": 100}}

    def test_simple_config_reference(self):
        """Test SimpleConfig with reference flag."""
        parser = CLIParser()
        parser.add_config(SimpleConfig, scope="simple", flag_name="simple")

        args = parser._parser.parse_args(["--simple", "::shared::config"])

        result = parser.parse_namespace(args)
        assert result == {"simple": "::shared::config"}

    def test_simple_config_json(self):
        """Test SimpleConfig with JSON syntax."""
        parser = CLIParser()
        parser.add_config(SimpleConfig, scope="simple")

        args = parser._parser.parse_args(["--simple", '{"name": "test", "value": 100}'])

        result = parser.parse_namespace(args)
        assert result == {"simple": {"_overwrite_": True, "name": "test", "value": 100}}

    # Tests for UnionConfig
    def test_union_config_basic(self):
        """Test basic UnionConfig parsing."""
        parser = CLIParser()
        parser.add_config(UnionConfig, scope="union")

        args = parser._parser.parse_args(
            [
                "--union-typing-union",
                '"42"',
                "--union-types-union",
                "42",
                "--union-typing-optional",
                "3.14",
                "--union-types-optional",
                "none",
            ]
        )

        result = parser.parse_namespace(args)
        assert result == {
            "union": {
                "typing_union": "42",
                "types_union": 42,
                "typing_optional": 3.14,
                "types_optional": None,
            }
        }

    def test_union_config_json(self):
        """Test UnionConfig with JSON syntax."""
        parser = CLIParser()
        parser.add_config(UnionConfig, scope="union")

        args = parser._parser.parse_args(
            [
                "--union",
                '{"typing_union": 42, "types_union": "42", "typing_optional": 1.5}',
            ]
        )

        result = parser.parse_namespace(args)
        assert result == {
            "union": {
                "_overwrite_": True,
                "typing_union": 42,
                "types_union": "42",
                "typing_optional": 1.5,
            }
        }

    # Tests for ContainerConfig
    def test_container_config_str_seq(self):
        """Test ContainerConfig with string sequence."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-str-seq", "a", "b", "c"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"str_seq": ["a", "b", "c"]}}

    def test_container_config_str_seq_json(self):
        """Test ContainerConfig string sequence with JSON."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-str-seq", '["x", "y", "z"]'])

        result = parser.parse_namespace(args)
        assert result == {"container": {"str_seq": ["x", "y", "z"]}}

    def test_container_config_str_seq_index(self):
        """Test ContainerConfig string sequence with index updates."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-str-seq", "0=first", "2=third"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"str_seq": {0: "first", 2: "third"}}}

    def test_container_config_int_map(self):
        """Test ContainerConfig with int map."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-int-map", "key1=1", "key2=2"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"int_map": {"key1": 1, "key2": 2}}}

    def test_container_config_int_map_dot(self):
        """Test ContainerConfig int map with dot notation."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-int-map", "level1.level2=42"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"int_map": {"level1": {"level2": 42}}}}

    def test_container_config_union_seq(self):
        """Test ContainerConfig with union sequence."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-union-seq", "text", "123", '"123"'])

        result = parser.parse_namespace(args)
        assert result == {"container": {"union_seq": ["text", 123, "123"]}}

    def test_container_config_union_map(self):
        """Test ContainerConfig with union map."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(
            ["--container-union-map", "name=alice", "count=10", 'tag="42"']
        )

        result = parser.parse_namespace(args)
        assert result == {"container": {"union_map": {"name": "alice", "count": 10, "tag": "42"}}}

    def test_container_config_seq_or_map_list(self):
        """Test ContainerConfig seq_or_map as list."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-seq-or-map", "a", "b", "c"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"seq_or_map": ["a", "b", "c"]}}

    def test_container_config_seq_or_map_dict(self):
        """Test ContainerConfig seq_or_map as dict."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-seq-or-map", "k1=1", "k2=2"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"seq_or_map": {"k1": 1, "k2": 2}}}

    def test_container_config_seq_or_map_reference(self):
        """Test ContainerConfig seq_or_map as reference."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-seq-or-map", "::abc::path"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"seq_or_map": "::abc::path"}}

    def test_container_config_seq_or_map_reference_list(self):
        """Test ContainerConfig seq_or_map as reference."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-seq-or-map", "::abc::path", "::def::path"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"seq_or_map": ["::abc::path", "::def::path"]}}

    def test_container_config_seq_or_map_single_reference_list(self):
        """Test ContainerConfig seq_or_map as single reference list."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-seq-or-map", '["::abc::path"]'])

        result = parser.parse_namespace(args)
        assert result == {"container": {"seq_or_map": ["::abc::path"]}}

    def test_container_config_untyped_seq(self):
        """Test ContainerConfig with untyped sequence."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-untyped-seq", "1", "true", "text"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"untyped_seq": [1, True, "text"]}}

    def test_container_config_untyped_map(self):
        """Test ContainerConfig with untyped map."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(
            [
                "--container-untyped-map",
                "num=42",
                "bool=true",
                "str=hello",
                'numstr="42"',
            ]
        )

        result = parser.parse_namespace(args)
        assert result == {
            "container": {"untyped_map": {"num": 42, "bool": True, "str": "hello", "numstr": "42"}}
        }

    def test_container_config_untyped_seq_or_map_seq(self):
        """Test ContainerConfig with untyped union as list."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-untyped-seq-or-map", "1", "2", "3"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"untyped_seq_or_map": [1, 2, 3]}}

    def test_container_config_untyped_seq_or_map_map(self):
        """Test ContainerConfig with untyped union as map."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-untyped-seq-or-map", "k1=1", "k2=2"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"untyped_seq_or_map": {"k1": 1, "k2": 2}}}

    def test_container_config_untyped_seq_or_map_seq_json(self):
        """Test ContainerConfig with untyped union as list with json."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-untyped-seq-or-map", '["abc", 1]'])

        result = parser.parse_namespace(args)
        assert result == {"container": {"untyped_seq_or_map": ["abc", 1]}}

    def test_container_config_untyped_seq_or_map_seq_partial(self):
        """Test ContainerConfig with untyped container as list with updates."""  # noqa: W505
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(["--container-untyped-seq-or-map", "0=1", "1=str"])

        result = parser.parse_namespace(args)
        assert result == {"container": {"untyped_seq_or_map": {0: 1, 1: "str"}}}

    def test_container_config_mixed_seq_or_map_map_json(self):
        """Test ContainerConfig with mixed container."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(
            ["--container-mixed-seq-or-map", '{"a": 1, "b": "2", "c": "abc"}']
        )

        result = parser.parse_namespace(args)
        assert result == {
            "container": {"mixed_seq_or_map": {"_overwrite_": True, "a": 1, "b": "2", "c": "abc"}}
        }

    def test_container_config_json(self):
        """Test ContainerConfig with JSON syntax."""
        parser = CLIParser()
        parser.add_config(ContainerConfig, scope="container")

        args = parser._parser.parse_args(
            ["--container", '{"str_seq": ["a", "b"], "int_map": {"x": 1, "y": 2}}']
        )

        result = parser.parse_namespace(args)
        assert result == {
            "container": {
                "_overwrite_": True,
                "str_seq": ["a", "b"],
                "int_map": {"x": 1, "y": 2},
            }
        }

    # Tests for CustomConfig
    def test_custom_config_basic(self):
        """Test basic CustomConfig parsing."""

        parser = CLIParser()
        parser.add_config(CustomConfig, scope="custom")

        args = parser._parser.parse_args(
            [
                "--custom-path",
                "/home/user/file.txt",
                "--custom-custom",
                '{"name": "test", "value": 42}',
                "--custom-optional-path",
                "none",
                "--custom-optional-custom",
                "name=optional",
                "value=100",
            ]
        )

        result = parser.parse_namespace(args)
        assert result == {
            "custom": {
                "path": "/home/user/file.txt",
                "custom": {"_overwrite_": True, "name": "test", "value": 42},
                "optional_path": None,
                "optional_custom": {"name": "optional", "value": 100},
            }
        }

    def test_custom_config_union_path(self):
        """Test CustomConfig union with path."""

        parser = CLIParser()
        parser.add_config(CustomConfig, scope="custom")

        args = parser._parser.parse_args(["--custom-union", "/path/to/file"])

        result = parser.parse_namespace(args)
        assert result == {"custom": {"union": "/path/to/file"}}

    def test_custom_config_union_reference(self):
        """Test CustomConfig union with custom object."""

        parser = CLIParser()
        parser.add_config(CustomConfig, scope="custom")

        args = parser._parser.parse_args(["--custom-union", "::shared::custom"])

        result = parser.parse_namespace(args)
        assert result == {"custom": {"union": "::shared::custom"}}

    def test_custom_config_union_custom(self):
        """Test CustomConfig union with custom object."""

        parser = CLIParser()
        parser.add_config(CustomConfig, scope="custom")

        args = parser._parser.parse_args(["--custom-union", "name=union", "value=50"])

        result = parser.parse_namespace(args)
        assert result == {"custom": {"union": {"name": "union", "value": 50}}}

    def test_custom_config_union_custom_with_reference(self):
        """Test CustomConfig union with custom object."""

        parser = CLIParser()
        parser.add_config(CustomConfig, scope="custom")

        args = parser._parser.parse_args(
            ["--custom-union", "::shared::custom", "name=union", "value=50"]
        )

        result = parser.parse_namespace(args)
        assert result == {
            "custom": {"union": {"_reference_": "::shared::custom", "name": "union", "value": 50}}
        }

    def test_custom_config_union_custom_json(self):
        """Test CustomConfig union with custom object."""

        parser = CLIParser()
        parser.add_config(CustomConfig, scope="custom")

        args = parser._parser.parse_args(["--custom-union", '{"name": "union", "value": 50}'])

        result = parser.parse_namespace(args)
        assert result == {"custom": {"union": {"_overwrite_": True, "name": "union", "value": 50}}}

    def test_custom_config_json(self):
        """Test CustomConfig with JSON syntax."""

        parser = CLIParser()
        parser.add_config(CustomConfig, scope="custom")

        args = parser._parser.parse_args(
            [
                "--custom",
                '{"path": "/new/path", "custom": {"name": "json", "value": 99}, "optional_path": null}',  # noqa: E501
            ]
        )

        result = parser.parse_namespace(args)
        assert result == {
            "custom": {
                "_overwrite_": True,
                "path": "/new/path",
                "custom": {"name": "json", "value": 99},
                "optional_path": None,
            }
        }

    # Tests for NestedConfig
    def test_nested_config_basic(self):
        """Test basic NestedConfig parsing."""

        parser = CLIParser()
        parser.add_config(NestedConfig, scope="nested")

        args = parser._parser.parse_args(
            [
                "--nested-name",
                "test",
                "--nested-simple-name",
                "inner",
                "--nested-simple-value",
                "42",
                "--nested-simple-enabled",
                "true",
            ]
        )

        result = parser.parse_namespace(args)
        assert result == {
            "nested": {
                "name": "test",
                "simple": {"name": "inner", "value": 42, "enabled": True},
            }
        }

    def test_nested_config_reference(self):
        """Test NestedConfig with reference."""
        parser = CLIParser()
        parser.add_config(NestedConfig, scope="nested")

        args = parser._parser.parse_args(["--nested-simple", "::shared::simple"])

        result = parser.parse_namespace(args)
        assert result == {"nested": {"simple": "::shared::simple"}}

    def test_nested_config_reference_pair(self):
        """Test NestedConfig with reference."""
        parser = CLIParser()
        parser.add_config(NestedConfig, scope="nested")

        args = parser._parser.parse_args(["--nested-simple", "_reference_=::shared::simple"])

        result = parser.parse_namespace(args)
        assert result == {"nested": {"simple": {"_reference_": "::shared::simple"}}}

    def test_nested_config_reference_with_updates(self):
        """Test NestedConfig with reference and updates."""
        parser = CLIParser()
        parser.add_config(NestedConfig, scope="nested")

        args = parser._parser.parse_args(
            ["--nested-simple", "::shared::simple", "--nested-simple-value", "100"]
        )

        result = parser.parse_namespace(args)
        assert result == {"nested": {"simple": {"_reference_": "::shared::simple", "value": 100}}}

    def test_nested_config_optional(self):
        """Test NestedConfig with optional field."""
        parser = CLIParser()
        parser.add_config(NestedConfig, scope="nested")

        args = parser._parser.parse_args(
            ["--nested-optional", '{"name": "opt", "value": 123, "enabled": true}']
        )

        result = parser.parse_namespace(args)
        assert result == {
            "nested": {
                "optional": {"_overwrite_": True, "name": "opt", "value": 123, "enabled": True}
            }
        }

    def test_nested_config_union_custom(self):
        """Test NestedConfig union with CustomConfig."""
        parser = CLIParser()
        parser.add_config(NestedConfig, scope="nested")

        args = parser._parser.parse_args(
            ["--nested-union", '{"path": "/test", "custom": {"name": "c", "value": 1}}']
        )

        result = parser.parse_namespace(args)
        assert result == {
            "nested": {
                "union": {
                    "_overwrite_": True,
                    "path": "/test",
                    "custom": {"name": "c", "value": 1},
                }
            }
        }

    def test_nested_config_union_simple(self):
        """Test NestedConfig union with SimpleConfig."""
        parser = CLIParser()
        parser.add_config(NestedConfig, scope="nested")

        args = parser._parser.parse_args(
            ["--nested-union", "name=simple", "value=99", "enabled=false"]
        )

        result = parser.parse_namespace(args)
        assert result == {"nested": {"union": {"name": "simple", "value": 99, "enabled": False}}}

    def test_nested_config_json(self):
        """Test NestedConfig with JSON syntax."""
        parser = CLIParser()
        parser.add_config(NestedConfig, scope="nested")

        args = parser._parser.parse_args(
            ["--nested", '{"name": "outer", "simple": {"name": "inner", "value": 50}}']
        )

        result = parser.parse_namespace(args)
        assert result == {
            "nested": {
                "_overwrite_": True,
                "name": "outer",
                "simple": {"name": "inner", "value": 50},
            }
        }

    def test_nested_config_json_with_update(self):
        """Test NestedConfig JSON with subsequent update."""
        parser = CLIParser()
        parser.add_config(NestedConfig, scope="nested")

        args = parser._parser.parse_args(
            [
                "--nested",
                '{"name": "json", "simple": {"name": "initial", "value": 10}}',
                "--nested-simple-value",
                "20",
            ]
        )

        result = parser.parse_namespace(args)
        assert result == {
            "nested": {
                "_overwrite_": True,
                "name": "json",
                "simple": {"name": "initial", "value": 20},
            }
        }

    # Edge cases and combined tests
    def test_multiple_configs(self):
        """Test multiple configs in one parser."""
        parser = CLIParser()
        parser.add_config(SimpleConfig, scope="simple")
        parser.add_config(UnionConfig, scope="union")

        args = parser._parser.parse_args(["--simple-name", "test", "--union-typing-union", "42"])

        result = parser.parse_namespace(args)
        assert result == {"simple": {"name": "test"}, "union": {"typing_union": 42}}

    def test_empty_arguments(self):
        """Test with no arguments provided."""
        parser = CLIParser()
        parser.add_config(SimpleConfig, scope="simple")

        args = parser._parser.parse_args([])

        result = parser.parse_namespace(args)
        assert result == {}
