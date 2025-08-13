"""Tests for ResolutionNode implementation."""

from dataclasses import MISSING, dataclass, field
from typing import Dict, List, Optional

import pytest

from omniconfig.core.exceptions import ConfigParseError, ConfigReferenceError
from omniconfig.core.types import TypeInfo
from omniconfig.resolution.node import ResolutionNode


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
    optional: Optional[int] = None


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


class TestResolutionNodeCreation:
    """Test ResolutionNode creation and basic properties."""

    def test_primitive_node(self):
        """Test creating nodes with primitive content."""
        # Test integer
        node = ResolutionNode(content=42, path=("value",))
        assert node.content == 42
        assert node.value is MISSING
        assert node.name == "::value"
        assert not node.is_reference
        assert not node.is_factoried
        assert not node.is_root

        # Test string
        node = ResolutionNode(content="hello", path=("message",))
        assert node.content == "hello"
        assert node.name == "::message"

        # Test boolean
        node = ResolutionNode(content=True, path=("flag",))
        assert node.content is True

        # Test None
        node = ResolutionNode(content=None, path=("empty",))
        assert node.content is None

    def test_root_node(self):
        """Test root node creation."""
        node = ResolutionNode(content={}, path=())
        assert node.is_root
        assert node.name == ""
        assert not node.is_reference
        assert not node.is_factoried

    def test_reference_node_string(self):
        """Test reference node with string format."""
        node = ResolutionNode(content="test", reference="::shared::config", path=("ref",))
        assert node.is_reference
        assert node.reference == "::shared::config"
        assert node.content == "test"
        assert not node.is_factoried

    def test_reference_node_dict(self):
        """Test reference node with dict format."""
        node = ResolutionNode(
            content={"key": ResolutionNode(content="value", path=("ref", "key"))},
            reference="::base",
            path=("ref",),
        )
        assert node.is_reference
        assert node.reference == "::base"
        assert isinstance(node.content, dict)

    def test_invalid_reference_format(self):
        """Test invalid reference format raises error."""
        with pytest.raises(ConfigReferenceError, match="Invalid reference format"):
            ResolutionNode(content={}, reference="invalid", path=("test",))

        with pytest.raises(ConfigReferenceError, match="Reference must be a string"):
            ResolutionNode(content={}, reference=123, path=("test",))  # type: ignore

    def test_self_referencing_node(self):
        """Test that self-referencing nodes raise error."""
        with pytest.raises(ConfigReferenceError, match="cannot start with its own name"):
            ResolutionNode(content={}, reference="::test::sub", path=("test", "sub"))

    def test_dict_content_node(self):
        """Test node with dict content."""
        child1 = ResolutionNode(content="value1", path=("parent", "key1"))
        child2 = ResolutionNode(content=42, path=("parent", "key2"))
        node = ResolutionNode(content={"key1": child1, "key2": child2}, path=("parent",))
        assert isinstance(node.content, dict)
        assert len(node.content) == 2
        assert node.content["key1"] is child1
        assert node.content["key2"] is child2

    def test_list_content_node(self):
        """Test node with list content."""
        child1 = ResolutionNode(content="first", path=("items", 0))
        child2 = ResolutionNode(content="second", path=("items", 1))
        node = ResolutionNode(content=[child1, child2], path=("items",))
        assert isinstance(node.content, list)
        assert len(node.content) == 2
        assert node.content[0] is child1
        assert node.content[1] is child2

    def test_node_with_aliases(self):
        """Test node alias management."""
        node = ResolutionNode(content="test", path=("original",))
        node.aliases.add("::alias1")
        node.aliases.add("::alias2")

        assert node.matches_name("::original")
        assert node.matches_name("::alias1")
        assert node.matches_name("::alias2")
        assert not node.matches_name("::other")

    def test_factoried_node(self):
        """Test factoried node state."""
        node = ResolutionNode(
            content={"name": ResolutionNode(content="test", path=("config", "name"))},
            path=("config",),
        )
        assert not node.is_factoried

        node.value = SimpleConfig(name="test")
        assert node.is_factoried
        assert isinstance(node.value, SimpleConfig)


