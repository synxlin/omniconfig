"""Tests for the main OmniConfigParser."""

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Union, cast

import pytest
import yaml

from omniconfig import OmniConfig, OmniConfigParser
from omniconfig.core.exceptions import CircularReferenceError, ConfigError


class DatabaseConnection:
    """Database connection for testing type registration."""

    def __init__(self, host: str = "localhost", port: int = 5432):
        self.host = host
        self.port = port

    def __eq__(self, other):
        if not isinstance(other, DatabaseConnection):
            return False
        return self.host == other.host and self.port == other.port

    def __repr__(self):
        return f"DatabaseConnection(host={self.host}, port={self.port})"


@dataclass
class ServerConfig:
    """Server configuration for basic tests."""

    hostname: str = "localhost"
    port: int = 8080
    is_enabled: bool = True
    timeout_seconds: float = 30.0


@dataclass
class CacheConfig:
    """Cache configuration for nested tests."""

    cache_name: str = "default_cache"
    max_entries: int = 1000
    is_active: bool = False


@dataclass
class MicroserviceConfig:
    """Microservice configuration with nested components."""

    service_name: str = "api-service"
    server: ServerConfig = field(default_factory=ServerConfig)
    fallback_server: Optional[ServerConfig] = None
    cache: CacheConfig = field(default_factory=CacheConfig)


@dataclass
class CloudDeploymentConfig:
    """Cloud deployment configuration with multi-tier setup."""

    deployment_name: str = "production"
    microservice: MicroserviceConfig = field(default_factory=MicroserviceConfig)
    backup_microservice: Optional[MicroserviceConfig] = None


@dataclass
class ClusterConfiguration:
    """Cluster configuration with complex type annotations."""

    # Dict with Config values
    node_configs: Dict[str, ServerConfig] = field(default_factory=dict)

    # List of Configs
    server_pool: List[ServerConfig] = field(default_factory=list)

    # List of Dict[str, str]
    environment_variables: List[Dict[str, str]] = field(default_factory=list)

    # Dict[str, List[int]]
    port_mappings: Dict[str, List[int]] = field(default_factory=dict)

    # Union types with configs
    primary_node: Union[ServerConfig, Dict[str, Any]] = field(default_factory=dict)

    # Optional complex types
    backup_nodes: Optional[Dict[str, ServerConfig]] = None


@dataclass
class LegacySystemConfig:
    """Legacy system configuration with untyped containers."""

    # Untyped dict and list
    legacy_settings: Dict = field(default_factory=dict)
    legacy_items: List = field(default_factory=list)

    # Mixed type field
    dynamic_value: Optional[Union[str, int, float]] = None

    # Untyped nested structures
    nested_config: Dict = field(default_factory=lambda: {"tier1": {"tier2": {"tier3": "legacy"}}})


@dataclass
class ProfileConfig:
    """Profile configuration for testing references."""

    base_profile: str = "default"
    extended_profile: str = "custom"
    inherited_server: Optional[ServerConfig] = None


@dataclass
class FileSystemConfig:
    """File system configuration with custom registered types."""

    base_path: Path = Path("/var/data")
    database: DatabaseConnection = field(default_factory=DatabaseConnection)
    backup_path: Optional[Path] = None
    database_pool: List[DatabaseConnection] = field(default_factory=list)
    mount_points: Dict[str, Path] = field(default_factory=dict)


@dataclass
class EnterpriseSuiteConfig:
    """Enterprise suite configuration mixing all complex features."""

    suite_name: str = "enterprise"
    microservice: MicroserviceConfig = field(default_factory=MicroserviceConfig)
    cluster: ClusterConfiguration = field(default_factory=ClusterConfiguration)
    legacy: LegacySystemConfig = field(default_factory=LegacySystemConfig)
    profiles: ProfileConfig = field(default_factory=ProfileConfig)


