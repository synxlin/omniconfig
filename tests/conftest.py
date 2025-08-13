# -*- coding: utf-8 -*-
"""Test configuration and fixtures."""

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def project_root_path():
    """Return the project root path."""
    return project_root


@pytest.fixture(scope="session")
def python_version():
    """Return the current Python version info."""
    return sys.version_info


@pytest.fixture
def supports_new_union_syntax(python_version):
    """Check if the Python version supports new union syntax (3.10+)."""
    return python_version >= (3, 10)


@pytest.fixture(autouse=True)
def clear_type_registry():
    """Clear the type registry before each test."""
    from omniconfig import OmniConfig

    OmniConfig.clear_type_registry()
    yield
    OmniConfig.clear_type_registry()