class TestResolutionNodeReferences:
    """Test reference handling in ResolutionNode."""

    def test_get_references_empty(self):
        """Test getting references from node without references."""
        node = ResolutionNode(content=42, path=("value",))
        assert node.get_references() == set()

    def test_get_references_single(self):
        """Test getting single reference."""
        node = ResolutionNode(content="val", reference="::shared", path=("ref",))
        assert node.get_references() == {"::shared"}

    def test_get_references_nested_dict(self):
        """Test getting references from nested dict structure."""
        child1 = ResolutionNode(content="v1", reference="::ref1", path=("root", "c1"))
        child2 = ResolutionNode(content="v2", reference="::ref2", path=("root", "c2"))
        child3 = ResolutionNode(content="v3", path=("root", "c3"))
        root = ResolutionNode(content={"c1": child1, "c2": child2, "c3": child3}, path=("root",))

        refs = root.get_references()
        assert refs == {"::ref1", "::ref2"}

    def test_get_references_nested_list(self):
        """Test getting references from nested list structure."""
        child1 = ResolutionNode(content="v1", reference="::ref1", path=("items", 0))
        child2 = ResolutionNode(content="v2", path=("items", 1))
        child3 = ResolutionNode(content="v3", reference="::ref3", path=("items", 2))
        root = ResolutionNode(content=[child1, child2, child3], path=("items",))

        refs = root.get_references()
        assert refs == {"::ref1", "::ref3"}

    def test_resolve_reference_simple(self):
        """Test simple reference resolution."""
        target = ResolutionNode(
            content={"resolved": ResolutionNode(content=True, path=("shared", "resolved"))},
            path=("shared",),
        )
        target.value = {"resolved": True}

        ref_node = ResolutionNode(content="ref", reference="::shared", path=("myref",))

        resolved = ref_node.resolve_reference(target)
        assert resolved is target
        assert "::myref" in resolved.aliases

    def test_resolve_reference_with_updates(self):
        """Test reference resolution with updates."""
        target_child = ResolutionNode(content="original", path=("base", "field"))
        target = ResolutionNode(content={"field": target_child}, path=("base",))

        update_child = ResolutionNode(content="updated", path=("ref", "field"))
        new_child = ResolutionNode(content="new", path=("ref", "extra"))
        ref_node = ResolutionNode(
            content={"field": update_child, "extra": new_child}, reference="::base", path=("ref",)
        )

        resolved = ref_node.resolve_reference(target)
        assert resolved != target  # Should be a new node
        assert isinstance(resolved.content, dict)
        assert "field" in resolved.content
        assert "extra" in resolved.content
        assert resolved.resolved == "::base"

    def test_resolve_reference_errors(self):
        """Test error cases in reference resolution."""
        target = ResolutionNode(content="target", path=("shared",))
        ref_node = ResolutionNode(content="ref", reference="::other", path=("myref",))

        # Wrong target
        with pytest.raises(ConfigReferenceError, match="does not match"):
            ref_node.resolve_reference(target)

        # Non-reference node
        non_ref = ResolutionNode(content="test", path=("normal",))
        with pytest.raises(ConfigReferenceError, match="non-reference node"):
            non_ref.resolve_reference(target)

        # Already factoried
        ref_node2 = ResolutionNode(content="ref", reference="::shared", path=("ref2",))
        ref_node2.value = "factoried"
        with pytest.raises(ConfigReferenceError, match="already been factoried"):
            ref_node2.resolve_reference(target)

        # Target is also reference
        target_ref = ResolutionNode(content="t", reference="::another", path=("shared",))
        ref_node3 = ResolutionNode(content="r", reference="::shared", path=("ref3",))
        with pytest.raises(ConfigReferenceError, match="also a reference"):
            ref_node3.resolve_reference(target_ref)