class TestOmniConfigParser:
    """Test suite for OmniConfigParser."""

    def setup_method(self):
        """Setup test environment."""
        # Register custom types
        OmniConfig.register_type(
            Path, type_hint=str, factory=lambda x: Path(x), reducer=lambda x: str(x)
        )

        OmniConfig.register_type(
            DatabaseConnection,
            type_hint=Dict[str, Union[str, float]],
            factory=lambda x: DatabaseConnection(**x)
            if isinstance(x, dict)
            else DatabaseConnection(),
            reducer=lambda x: {"name": x.host, "port": x.port},
        )

    def teardown_method(self):
        """Clean up after tests."""
        OmniConfig.clear_type_registry()

    # Basic Parser Tests

    def test_simple_config_registration(self):
        """Test registering a simple configuration."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="simple")

        # Parse with defaults
        config, _, _, _, _, _ = parser.parse_known_args([])
        assert isinstance(config.simple, ServerConfig)
        assert config.simple.hostname == "localhost"
        assert config.simple.port == 8080
        assert config.simple.is_enabled is True

    def test_multiple_config_registration(self):
        """Test registering multiple configurations."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="simple")
        parser.add_config(CacheConfig, scope="another")

        config, _, _, _, _, _ = parser.parse_known_args([])
        assert isinstance(config.simple, ServerConfig)
        assert config.simple.hostname == "localhost"
        assert config.another.cache_name == "default_cache"

    def test_empty_scope_config(self):
        """Test configuration with empty scope."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="")

        config, _, _, used, unused, _ = parser.parse_known_args([])
        config = config[""]
        assert isinstance(config, ServerConfig)
        assert config.hostname == "localhost"
        assert config.port == 8080
        assert config.is_enabled is True

    def test_empty_scope_exclusive(self):
        """Test that empty scope must be exclusive."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="")

        with pytest.raises(ConfigError, match="Cannot add non-empty scope"):
            parser.add_config(CacheConfig, scope="another")

    # Nested Configuration Tests

    def test_nested_config_basic(self):
        """Test basic nested configuration."""
        parser = OmniConfigParser()
        parser.add_config(MicroserviceConfig, scope="microservice")

        config, _, _, _, _, _ = parser.parse_known_args([])
        assert isinstance(config.microservice, MicroserviceConfig)
        assert config.microservice.service_name == "api-service"
        assert config.microservice.server.hostname == "localhost"
        assert config.microservice.server.port == 8080
        assert config.microservice.cache.cache_name == "default_cache"

    def test_deeply_nested_config(self):
        """Test deeply nested configuration."""
        parser = OmniConfigParser()
        parser.add_config(CloudDeploymentConfig, scope="cloud")

        config, _, _, _, _, _ = parser.parse_known_args([])
        assert isinstance(config.cloud, CloudDeploymentConfig)
        assert config.cloud.deployment_name == "production"
        assert config.cloud.microservice.service_name == "api-service"
        assert config.cloud.microservice.server.hostname == "localhost"
        assert config.cloud.microservice.server.port == 8080

    def test_nested_config_cli_override(self):
        """Test CLI override of nested configuration."""
        parser = OmniConfigParser()
        parser.add_config(MicroserviceConfig, scope="microservice")

        args = [
            "--microservice-service-name=custom_title",
            "--microservice-server-hostname=custom_name",
            "--microservice-server-port=100",
            "--microservice-cache-max-entries=50",
        ]

        config, _, _, _, _, _ = parser.parse_known_args(args)
        assert isinstance(config.microservice, MicroserviceConfig)
        assert config.microservice.service_name == "custom_title"
        assert config.microservice.server.hostname == "custom_name"
        assert config.microservice.server.port == 100
        assert config.microservice.cache.max_entries == 50

    # Complex Types Tests

    def test_dict_of_configs(self):
        """Test Dict[str, Config] type handling."""
        parser = OmniConfigParser()
        parser.add_config(ClusterConfiguration, scope="complex")

        # Create temp file with config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "complex": {
                    "node_configs": {
                        "first": {"hostname": "first_config", "port": 1},
                        "second": {"hostname": "second_config", "port": 2},
                    }
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.complex, ClusterConfiguration)
            assert len(config.complex.node_configs) == 2
            assert config.complex.node_configs["first"].hostname == "first_config"
            assert config.complex.node_configs["first"].port == 1
            assert config.complex.node_configs["second"].hostname == "second_config"
            assert config.complex.node_configs["second"].port == 2
        finally:
            Path(temp_file).unlink()

    def test_list_of_configs(self):
        """Test List[Config] type handling."""
        parser = OmniConfigParser()
        parser.add_config(ClusterConfiguration, scope="complex")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "complex": {
                    "server_pool": [
                        {"hostname": "item1", "port": 10},
                        {"hostname": "item2", "port": 20},
                        {"hostname": "item3", "port": 30},
                    ]
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.complex, ClusterConfiguration)
            assert len(config.complex.server_pool) == 3
            assert config.complex.server_pool[0].hostname == "item1"
            assert config.complex.server_pool[1].port == 20
            assert config.complex.server_pool[2].hostname == "item3"
        finally:
            Path(temp_file).unlink()

    def test_list_of_dict_str_str(self):
        """Test List[Dict[str, str]] type handling."""
        parser = OmniConfigParser()
        parser.add_config(ClusterConfiguration, scope="complex")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {
                "complex": {
                    "environment_variables": [
                        {"key1": "value1", "key2": "value2"},
                        {"key3": "value3", "key4": "value4"},
                    ]
                }
            }
            json.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.complex, ClusterConfiguration)
            assert len(config.complex.environment_variables) == 2
            assert config.complex.environment_variables[0]["key1"] == "value1"
            assert config.complex.environment_variables[1]["key3"] == "value3"
        finally:
            Path(temp_file).unlink()

    def test_dict_of_lists(self):
        """Test Dict[str, List[int]] type handling."""
        parser = OmniConfigParser()
        parser.add_config(ClusterConfiguration, scope="complex")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "complex": {
                    "port_mappings": {
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
            assert isinstance(config.complex, ClusterConfiguration)
            assert config.complex.port_mappings["odds"] == [1, 3, 5, 7]
            assert config.complex.port_mappings["evens"] == [2, 4, 6, 8]
            assert config.complex.port_mappings["primes"] == [2, 3, 5, 7, 11]
        finally:
            Path(temp_file).unlink()

    # Untyped Container Tests

    def test_untyped_dict(self):
        """Test untyped Dict handling."""
        parser = OmniConfigParser()
        parser.add_config(LegacySystemConfig, scope="legacy")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "legacy": {
                    "legacy_settings": {
                        "string_key": "string_value",
                        "int_key": 8080,
                        "list_key": [1, 2, 3],
                        "nested_key": {"inner": "value"},
                    }
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.legacy, LegacySystemConfig)
            assert config.legacy.legacy_settings["string_key"] == "string_value"
            assert config.legacy.legacy_settings["int_key"] == 8080
            assert config.legacy.legacy_settings["list_key"] == [1, 2, 3]
            assert config.legacy.legacy_settings["nested_key"]["inner"] == "value"
        finally:
            Path(temp_file).unlink()

    def test_untyped_list(self):
        """Test untyped List handling."""
        parser = OmniConfigParser()
        parser.add_config(LegacySystemConfig, scope="legacy")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {
                "legacy": {
                    "legacy_items": ["string", 8080, 3.14, True, {"key": "value"}, [1, 2, 3]]
                }
            }
            json.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.legacy, LegacySystemConfig)
            assert config.legacy.legacy_items[0] == "string"
            assert config.legacy.legacy_items[1] == 8080
            assert config.legacy.legacy_items[2] == 3.14
            assert config.legacy.legacy_items[3] is True
            assert config.legacy.legacy_items[4] == {"key": "value"}
            assert config.legacy.legacy_items[5] == [1, 2, 3]
        finally:
            Path(temp_file).unlink()

    def test_mixed_type(self):
        """Test mixed Union type handling."""
        parser = OmniConfigParser()
        parser.add_config(LegacySystemConfig, scope="legacy")

        # Test with different types
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"legacy": {"dynamic_value": "string_value"}}
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.legacy, LegacySystemConfig)
            assert config.legacy.dynamic_value == "string_value"
        finally:
            Path(temp_file).unlink()

        # Test with numeric value
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"legacy": {"dynamic_value": 8080}}
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.legacy, LegacySystemConfig)
            assert config.legacy.dynamic_value == 8080
        finally:
            Path(temp_file).unlink()

    # Reference Tests

    def test_complete_reference(self):
        """Test complete reference resolution."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="base")
        parser.add_config(ProfileConfig, scope="profile")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "base": {"hostname": "base_name", "port": 10000},
                "profile": {"base_profile": "custom_base", "inherited_server": "::base"},
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.profile, ProfileConfig)
            assert config.profile.inherited_server is not None
            assert config.profile.inherited_server.hostname == "base_name"
            assert config.profile.inherited_server.port == 10000
        finally:
            Path(temp_file).unlink()

    def test_reference_with_partial_update(self):
        """Test reference with partial field updates."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="base")
        parser.add_config(ProfileConfig, scope="profile")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "base": {"hostname": "original", "port": 50, "is_enabled": False},
                "profile": {
                    "inherited_server": {
                        "_reference_": "::base",
                        "hostname": "updated",
                        "is_enabled": True,
                    }
                },
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            # Check that reference was resolved with updates
            assert isinstance(config.profile, ProfileConfig)
            assert config.profile.inherited_server is not None
            assert config.profile.inherited_server.hostname == "updated"
            assert config.profile.inherited_server.port == 50  # Inherited from base
            assert config.profile.inherited_server.is_enabled is True  # Updated
        finally:
            Path(temp_file).unlink()

    def test_nested_references(self):
        """Test nested reference resolution."""
        parser = OmniConfigParser()
        parser.add_config(MicroserviceConfig, scope="microservice1")
        parser.add_config(MicroserviceConfig, scope="microservice2")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "microservice1": {
                    "service_name": "first",
                    "server": {"hostname": "simple", "port": 10},
                },
                "microservice2": {
                    "service_name": "second",
                    "server": {"_reference_": "::microservice1::server", "port": 20},
                },
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.microservice2, MicroserviceConfig)
            assert config.microservice2.server.hostname == "simple"  # From reference
            assert config.microservice2.server.port == 20  # Updated
        finally:
            Path(temp_file).unlink()

    def test_cross_scope_references(self):
        """Test references across different scopes."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="scope1")
        parser.add_config(ServerConfig, scope="scope2")
        parser.add_config(ServerConfig, scope="scope3")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "scope1": {"hostname": "first", "port": 1},
                "scope2": "::scope1",
                "scope3": {"_reference_": "::scope2", "hostname": "third"},
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.scope1, ServerConfig)
            assert isinstance(config.scope2, ServerConfig)
            assert isinstance(config.scope3, ServerConfig)
            assert config.scope1.hostname == "first"
            assert config.scope1.port == 1
            assert config.scope2 is config.scope1  # Exact same instance
            assert config.scope3.hostname == "third"
            assert config.scope3.port == 1
        finally:
            Path(temp_file).unlink()

    # File Loading with CLI Tests

    def test_load_yaml_with_cli_override(self):
        """Test loading YAML file with CLI overrides."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="simple")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"simple": {"hostname": "from_file", "port": 99}}
            yaml.dump(data, f)
            temp_file = f.name

        try:
            args = [temp_file, "--simple-hostname=from_cli", "--simple-is-enabled=false"]
            config, _, _, _, _, _ = parser.parse_known_args(args)
            assert isinstance(config.simple, ServerConfig)
            assert config.simple.hostname == "from_cli"  # CLI override
            assert config.simple.port == 99  # From file
            assert config.simple.is_enabled is False  # CLI override
        finally:
            Path(temp_file).unlink()

    def test_load_json_with_cli_override(self):
        """Test loading JSON file with CLI overrides."""
        parser = OmniConfigParser()
        parser.add_config(CacheConfig, scope="another")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {"another": {"cache_name": "json_label", "max_entries": 25}}
            json.dump(data, f)
            temp_file = f.name

        try:
            args = [temp_file, "--another-is-active=true"]
            config, _, _, _, _, _ = parser.parse_known_args(args)
            assert isinstance(config.another, CacheConfig)
            assert config.another.cache_name == "json_label"  # From file
            assert config.another.max_entries == 25  # From file
            assert config.another.is_active is True  # CLI override
        finally:
            Path(temp_file).unlink()

    def test_load_multiple_files(self):
        """Test loading multiple configuration files."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="simple")
        parser.add_config(CacheConfig, scope="another")

        # Create first file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"simple": {"hostname": "file1", "port": 10}}
            yaml.dump(data, f)
            file1 = f.name

        # Create second file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {"another": {"cache_name": "file2", "max_entries": 20}}
            json.dump(data, f)
            file2 = f.name

        try:
            args = [file1, file2]
            config, _, _, _, _, _ = parser.parse_known_args(args)
            assert isinstance(config.simple, ServerConfig)
            assert isinstance(config.another, CacheConfig)
            assert config.simple.hostname == "file1"
            assert config.simple.port == 10
            assert config.another.cache_name == "file2"
            assert config.another.max_entries == 20
        finally:
            Path(file1).unlink()
            Path(file2).unlink()

    def test_file_priority_order(self):
        """Test priority order: CLI > later files > earlier files."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="simple")

        # Create first file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"simple": {"hostname": "first", "port": 1, "is_enabled": True}}
            yaml.dump(data, f)
            file1 = f.name

        # Create second file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {"simple": {"hostname": "second", "port": 2}}
            yaml.dump(data, f)
            file2 = f.name

        try:
            args = [file1, file2, "--simple-hostname=cli"]
            config, _, _, _, _, _ = parser.parse_known_args(args)
            assert isinstance(config.simple, ServerConfig)
            assert config.simple.hostname == "cli"  # CLI has highest priority
            assert config.simple.port == 2  # From second file
            assert config.simple.is_enabled is True  # From first file (not overridden)
        finally:
            Path(file1).unlink()
            Path(file2).unlink()

    # Custom Type Tests

    def test_custom_type_basic(self):
        """Test custom registered type handling."""
        parser = OmniConfigParser()
        parser.add_config(FileSystemConfig, scope="filesystem")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "filesystem": {
                    "base_path": "/custom/path",
                    "database": {"host": "test_custom", "port": 314},
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.filesystem, FileSystemConfig)
            assert config.filesystem.base_path == Path("/custom/path")
            assert config.filesystem.database.host == "test_custom"
            assert config.filesystem.database.port == 314
        finally:
            Path(temp_file).unlink()

    def test_custom_type_in_containers(self):
        """Test custom types in containers."""
        parser = OmniConfigParser()
        parser.add_config(FileSystemConfig, scope="filesystem")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "filesystem": {
                    "database_pool": [
                        {"host": "item1", "port": 10},
                        {"host": "item2", "port": 20},
                    ],
                    "mount_points": {"home": "/home/user", "work": "/work/projects"},
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, _, _, _ = parser.parse_known_args([temp_file])
            assert isinstance(config.filesystem, FileSystemConfig)
            assert len(config.filesystem.database_pool) == 2
            assert config.filesystem.database_pool[0].host == "item1"
            assert config.filesystem.database_pool[1].port == 20
            assert config.filesystem.mount_points["home"] == Path("/home/user")
            assert config.filesystem.mount_points["work"] == Path("/work/projects")
        finally:
            Path(temp_file).unlink()

    # Integration Tests

    def test_mixed_complex_config(self):
        """Test configuration mixing all complex features."""
        parser = OmniConfigParser()
        parser.add_config(EnterpriseSuiteConfig, scope="enterprise")
        parser.add_config(ServerConfig, scope="shared")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "shared": {"hostname": "shared_config", "port": 42},
                "enterprise": {
                    "suite_name": "complex_test",
                    "microservice": {
                        "service_name": "nested_title",
                        "server": {"_reference_": "::shared", "port": 100},
                    },
                    "cluster": {
                        "node_configs": {
                            "key1": {"hostname": "config", "port": 1},
                            "key2": "::shared",
                        },
                        "server_pool": [{"hostname": "list_item", "port": 5}, "::shared"],
                    },
                    "legacy": {
                        "legacy_settings": {"any": "value", "nested": {"deep": True}},
                        "legacy_items": [1, "two", 3.0, {"four": 4}],
                    },
                },
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            args = [temp_file, "--enterprise-suite-name=overridden"]
            config, _, _, _, _, _ = parser.parse_known_args(args)

            assert isinstance(config.enterprise, EnterpriseSuiteConfig)
            # Check basic override
            assert config.enterprise.suite_name == "overridden"

            # Check nested reference resolution
            assert config.enterprise.microservice.server.hostname == "shared_config"
            assert config.enterprise.microservice.server.port == 100  # Updated

            # Check complex types with references
            assert config.enterprise.cluster.node_configs["key1"].hostname == "config"
            assert config.enterprise.cluster.node_configs["key2"] is config.shared  # Same instance
            assert config.enterprise.cluster.server_pool[0].hostname == "list_item"
            assert config.enterprise.cluster.server_pool[1] is config.shared  # Same instance

            # Check untyped data
            assert config.enterprise.legacy.legacy_settings["any"] == "value"
            assert config.enterprise.legacy.legacy_settings["nested"]["deep"] is True
            assert config.enterprise.legacy.legacy_items[1] == "two"
        finally:
            Path(temp_file).unlink()

    def test_empty_scope_with_references(self):
        """Test empty scope configuration with references."""
        parser = OmniConfigParser()
        parser.add_config(MicroserviceConfig, scope="")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # For empty scope, the config is at root level
            data = {
                "service_name": "root_level",
                "server": {"service_host": "simple_at_root", "port": 123},
                "cache": {"cache_name": "another_at_root", "max_entries": 456},
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            # Use empty scope reference format
            args = [temp_file, "--server-hostname=cli_override"]
            config, _, _, _, _, _ = parser.parse_known_args(args)
            config = config[""]

            assert isinstance(config, MicroserviceConfig)
            assert config.service_name == "root_level"
            assert config.server.hostname == "cli_override"
            assert config.server.port == 123
            assert config.cache.max_entries == 456
        finally:
            Path(temp_file).unlink()

    def test_circular_reference_detection(self):
        """Test that circular references are detected."""
        parser = OmniConfigParser()
        parser.add_config(ProfileConfig, scope="ref1")
        parser.add_config(ProfileConfig, scope="ref2")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "ref1": {"base_profile": "::ref2::extended_profile"},
                "ref2": {"extended_profile": "::ref1::base_profile"},
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
        parser.add_config(ServerConfig, scope="server")
        parser.add_config(MicroserviceConfig, scope="microservice")

        defaults = parser.dump_defaults()

        # Check structure
        assert "server" in defaults
        assert "microservice" in defaults

        # Check simple defaults
        assert defaults["server"]["hostname"] == "localhost"
        assert defaults["server"]["port"] == 8080
        assert defaults["server"]["is_enabled"] is True

        # Check nested defaults
        assert defaults["microservice"]["service_name"] == "api-service"
        assert defaults["microservice"]["server"]["hostname"] == "localhost"
        assert defaults["microservice"]["fallback_server"] is None

    def test_dump_defaults_to_file(self):
        """Test dumping defaults to file."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="server")

        # Test YAML output
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_file = f.name

        try:
            parser.dump_defaults(yaml_file)
            with open(yaml_file, "r") as f:
                loaded = yaml.safe_load(f)
            assert loaded["server"]["hostname"] == "localhost"
        finally:
            Path(yaml_file).unlink()

        # Test JSON output
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json_file = f.name

        try:
            parser.dump_defaults(json_file)
            with open(json_file, "r") as f:
                loaded = json.load(f)
            assert loaded["server"]["hostname"] == "localhost"
        finally:
            Path(json_file).unlink()

    def test_unknown_arguments(self):
        """Test handling of unknown arguments."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="server")

        args = ["--server-hostname=test", "--unknown=value"]
        config, _, _, _, _, unknown = parser.parse_known_args(args)
        assert isinstance(config.server, ServerConfig)
        assert config.server.hostname == "test"
        assert "--unknown=value" in unknown

    def test_extra_arguments(self):
        """Test handling of extra arguments."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="server")
        parser.add_extra_argument("--extra", type=int, default=0)

        args = ["--server-hostname=test", "--extra=42"]
        config, extra, _, _, _, _ = parser.parse_known_args(args)

        assert isinstance(config.server, ServerConfig)
        assert config.server.hostname == "test"
        assert extra.extra == 42


class TestOmniConfigParserRegistry:
    """Test suite for registry-based configurations."""

    def test_registry_based_config(self):
        """Test parser with registry-based configurations."""
        from omniconfig.core.registry import RegistryMixin

        # Define a base registry config
        class ServiceConfig(RegistryMixin):
            _REGISTRY_NAME_FIELD: ClassVar[str] = "service_type"
            _REGISTRY_SUBREGISTRY_FIELD: ClassVar[str] = "environment"

            @staticmethod
            def from_dict(kwargs: Dict[str, Any]):
                service_type = kwargs.pop(ServiceConfig._REGISTRY_NAME_FIELD, None)
                environment = kwargs.pop(ServiceConfig._REGISTRY_SUBREGISTRY_FIELD, "")

                if service_type:
                    cls = ServiceConfig.retrieve(name=service_type, subregistry=environment)
                    cls = cast(type[ServiceConfig], cls)
                    return cls(**kwargs)
                raise ValueError("Service type not specified")

        # Register with OmniConfig
        OmniConfig.register_type(
            ServiceConfig,
            type_hint=Dict[str, Any],
            factory=ServiceConfig.from_dict,
            reducer=lambda x: {"service_type": type(x).__name__.lower()},
        )

        # Define and register PostgreSQL service
        @ServiceConfig.register(name="postgres")
        @dataclass
        class PostgresConfig(ServiceConfig):
            host: str = "localhost"
            port: int = 5432
            username: str = "postgres"
            database_name: str = "app_db"

        # Define and register Redis service
        @ServiceConfig.register(name="redis")
        @dataclass
        class RedisConfig(ServiceConfig):
            host: str = "localhost"
            port: int = 6379
            ttl_seconds: int = 3600
            connection_pool_size: int = 10

        @dataclass
        class InfrastructureConfig:
            postgres_db: ServiceConfig
            redis_cache: ServiceConfig

        # Test parser with registry configs
        parser = OmniConfigParser()
        parser.add_config(InfrastructureConfig, scope="infrastructure")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "infrastructure": {
                    "postgres_db": {
                        "service_type": "postgres",
                        "host": "db.production.aws",
                        "port": 5432,
                        "database_name": "production_db",
                    },
                    "redis_cache": {
                        "service_type": "redis",
                        "host": "redis.production.aws",
                        "ttl_seconds": 7200,
                    },
                },
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, used, unused, _ = parser.parse_known_args([temp_file])

            # Verify PostgreSQL service
            assert isinstance(config.infrastructure.postgres_db, PostgresConfig)
            assert config.infrastructure.postgres_db.host == "db.production.aws"
            assert config.infrastructure.postgres_db.port == 5432
            assert config.infrastructure.postgres_db.database_name == "production_db"
            assert config.infrastructure.postgres_db.username == "postgres"  # default value

            # Verify Redis service
            assert isinstance(config.infrastructure.redis_cache, RedisConfig)
            assert config.infrastructure.redis_cache.host == "redis.production.aws"
            assert config.infrastructure.redis_cache.ttl_seconds == 7200
            assert config.infrastructure.redis_cache.port == 6379  # default value
            assert config.infrastructure.redis_cache.connection_pool_size == 10  # default value

            # Verify used and unused
            assert used == data
            assert unused == {}
        finally:
            Path(temp_file).unlink()
            OmniConfig.clear_type_registry()

    def test_registry_with_custom_types(self):
        """Test registry configs combined with custom types."""

        from omniconfig.core.registry import RegistryMixin

        # Register Path type
        OmniConfig.register_type(
            Path, type_hint=str, factory=lambda x: Path(x), reducer=lambda x: str(x)
        )

        # Define a custom ServiceEndpoint type
        class ServiceEndpoint:
            def __init__(self, url: str):
                self.url = url

            def __eq__(self, other):
                return isinstance(other, ServiceEndpoint) and self.url == other.url

        OmniConfig.register_type(
            ServiceEndpoint,
            type_hint=str,
            factory=ServiceEndpoint,
            reducer=lambda x: x.endpoint,
        )

        # Define FeatureFlagsConfig for optional fields
        @dataclass
        class FeatureFlagsConfig:
            feature_flags: dict[str, bool] = field(default_factory=dict)

        # Base registry config
        class StorageProviderConfig(RegistryMixin):
            _REGISTRY_NAME_FIELD: ClassVar[str] = "provider_type"

            @staticmethod
            def from_dict(kwargs: Dict[str, Any]):
                provider_type = kwargs.pop(StorageProviderConfig._REGISTRY_NAME_FIELD, None)

                if provider_type:
                    cls = StorageProviderConfig.retrieve(name=provider_type)
                    cls = cast(type[StorageProviderConfig], cls)
                    if "feature_flags" in kwargs:
                        cls = dataclass(
                            type(f"Feature{cls.__name__}", (FeatureFlagsConfig, cls), {}),
                            kw_only=True,
                        )
                    return cls(**kwargs)
                raise ValueError("Provider type not specified")

        OmniConfig.register_type(
            StorageProviderConfig,
            type_hint=Dict[str, Any],
            factory=StorageProviderConfig.from_dict,
            reducer=lambda x: {
                "provider_type": type(x)
                .__name__.replace("Feature", "")
                .replace("Provider", "")
                .lower()
            },
        )

        # Register implementations
        @StorageProviderConfig.register(name="local")
        @dataclass
        class LocalStorageProviderConfig(StorageProviderConfig):
            base_path: Path = Path("/var/storage")
            max_storage_gb: int = 100

        @StorageProviderConfig.register(name="aws-s3")
        @dataclass
        class AwsS3ProviderConfig(StorageProviderConfig):
            s3_bucket: str = "default-bucket"
            endpoint: ServiceEndpoint = field(
                default_factory=lambda: ServiceEndpoint("https://s3.amazonaws.com")
            )
            aws_region: str = "us-east-1"

        @dataclass
        class StorageConfiguration:
            primary: StorageProviderConfig
            backup: StorageProviderConfig

        # Test parser
        parser = OmniConfigParser()
        parser.add_config(StorageConfiguration, scope="storage")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "storage": {
                    "primary": {
                        "provider_type": "local",
                        "base_path": "/data/primary",
                        "max_storage_gb": 500,
                        "feature_flags": {"compression": True},
                    },
                    "backup": {
                        "provider_type": "aws-s3",
                        "s3_bucket": "company-backups",
                        "endpoint": "https://s3.us-west-2.amazonaws.com",
                        "aws_region": "us-west-2",
                    },
                }
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, used, unused, _ = parser.parse_known_args([temp_file])

            # Verify local storage with feature flags
            assert isinstance(config.storage, StorageConfiguration)
            assert isinstance(config.storage.primary, LocalStorageProviderConfig)
            assert config.storage.primary.base_path == Path("/data/primary")
            assert config.storage.primary.max_storage_gb == 500
            assert isinstance(config.storage.primary, FeatureFlagsConfig)
            assert config.storage.primary.feature_flags["compression"] is True

            # Verify AWS S3 storage with custom types
            assert isinstance(config.storage.backup, AwsS3ProviderConfig)
            assert config.storage.backup.s3_bucket == "company-backups"
            assert isinstance(config.storage.backup.endpoint, ServiceEndpoint)
            assert config.storage.backup.endpoint.url == "https://s3.us-west-2.amazonaws.com"
            assert config.storage.backup.aws_region == "us-west-2"

            # Verify used and unused
            assert used == data
            assert unused == {}
        finally:
            Path(temp_file).unlink()
            OmniConfig.clear_type_registry()

    def test_registry_with_references(self):
        """Test references between registry-based configs."""

        from omniconfig.core.registry import RegistryMixin

        # Define FeatureFlagsConfig for optional fields
        @dataclass
        class FeatureFlagsConfig:
            feature_flags: dict[str, bool] = field(default_factory=dict)

        # Base registry config
        @dataclass
        class ComponentConfig(RegistryMixin):
            _REGISTRY_NAME_FIELD: ClassVar[str] = "component_type"

            service_host: str

            @staticmethod
            def from_dict(kwargs: Dict[str, Any]):
                component_type = kwargs.pop(ComponentConfig._REGISTRY_NAME_FIELD, None)

                if component_type:
                    cls = ComponentConfig.retrieve(name=component_type)
                    cls = cast(type[ComponentConfig], cls)
                    if "feature_flags" in kwargs:
                        cls = dataclass(
                            type(f"Feature{cls.__name__}", (FeatureFlagsConfig, cls), {}),
                            kw_only=True,
                        )
                    return cls(**kwargs)
                raise ValueError("Component type not specified")

        OmniConfig.register_type(
            ComponentConfig,
            type_hint=Dict[str, Any],
            factory=ComponentConfig.from_dict,
            reducer=lambda x: {
                "component_type": type(x)
                .__name__.replace("Service", "")
                .replace("Collector", "")
                .lower()
            },
        )

        # Register implementations
        @ComponentConfig.register(name="logging")
        @dataclass
        class LoggingService(ComponentConfig):
            log_level: str = "INFO"
            log_format: str = "%(asctime)s - %(message)s"
            log_file_path: Optional[str] = None

        @ComponentConfig.register(name="metrics")
        @dataclass
        class MetricsCollector(ComponentConfig):
            collection_interval_seconds: int = 60
            metric_types: List[str] = field(default_factory=list)
            logging_service: Optional[LoggingService] = None

        @dataclass
        class MonitoringConfiguration:
            shared_logging: ComponentConfig
            system_metrics: ComponentConfig
            app_metrics: ComponentConfig

        # Test parser with references
        parser = OmniConfigParser()
        parser.add_config(MonitoringConfiguration, scope="monitoring")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "monitoring": {
                    "shared_logging": {
                        "component_type": "logging",
                        "service_host": "log",
                        "log_level": "DEBUG",
                        "log_file_path": "/var/log/app.log",
                    },
                    "system_metrics": {
                        "component_type": "metrics",
                        "service_host": "sys",
                        "collection_interval_seconds": 30,
                        "metric_types": ["cpu", "memory", "disk"],
                        "logging_service": "::monitoring::shared_logging",
                    },
                    "app_metrics": {
                        "component_type": "metrics",
                        "service_host": "app",
                        "collection_interval_seconds": 10,
                        "metric_types": ["requests", "errors"],
                        "logging_service": {
                            "_reference_": "::monitoring::shared_logging",
                            "log_level": "WARNING",  # Override the level
                        },
                        "feature_flags": {"enable_tracing": True, "enable_profiling": False},
                    },
                },
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            config, _, _, used, unused, _ = parser.parse_known_args([temp_file])

            assert isinstance(config.monitoring, MonitoringConfiguration)
            # Verify shared logging service
            assert isinstance(config.monitoring.shared_logging, LoggingService)
            assert config.monitoring.shared_logging.log_level == "DEBUG"
            assert config.monitoring.shared_logging.log_file_path == "/var/log/app.log"

            # Verify system metrics collector with complete reference
            assert isinstance(config.monitoring.system_metrics, MetricsCollector)
            assert config.monitoring.system_metrics.collection_interval_seconds == 30
            assert config.monitoring.system_metrics.metric_types == ["cpu", "memory", "disk"]
            assert isinstance(config.monitoring.system_metrics.logging_service, LoggingService)
            assert (
                config.monitoring.system_metrics.logging_service
                is config.monitoring.shared_logging
            )

            # Verify app metrics collector with partial reference
            assert isinstance(config.monitoring.app_metrics, MetricsCollector)
            assert config.monitoring.app_metrics.collection_interval_seconds == 10
            assert config.monitoring.app_metrics.metric_types == ["requests", "errors"]
            assert isinstance(config.monitoring.app_metrics, FeatureFlagsConfig)
            assert config.monitoring.app_metrics.feature_flags["enable_tracing"] is True
            assert config.monitoring.app_metrics.feature_flags["enable_profiling"] is False
            assert isinstance(config.monitoring.app_metrics.logging_service, LoggingService)
            assert (
                config.monitoring.app_metrics.logging_service.log_level == "WARNING"
            )  # Overridden
            assert (
                config.monitoring.app_metrics.logging_service.log_file_path == "/var/log/app.log"
            )  # Inherited

            # Verify used and unused
            assert used == data
            assert unused == {}
        finally:
            Path(temp_file).unlink()
            OmniConfig.clear_type_registry()

    def test_used_and_unused_data(self):
        """Test tracking of used and unused configuration data."""
        parser = OmniConfigParser()
        parser.add_config(ServerConfig, scope="server")
        parser.add_config(CacheConfig, scope="cache")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Add extra fields that don't exist in the config
            data = {
                "server": {"hostname": "used", "port": 10, "extra_field": "ignored"},
                "cache": {"cache_name": "test"},
            }
            yaml.dump(data, f)
            temp_file = f.name

        try:
            _, _, _, used, unused, _ = parser.parse_known_args([temp_file])

            # Check used data
            assert "server" in used
            assert used["server"]["hostname"] == "used"
            assert used["server"]["port"] == 10
            assert "cache" in used
            assert used["cache"]["cache_name"] == "test"

            # Check unused data
            assert "server" in unused
            assert unused["server"]["extra_field"] == "ignored"
        finally:
            Path(temp_file).unlink()
