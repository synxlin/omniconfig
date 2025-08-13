# Contributing to OmniConfig

Thank you for your interest in contributing to OmniConfig! We welcome contributions from everyone and are grateful for even the smallest fixes or improvements.

## Code of Conduct

By participating in this project, you agree to abide by our code of conduct:

- **Be respectful**: Treat everyone with respect and kindness
- **Be inclusive**: Welcome diverse perspectives and experiences
- **Be collaborative**: Work together to solve problems
- **Be constructive**: Provide helpful feedback and accept criticism gracefully
- **Be responsible**: Take ownership of your contributions

## How to Contribute

There are many ways to contribute to OmniConfig:

- **Report bugs**: Help us identify and fix issues
- **Suggest features**: Share ideas for new functionality
- **Improve documentation**: Fix typos, clarify explanations, add examples
- **Write tests**: Increase test coverage and improve reliability
- **Fix bugs**: Submit patches for known issues
- **Add features**: Implement new functionality
- **Review code**: Help review pull requests from other contributors

## Development Setup

### Prerequisites

- Python 3.13 or higher
- git
- uv (recommended) or pip

### Setup Instructions

1. **Fork the repository**
   ```bash
   # Click the "Fork" button on GitHub
   ```

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/omniconfig.git
   cd omniconfig
   ```

3. **Set up the development environment**
   ```bash
   # Using uv (recommended)
   uv sync
   
   # Or using pip
   pip install -e ".[dev]"
   ```

4. **Create a new branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```

5. **Make your changes**
   ```bash
   # Edit files, add features, fix bugs, etc.
   ```

6. **Run tests**
   ```bash
   # Run all tests
   pytest
   
   # Run with coverage
   pytest --cov=omniconfig --cov-report=term-missing
   
   # Run specific test file
   pytest tests/omniconfig/test_parser.py
   
   # Run specific test
   pytest tests/omniconfig/test_parser.py::TestOmniConfigParser::test_simple_config_registration
   ```

7. **Format and lint your code**
   ```bash
   # Format code
   ruff format .
   
   # Check linting
   ruff check .
   
   # Fix linting issues automatically
   ruff check --fix .
   ```

## Coding Standards

### Python Style Guide

We follow PEP 8 with the following specifications:

- **Line length**: Maximum 99 characters
- **Indentation**: 4 spaces (no tabs)
- **String formatting**: Use f-strings for formatting
- **Quotes**: Use double quotes for strings
- **Imports**: Sort imports with `ruff`

### Type Hints

All functions and methods must have type hints:

```python
def parse_config(
    config_path: Path,
    defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse configuration from file."""
    ...
```

### Docstrings

Use NumPy-style docstrings for all public functions, methods, and classes:

```python
def register_type(
    cls,
    type_: Type,
    type_hint: Any,
    factory: Callable[[Any], Any],
    reducer: Callable[[Any], Any],
) -> None:
    """Register a custom type globally.
    
    Parameters
    ----------
    type_ : Type
        The custom type to register.
    type_hint : Any
        The type hint to use for parsing.
    factory : Callable[[Any], Any]
        Function to convert from type_hint to type_.
    reducer : Callable[[Any], Any]
        Function to convert from type_ to type_hint.
        
    Raises
    ------
    TypeRegistrationError
        If the type is already registered.
        
    Examples
    --------
    >>> OmniConfig.register_type(
    ...     Path,
    ...     type_hint=str,
    ...     factory=lambda x: Path(x),
    ...     reducer=lambda x: str(x)
    ... )
    """
```

## Testing Guidelines

### Writing Tests

1. **Test file structure**: Mirror the source code structure
   - Source: `src/omniconfig/parser.py`
   - Test: `tests/omniconfig/test_parser.py`

2. **Test naming**: Use descriptive names
   ```python
   def test_simple_config_registration():
       """Test registering a simple configuration."""
       
   def test_multiple_config_registration_with_different_scopes():
       """Test registering multiple configurations with different scopes."""
   ```

3. **Test coverage**: Aim for >99% coverage
   - Test both success and failure cases
   - Test edge cases and boundary conditions
   - Test error messages

4. **Fixtures**: Use pytest fixtures for common setup
   ```python
   @pytest.fixture
   def simple_config():
       """Create a simple configuration for testing."""
       return SimpleConfig(name="test", value=42)
   ```

