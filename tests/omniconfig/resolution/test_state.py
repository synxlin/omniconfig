"""Tests for ResolutionState implementation."""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pytest

from omniconfig.core.exceptions import CircularReferenceError, ConfigReferenceError
from omniconfig.core.types import TypeSystem
from omniconfig.resolution.node import ResolutionNode
from omniconfig.resolution.state import ResolutionState


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


@dataclass
class ListConfig:
    """Config with list fields."""

    items: List[str]
    numbers: List[int] = field(default_factory=list)


@dataclass
class DictConfig:
    """Config with dict fields."""

    mapping: Dict[str, int]
    options: Dict[str, str] = field(default_factory=dict)


@dataclass
class ReferenceConfig:
    """Config for testing references."""

    base_value: str
    extra_field: Optional[str] = None


@dataclass
class MainConfig:
    """Main configuration class."""

    name: str
    simple: SimpleConfig
    reference: Optional[ReferenceConfig] = None


class TestResolutionStateInitialization:
    """Test ResolutionState initialization."""

    def test_simple_initialization(self):
        """Test basic state initialization."""
        data = {"main": {"name": "test", "simple": {"name": "inner", "value": 100}}}
        configs = {"main": MainConfig}

        state = ResolutionState(data, configs)

        assert state.root is not None
        assert isinstance(state.root, ResolutionNode)
        assert state.graph is not None
        assert len(state._configs) == 1
        assert "main" in state._configs

    def test_type_system_scanning(self):
        """Test that type system scans all configs."""
        data = {
            "config1": {"name": "test1", "value": 10},
            "config2": {"title": "test2", "simple": {"name": "inner", "value": 20}},
        }
        configs = {"config1": SimpleConfig, "config2": NestedConfig}

        type_system = TypeSystem()
        state = ResolutionState(data, configs, type_system=type_system)

        # Type system should have scanned both configs
        assert state._type_system is type_system
        # Type infos should be built for all fields
        assert ("config1", "name") in state._type_infos
        assert ("config1", "value") in state._type_infos
        assert ("config2", "title") in state._type_infos
        assert ("config2", "simple") in state._type_infos

    def test_node_tree_building(self):
        """Test node tree construction."""
        data = {
            "simple": {"name": "test", "value": 50},
            "nested": {"title": "outer", "simple": {"name": "inner", "value": 100}, "count": 5},
        }
        configs = {"simple": SimpleConfig, "nested": NestedConfig}

        state = ResolutionState(data, configs)

        # Check root structure
        assert isinstance(state.root.content, dict)
        assert "simple" in state.root.content
        assert "nested" in state.root.content

        # Check nested structure
        nested_node = state.root.content["nested"]
        assert isinstance(nested_node.content, dict)
        assert "title" in nested_node.content
        assert "simple" in nested_node.content
        assert "count" in nested_node.content

    def test_empty_data(self):
        """Test initialization with empty data."""
        data = {}
        configs = {"main": MainConfig}

        state = ResolutionState(data, configs)

        assert state.root is not None
        assert isinstance(state.root.content, dict)
        assert len(state.root.content) == 0

    def test_circular_reference_detection(self):
        """Test that circular references are detected."""
        data = {
            "ref1": {"_reference_": "::ref2", "base_value": "r1"},
            "ref2": {"_reference_": "::ref1", "base_value": "r2"},
        }
        configs = {"ref1": ReferenceConfig, "ref2": ReferenceConfig}

        with pytest.raises(CircularReferenceError):
            ResolutionState(data, configs)


class TestResolutionQueue:
    """Test resolution queue generation."""

    def test_simple_queue(self):
        """Test queue for simple configuration."""
        data = {"simple": {"name": "test", "value": 42}}
        configs = {"simple": SimpleConfig}

        state = ResolutionState(data, configs)
        queue = state.get_resolution_queue()

        assert len(queue) > 0
        # Should contain nodes for fields and parent
        assert any(isinstance(item, ResolutionNode) for item in queue)

    def test_queue_order(self):
        """Test that queue respects dependency order."""
        data = {"nested": {"title": "test", "simple": {"name": "inner", "value": 100}}}
        configs = {"nested": NestedConfig}

        state = ResolutionState(data, configs)
        queue = state.get_resolution_queue()

        # Convert queue to names for easier checking
        queue_names = []
        for item in queue:
            if isinstance(item, tuple):
                queue_names.append(item[0].name)
            else:
                queue_names.append(item.name)

        # Inner fields should come before outer
        name_idx = queue_names.index("::nested::simple::name")
        value_idx = queue_names.index("::nested::simple::value")
        simple_idx = queue_names.index("::nested::simple")
        nested_idx = queue_names.index("::nested")

        assert name_idx < simple_idx
        assert value_idx < simple_idx
        assert simple_idx < nested_idx


