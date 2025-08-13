"""Tests for parsing.file_loader module."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import pytest
import yaml

from omniconfig.core.exceptions import ConfigParseError
from omniconfig.parsing.file_loader import FileLoader


class TestFileLoader:
    """Test FileLoader class."""

    def setup_method(self):
        """Setup test environment."""
        self.loader = FileLoader()

    def test_load_yaml_file(self):
        """Test loading YAML configuration file."""
        config_data = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {"username": "admin", "password": "secret"},
            },
            "features": ["feature1", "feature2"],
            "debug": True,
        }

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()

            # Load the file
            loaded = self.loader.load_file(f.name)

            assert loaded == config_data
            assert loaded["database"]["host"] == "localhost"
            assert loaded["database"]["port"] == 5432
            assert loaded["features"] == ["feature1", "feature2"]
            assert loaded["debug"] is True

    def test_load_json_file(self):
        """Test loading JSON configuration file."""
        config_data = {
            "app": {
                "name": "test-app",
                "version": "1.0.0",
                "settings": {"timeout": 30, "retries": 3},
            },
            "enabled": False,
            "items": [1, 2, 3],
        }

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            f.flush()

            # Load the file
            loaded = self.loader.load_file(f.name)

            assert loaded == config_data
            assert loaded["app"]["name"] == "test-app"
            assert loaded["app"]["settings"]["timeout"] == 30
            assert loaded["items"] == [1, 2, 3]
            assert loaded["enabled"] is False

    def test_load_with_references(self):
        """Test loading files with reference strings."""
        config_data = {
            "train": {
                "optimizer": "::shared::optimizers::adam",
                "learning_rate": 0.001,
                "dataset": {"_reference_": "::shared::datasets::imagenet", "batch_size": 32},
            }
        }

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()

            loaded = self.loader.load_file(f.name)

            assert loaded["train"]["optimizer"] == "::shared::optimizers::adam"
            assert loaded["train"]["dataset"]["_reference_"] == "::shared::datasets::imagenet"
            assert loaded["train"]["dataset"]["batch_size"] == 32

    def test_load_multiple_files(self):
        """Test loading and merging multiple configuration files."""
        base_config = {
            "app": {"name": "base", "version": "1.0"},
            "database": {"host": "localhost", "port": 5432},
        }

        override_config = {
            "app": {"name": "override"},
            "database": {"port": 3306},
            "new_field": "value",
        }

        with TemporaryDirectory() as tmpdir:
            base_file = Path(tmpdir) / "base.yaml"
            override_file = Path(tmpdir) / "override.yaml"

            with open(base_file, "w") as f:
                yaml.dump(base_config, f)

            with open(override_file, "w") as f:
                yaml.dump(override_config, f)

            # Load files
            configs = self.loader.load_with_defaults([str(base_file), str(override_file)])

            assert len(configs) == 2
            assert configs[0] == base_config
            assert configs[1] == override_config

    def test_load_nonexistent_file(self):
        """Test loading a non-existent file."""
        with pytest.raises(ConfigParseError) as exc_info:
            self.loader.load_file("/nonexistent/path/config.yaml")
        assert "not found" in str(exc_info.value)

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML file."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()

            with pytest.raises(ConfigParseError) as exc_info:
                self.loader.load_file(f.name)

            assert "Failed to load" in str(exc_info.value)

    def test_load_invalid_json(self):
        """Test loading invalid JSON file."""
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"invalid": "json", "missing": }')
            f.flush()

            with pytest.raises(ConfigParseError) as exc_info:
                self.loader.load_file(f.name)

            assert "Failed to load" in str(exc_info.value)

    def test_unsupported_file_format(self):
        """Test loading a file that's not a valid config format."""
        with NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("some text content")
            f.flush()

            with pytest.raises(ConfigParseError) as exc_info:
                self.loader.load_file(f.name)

            # The loader tries to parse as JSON/YAML and fails
            assert "Unsupported file type: .txt." in str(exc_info.value)

    def test_load_empty_file(self):
        """Test loading empty configuration file."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()

            loaded = self.loader.load_file(f.name)

            # Empty file should return empty dict or None
            assert loaded is None or loaded == {}

    def test_hierarchical_default_loading(self):
        """Test hierarchical default.yaml loading."""
        with TemporaryDirectory(dir=Path.cwd()) as tmpdir:
            # Create directory structure
            configs_dir = Path(tmpdir) / "configs"
            configs_dir.mkdir()

            # Create config files
            config1 = configs_dir / "__default__.yaml"
            config1.write_text(yaml.dump({"level": "first", "value": 1}))
            config2 = configs_dir / "config2.yaml"
            config2.write_text(yaml.dump({"level": "second", "value": 2}))

            # Load files
            data1, data2 = self.loader.load_with_defaults([str(config2)])

            assert data1["level"] == "first"
            assert data1["value"] == 1
            assert data2["level"] == "second"
            assert data2["value"] == 2
