.PHONY: help test test-cov test-cov-html test-verbose format lint clean

# Default target - show help
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "OmniConfig Development Commands"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make test        # Run all tests"
	@echo "  make format      # Format code with black and isort"
	@echo "  make lint        # Run linting checks"

test: ## Run all tests with pytest
	@echo "Running tests..."
	@python -m pytest tests/ -v

test-cov: ## Run tests with coverage report
	@echo "Running tests with coverage..."
	@python -m pytest tests/ --cov=src/omniconfig --cov-report=term-missing --cov-report=term

test-cov-html: ## Run tests with HTML coverage report
	@echo "Generating HTML coverage report..."
	@python -m pytest tests/ --cov=src/omniconfig --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/index.html"

test-verbose: ## Run tests with verbose output
	@echo "Running tests with verbose output..."
	@python -m pytest tests/ -vvs --tb=short

format: ## Format code with black and isort
	@echo "Formatting code with black..."
	@black src/ tests/ --line-length 88
	@echo "Organizing imports with isort..."
	@isort src/ tests/ --profile black --line-length 88
	@echo "Code formatting complete!"

lint: ## Run linting checks (ruff, mypy)
	@echo "Running ruff linter..."
	@ruff check src/ tests/ || true
	@echo ""
	@echo "Running mypy type checker..."
	@mypy src/omniconfig --ignore-missing-imports || true
	@echo ""
	@echo "Linting complete!"

clean: ## Clean up generated files and caches
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@find . -type f -name "coverage.xml" -delete 2>/dev/null || true
	@echo "Cleanup complete!"

# Additional useful targets

install: ## Install the package in development mode
	@echo "Installing package in development mode..."
	@pip install -e .
	@echo "Installation complete!"

install-dev: ## Install development dependencies
	@echo "Installing development dependencies..."
	@pip install -e ".[dev]"
	@echo "Development dependencies installed!"

check: lint test ## Run both linting and tests
	@echo "All checks complete!"

test-fast: ## Run tests without coverage (faster)
	@echo "Running fast tests..."
	@python -m pytest tests/ -q

test-failed: ## Re-run only failed tests
	@echo "Re-running failed tests..."
	@python -m pytest tests/ --lf -v

test-watch: ## Run tests in watch mode (requires pytest-watch)
	@echo "Running tests in watch mode..."
	@python -m pytest_watch tests/ -- -v

build: clean ## Build distribution packages
	@echo "Building distribution packages..."
	@python -m build
	@echo "Build complete! Check dist/ directory"

docs: ## Generate documentation (if sphinx is configured)
	@echo "Generating documentation..."
	@cd docs && make html 2>/dev/null || echo "Documentation not configured"

# Quick test for specific module
test-tiers: ## Test only tier classification
	@echo "Testing tier classification..."
	@python -m pytest tests/omniconfig/test_tiers.py -v

test-union: ## Test only union types
	@echo "Testing union types..."
	@python -m pytest tests/omniconfig/test_union_types.py -v

test-basic: ## Test basic functionality
	@echo "Testing basic functionality..."
	@python -m pytest tests/omniconfig/test_basic.py -v