class TestFactoryApplication:
    """Test factory application through ResolutionState."""

    def test_apply_factory_simple(self):
        """Test applying factory to a simple node."""
        data = {"simple": {"name": "test", "value": 50}}
        configs = {"simple": SimpleConfig}

        state = ResolutionState(data, configs)

        # Get a node from the graph
        simple_node = state.graph.nodes["::simple"]
        assert not simple_node.is_factoried

        # Apply factory
        state.apply_factory(simple_node)
        assert simple_node.is_factoried
        assert isinstance(simple_node.value, SimpleConfig)
        assert simple_node.value.name == "test"
        assert simple_node.value.value == 50

    def test_apply_factory_nested(self):
        """Test applying factory to nested structures."""
        data = {
            "nested": {"title": "outer", "simple": {"name": "inner", "value": 100}, "count": 5}
        }
        configs = {"nested": NestedConfig}

        state = ResolutionState(data, configs)

        # Apply factory to inner config first
        simple_node = state.graph.nodes["::nested::simple"]
        state.apply_factory(simple_node)
        assert isinstance(simple_node.value, SimpleConfig)

        # Then apply to outer config
        nested_node = state.graph.nodes["::nested"]
        state.apply_factory(nested_node)
        assert isinstance(nested_node.value, NestedConfig)
        assert nested_node.value.simple is simple_node.value

    def test_apply_factory_with_types(self):
        """Test factory application with type chains."""
        data = {"items": {"items": ["a", "b", "c"], "numbers": [1, 2, 3]}}
        configs = {"items": ListConfig}

        state = ResolutionState(data, configs)

        # Apply factory to list fields
        items_node = state.graph.nodes["::items::items"]
        state.apply_factory(items_node)
        assert isinstance(items_node.value, list)
        assert items_node.value == ["a", "b", "c"]

        numbers_node = state.graph.nodes["::items::numbers"]
        state.apply_factory(numbers_node)
        assert isinstance(numbers_node.value, list)
        assert numbers_node.value == [1, 2, 3]


class TestReferenceResolution:
    """Test reference resolution through ResolutionState."""

    def test_resolve_simple_reference(self):
        """Test resolving a simple reference."""
        data = {
            "base": {"base_value": "original"},
            "derived": {"_reference_": "::base", "extra_field": "extra"},
        }
        configs = {"base": ReferenceConfig, "derived": ReferenceConfig}

        state = ResolutionState(data, configs)

        # Get nodes
        base_node = state.graph.nodes["::base"]
        derived_node = state.graph.nodes["::derived"]

        # Apply factory to base first
        state.apply_factory(base_node)

        # Resolve reference
        state.resolve_reference(derived_node)

        # Check that derived was updated
        updated_derived = state.graph.nodes["::derived"]
        assert updated_derived != derived_node  # Should be a new node
        assert updated_derived.name == "::derived"

    def test_resolve_reference_with_updates(self):
        """Test resolving reference with field updates."""
        data = {
            "base": {"base_value": "original", "extra_field": "base_extra"},
            "derived": {
                "_reference_": "::base",
                "base_value": "updated",
                "extra_field": "derived_extra",
            },
        }
        configs = {"base": ReferenceConfig, "derived": ReferenceConfig}

        state = ResolutionState(data, configs)

        derived_node = state.graph.nodes["::derived"]

        # Resolve reference
        state.resolve_reference(derived_node)

        # Check updated node
        updated = state.graph.nodes["::derived"]
        assert isinstance(updated.content, dict)
        # Should have updated values
        assert "base_value" in updated.content
        assert "extra_field" in updated.content

    def test_resolve_missing_target(self):
        """Test error when reference target doesn't exist."""
        data = {"ref": {"_reference_": "::nonexistent", "base_value": "test"}}
        configs = {"ref": ReferenceConfig}

        # Should fail during graph construction
        with pytest.raises(ConfigReferenceError):
            ResolutionState(data, configs)