class TestResolutionNodeCopyWithUpdate:
    """Test copy_with_update functionality."""

    def test_update_with_non_dict(self):
        """Test update with non-dict content."""
        original = ResolutionNode(
            content={"key": ResolutionNode(content="value", path=("orig", "key"))}, path=("orig",)
        )
        update = ResolutionNode(content="string", path=("upd",))

        result = original.copy_with_update(update)
        assert result is update

    def test_update_dict_with_dict(self):
        """Test updating dict node with dict updates."""
        child1 = ResolutionNode(content="v1", path=("root", "k1"))
        child2 = ResolutionNode(content="v2", path=("root", "k2"))
        original = ResolutionNode(content={"k1": child1, "k2": child2}, path=("root",))

        upd_child1 = ResolutionNode(content="updated", path=("update", "k1"))
        upd_child3 = ResolutionNode(content="new", path=("update", "k3"))
        update = ResolutionNode(content={"k1": upd_child1, "k3": upd_child3}, path=("update",))

        result = original.copy_with_update(update)
        assert isinstance(result.content, dict)
        assert len(result.content) == 3
        assert "k1" in result.content  # Updated
        assert "k2" in result.content  # Preserved
        assert "k3" in result.content  # Added

    def test_update_list_with_indices(self):
        """Test updating list node with index-based updates."""
        child1 = ResolutionNode(content="first", path=("items", 0))
        child2 = ResolutionNode(content="second", path=("items", 1))
        original = ResolutionNode(content=[child1, child2], path=("items",))

        upd_child = ResolutionNode(content="updated_first", path=("update", 0))
        new_child = ResolutionNode(content="third", path=("update", 2))
        update = ResolutionNode(content={0: upd_child, 2: new_child}, path=("update",))

        result = original.copy_with_update(update)
        assert isinstance(result.content, list)
        assert len(result.content) == 3

    def test_update_with_reference_node(self):
        """Test that reference nodes cannot be used as updates."""
        original = ResolutionNode(
            content={"key": ResolutionNode(content="value", path=("orig", "key"))}, path=("orig",)
        )
        ref_update = ResolutionNode(content="ref", reference="::base", path=("upd",))

        with pytest.raises(ConfigReferenceError, match="Cannot apply a reference node"):
            original.copy_with_update(ref_update)

    def test_update_empty_dict(self):
        """Test update with empty dict content."""
        original = ResolutionNode(
            content={"key": ResolutionNode(content="value", path=("orig", "key"))}, path=("orig",)
        )
        update = ResolutionNode(content={}, path=("upd",))

        result = original.copy_with_update(update)
        assert result is update


class TestResolutionNodeMaterialize:
    """Test materialization functionality."""

    def test_materialize_primitive(self):
        """Test materializing primitive nodes."""
        node = ResolutionNode(content=42, path=("value",))
        assert node.materialize(after_factory=False) == 42
        assert node.materialize(after_factory=True) == 42

    def test_materialize_factoried(self):
        """Test materializing factoried node."""
        node = ResolutionNode(
            content={"name": ResolutionNode(content="test", path=("config", "name"))},
            path=("config",),
        )
        node.value = SimpleConfig(name="test")

        assert node.materialize(after_factory=True) == node.value
        assert isinstance(node.materialize(after_factory=False), dict)

    def test_materialize_dict(self):
        """Test materializing dict nodes."""
        child1 = ResolutionNode(content="v1", path=("root", "k1"))
        child2 = ResolutionNode(content=42, path=("root", "k2"))
        node = ResolutionNode(content={"k1": child1, "k2": child2}, path=("root",))

        result = node.materialize(after_factory=False)
        assert isinstance(result, dict)
        assert result == {"k1": "v1", "k2": 42}

    def test_materialize_list(self):
        """Test materializing list nodes."""
        child1 = ResolutionNode(content="first", path=("items", 0))
        child2 = ResolutionNode(content="second", path=("items", 1))
        node = ResolutionNode(content=[child1, child2], path=("items",))

        result = node.materialize(after_factory=False)
        assert isinstance(result, list)
        assert result == ["first", "second"]

    def test_materialize_reference(self):
        """Test materializing reference nodes."""
        node = ResolutionNode(content={}, reference="::base", path=("ref",))

        result = node.materialize(after_factory=False)
        assert isinstance(result, dict)
        assert result == {"_reference_": "::base"}

        # String reference
        node2 = ResolutionNode(content="::base", reference="::base", path=("ref2",))
        result2 = node2.materialize(after_factory=False)
        assert result2 == "::base"