5. **Parametrized tests**: Use for testing multiple scenarios
   ```python
   @pytest.mark.parametrize("input,expected", [
       ("true", True),
       ("false", False),
       ("yes", True),
       ("no", False),
   ])
   def test_boolean_parsing(input, expected):
       """Test boolean value parsing."""
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=omniconfig --cov-report=html

# Run specific markers
pytest -m "not slow"

# Run in parallel (if pytest-xdist is installed)
pytest -n auto
```

## Pull Request Process

1. **Before submitting**:
   - Ensure all tests pass
   - Add tests for new functionality
   - Update documentation if needed
   - Format and lint your code
   - Write clear commit messages

2. **Pull request checklist**:
   - [ ] Code follows the project's style guidelines
   - [ ] All tests pass locally
   - [ ] Coverage remains above 99%
   - [ ] Documentation is updated (if applicable)
   - [ ] Commit messages are clear and descriptive
   - [ ] PR description explains the changes
   - [ ] PR links to related issues (if any)

3. **PR title format**:
   ```
   [Type] Brief description
   
   Types: feat, fix, docs, test, refactor, perf, style, chore
   
   Examples:
   - feat: Add support for TOML configuration files
   - fix: Resolve circular reference detection issue
   - docs: Improve README examples for custom types
   ```

4. **PR description template**:
   ```markdown
   ## Description
   Brief description of what this PR does.
   
   ## Motivation
   Why is this change needed?
   
   ## Changes
   - Change 1
   - Change 2
   
   ## Testing
   How has this been tested?
   
   ## Related Issues
   Fixes #123
   Relates to #456
   ```

## Commit Message Guidelines

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **test**: Test additions or changes
- **refactor**: Code refactoring
- **perf**: Performance improvements
- **style**: Code style changes (formatting, etc.)
- **chore**: Maintenance tasks

### Examples

```
feat(parser): add support for environment variables

Add ability to override configuration values using environment
variables with OMNICONFIG_ prefix.

Fixes #42
```

```
fix(resolution): handle empty scope references correctly

Empty scope references were not being resolved properly when
using the ::field syntax. This commit fixes the translation
logic to handle empty scopes.
```

## Issue Reporting

### Bug Reports

When reporting bugs, please include:

1. **System information**:
   - OmniConfig version
   - Python version
   - Operating system

2. **Minimal reproducible example**:
   ```python
   # Code that reproduces the issue
   ```

3. **Expected behavior**: What should happen

4. **Actual behavior**: What actually happens

5. **Error messages**: Full traceback if applicable

### Feature Requests

When requesting features:

1. **Use case**: Describe your use case
2. **Proposed solution**: How you envision it working
3. **Alternatives**: Other solutions you've considered
4. **Examples**: Code examples of the desired API

## Documentation

### Docstring Standards

All public APIs must have comprehensive docstrings:

- **Brief description**: One-line summary
- **Parameters**: All parameters with types and descriptions
- **Returns**: Return type and description
- **Raises**: Exceptions that may be raised
- **Examples**: Usage examples when helpful

### README Updates

When adding features or changing behavior:

1. Update relevant sections in README.md
2. Add examples for new features
3. Update API reference if needed
4. Keep examples simple and runnable

### Example Documentation

When contributing examples:

1. Ensure they are self-contained and runnable
2. Include comments explaining key concepts
3. Show both basic and advanced usage
4. Test that examples actually work

## Release Process

Releases are managed by maintainers following semantic versioning:

- **Major (X.0.0)**: Breaking changes
- **Minor (0.X.0)**: New features (backward compatible)
- **Patch (0.0.X)**: Bug fixes

### Release Checklist

1. Update version in `pyproject.toml` and `src/omniconfig/__init__.py`
2. Update CHANGELOG.md
3. Run full test suite
4. Create git tag: `git tag -a v0.2.0 -m "Release version 0.2.0"`
5. Push tag: `git push origin v0.2.0`
6. Create GitHub release
7. Publish to PyPI

## Getting Help

If you need help:

1. Check the [documentation](README.md)
2. Search [existing issues](https://github.com/synxlin/omniconfig/issues)
3. Ask in [discussions](https://github.com/synxlin/omniconfig/discussions)
4. Create a new issue if needed

## Recognition

Contributors will be recognized in:

- The project's CONTRIBUTORS.md file
- Release notes for significant contributions
- GitHub's contributor graph

Thank you for contributing to OmniConfig! Your efforts help make this project better for everyone.