class TestResolutionStateIntegration:
    """Integration tests for complete resolution process."""

    def test_full_resolution_simple(self):
        """Test full resolution of simple configuration."""
        data = {"main": {"name": "test", "simple": {"name": "inner", "value": 100}}}
        configs = {"main": MainConfig}

        state = ResolutionState(data, configs)
        queue = state.get_resolution_queue()

        # Process queue
        for node in queue:
            if node.is_reference:
                # Reference resolution
                state.resolve_reference(node)
            else:
                # Factory application
                state.apply_factory(node)

        # Check final state
        main_node = state.graph.nodes["::main"]
        assert main_node.is_factoried
        assert isinstance(main_node.value, MainConfig)
        assert main_node.value.name == "test"
        assert isinstance(main_node.value.simple, SimpleConfig)

    def test_full_resolution_with_references(self):
        """Test full resolution with references."""
        data = {
            "base_ref": {"base_value": "base", "extra_field": "original"},
            "main": {
                "name": "main_config",
                "simple": {"name": "simple", "value": 50},
                "reference": {"_reference_": "::base_ref", "extra_field": "updated"},
            },
        }
        configs = {"base_ref": ReferenceConfig, "main": MainConfig}

        state = ResolutionState(data, configs)
        queue = state.get_resolution_queue()

        # Process queue
        for node in queue:
            if node.is_reference:
                state.resolve_reference(node)
            else:
                state.apply_factory(node)

        # Check resolution
        main_node = state.graph.nodes["::main"]
        assert isinstance(main_node.value, MainConfig)
        assert isinstance(main_node.value.reference, ReferenceConfig)
        assert main_node.value.reference.base_value == "base"
        assert main_node.value.reference.extra_field == "updated"

    def test_complex_nested_resolution(self):
        """Test resolution of complex nested structures."""
        data = {
            "shared": {"base_value": "shared_base"},
            "config1": {
                "name": "first",
                "simple": {"name": "s1", "value": 10},
                "reference": {"_reference_": "::shared", "extra_field": "c1_extra"},
            },
            "config2": {
                "name": "second",
                "simple": {"_reference_": "::config1::simple", "value": 20},
                "reference": {"_reference_": "::shared", "extra_field": "c2_extra"},
            },
        }
        configs = {"shared": ReferenceConfig, "config1": MainConfig, "config2": MainConfig}

        state = ResolutionState(data, configs)
        queue = state.get_resolution_queue()

        # Process entire queue
        for node in queue:
            if node.is_reference:
                state.resolve_reference(node)
            else:
                state.apply_factory(node)

        # Verify config1
        config1 = state.graph.nodes["::config1"].value
        assert isinstance(config1, MainConfig)
        assert config1.name == "first"
        assert config1.simple.name == "s1"
        assert config1.simple.value == 10
        assert config1.reference is not None
        assert config1.reference.base_value == "shared_base"
        assert config1.reference.extra_field == "c1_extra"

        # Verify config2
        config2 = state.graph.nodes["::config2"].value
        assert isinstance(config2, MainConfig)
        assert config2.name == "second"
        assert config2.simple.name == "s1"  # From reference
        assert config2.simple.value == 20  # Updated
        assert config2.reference is not None
        assert config2.reference.base_value == "shared_base"
        assert config2.reference.extra_field == "c2_extra"

    def test_list_and_dict_resolution(self):
        """Test resolution with list and dict configs."""
        data = {
            "lists": {"items": ["first", "second", "third"], "numbers": [1, 2, 3, 4, 5]},
            "dicts": {
                "mapping": {"a": 1, "b": 2, "c": 3},
                "options": {"opt1": "val1", "opt2": "val2"},
            },
        }
        configs = {"lists": ListConfig, "dicts": DictConfig}

        state = ResolutionState(data, configs)
        queue = state.get_resolution_queue()

        # Process queue
        for node in queue:
            if node.is_reference:
                state.resolve_reference(node)
            else:
                state.apply_factory(node)

        # Check lists
        lists_node = state.graph.nodes["::lists"]
        assert isinstance(lists_node.value, ListConfig)
        assert lists_node.value.items == ["first", "second", "third"]
        assert lists_node.value.numbers == [1, 2, 3, 4, 5]

        # Check dicts
        dicts_node = state.graph.nodes["::dicts"]
        assert isinstance(dicts_node.value, DictConfig)
        assert dicts_node.value.mapping == {"a": 1, "b": 2, "c": 3}
        assert dicts_node.value.options == {"opt1": "val1", "opt2": "val2"}

    def test_resolution_with_custom_type_system(self):
        """Test resolution with custom type system."""
        from pathlib import Path

        # Custom type for Path
        type_system = TypeSystem()
        type_system.register(
            Path, type_hint=str, factory=lambda x: Path(x), reducer=lambda x: str(x)
        )

        @dataclass
        class PathConfig:
            name: str
            path: Path

        data = {"config": {"name": "test", "path": "/home/user/test"}}
        configs = {"config": PathConfig}

        state = ResolutionState(data, configs, type_system=type_system)
        queue = state.get_resolution_queue()

        # Process queue
        for node in queue:
            if node.is_reference:
                state.resolve_reference(node)
            else:
                state.apply_factory(node)

        # Check result
        config_node = state.graph.nodes["::config"]
        assert isinstance(config_node.value, PathConfig)
        assert config_node.value.name == "test"
        assert isinstance(config_node.value.path, Path)
        assert str(config_node.value.path) == os.sep.join(["", "home", "user", "test"])