class TestResolutionNodeBuild:
    """Test build functionality with type propagation."""

    def test_build_simple_dict(self):
        """Test building from simple dict."""
        node = ResolutionNode.build(
            {"name": "test", "value": 42},
            type_infos={
                ("name",): TypeInfo(type_=str),
                ("value",): TypeInfo(type_=int),
            },
        )
        assert node.is_root
        assert isinstance(node.content, dict)
        assert len(node.content) == 2

    def test_build_with_reference(self):
        """Test building with reference detection."""
        node = ResolutionNode.build(
            {"ref": {"_reference_": "::base", "extra": "value"}},
            type_infos={("ref",): TypeInfo(type_=dict), ("ref", "extra"): TypeInfo(type_=str)},
        )
        assert isinstance(node.content, dict)
        assert "ref" in node.content
        ref_node = node.content["ref"]
        assert ref_node.is_reference
        assert ref_node.reference == "::base"
        assert isinstance(ref_node.content, dict)
        assert "extra" in ref_node.content

    def test_build_nested_structure(self):
        """Test building nested dict/list structure."""
        node = ResolutionNode.build(
            {"items": [{"name": "first"}, {"name": "second"}], "count": 2},
            type_infos={
                ("items",): TypeInfo(type_=List[Dict[str, str]]),
                ("count",): TypeInfo(type_=int),
            },
        )
        assert isinstance(node.content, dict)
        assert isinstance(node.content["items"].content, list)
        assert len(node.content["items"].content) == 2

    def test_build_invalid_reference(self):
        """Test building with invalid reference format."""
        data = {"_reference_": 123}  # Invalid non-string reference
        type_infos = {}

        with pytest.raises(ConfigParseError, match="Invalid reference format"):
            ResolutionNode.build(data, type_infos=type_infos)

    def test_build_missing_type_info(self):
        """Test building when type info is missing for non-root."""
        with pytest.raises(ConfigParseError, match="No type information available"):
            # Build child directly without parent context
            ResolutionNode.build("value", type_infos={}, path=("field",))


class TestResolutionNodeSplit:
    """Test split functionality for used/unused data."""

    def test_split_non_factoried(self):
        """Test split on non-factoried node raises error."""
        node = ResolutionNode(
            content={"key": ResolutionNode(content="value", path=("test", "key"))}, path=("test",)
        )

        with pytest.raises(ConfigParseError, match="non-factoried node"):
            node.split({"key": "value"})

    def test_split_primitive(self):
        """Test split on primitive value."""
        node = ResolutionNode(content="test", path=("value",))
        node.value = "test"

        used, unused = node.split("test")
        assert used == "test"
        assert unused is MISSING

    def test_split_dataclass(self):
        """Test split with dataclass value."""
        child_name = ResolutionNode(content="test", path=("config", "name"))
        child_name.value = "test"
        child_value = ResolutionNode(content=42, path=("config", "value"))
        child_value.value = 42

        node = ResolutionNode(content={"name": child_name, "value": child_value}, path=("config",))
        node.value = SimpleConfig(name="test", value=42)

        data = {"name": "test", "value": 42, "extra": "unused"}
        used, unused = node.split(data)

        assert used == {"name": "test", "value": 42}
        assert unused == {"extra": "unused"}

    def test_split_dict_value(self):
        """Test split with dict value."""
        child1 = ResolutionNode(content="v1", path=("data", "k1"))
        child1.value = "v1"
        child2 = ResolutionNode(content="v2", path=("data", "k2"))
        child2.value = "v2"

        node = ResolutionNode(content={"k1": child1, "k2": child2}, path=("data",))
        node.value = {"k1": "v1", "k2": "v2"}

        data = {"k1": "v1", "k2": "v2", "k3": "unused"}
        used, unused = node.split(data)

        assert used == {"k1": "v1", "k2": "v2"}
        assert unused == {"k3": "unused"}

    def test_split_list_value(self):
        """Test split with list value."""
        child1 = ResolutionNode(content="first", path=("items", 0))
        child1.value = "first"
        child2 = ResolutionNode(content="second", path=("items", 1))
        child2.value = "second"

        node = ResolutionNode(content=[child1, child2], path=("items",))
        node.value = ["first", "second"]

        data = ["first", "second", "extra"]
        used, unused = node.split(data)

        assert used == {0: "first", 1: "second"}
        assert unused == {2: "extra"}

    def test_split_type_mismatch(self):
        """Test split with type mismatch raises error."""
        node = ResolutionNode(
            content={"key": ResolutionNode(content="value", path=("test", "key"))}, path=("test",)
        )
        node.value = {"dict": "value"}

        with pytest.raises(ConfigParseError, match="Expected dict"):
            node.split(["list", "data"])

    def test_split_nested_unused(self):
        """Test split with nested unused data."""
        grandchild = ResolutionNode(content="value", path=("root", "nested", "field"))
        grandchild.value = "value"
        child = ResolutionNode(content={"field": grandchild}, path=("root", "nested"))
        child.value = {"field": "value"}
        node = ResolutionNode(content={"nested": child}, path=("root",))
        node.value = {"nested": {"field": "value"}}

        data = {"nested": {"field": "value", "extra": "unused"}, "top_extra": "also_unused"}
        used, unused = node.split(data)

        assert used == {"nested": {"field": "value"}}
        assert unused == {"nested": {"extra": "unused"}, "top_extra": "also_unused"}
