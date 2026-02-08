# Wattscheduler Developer Guidelines

## Project Overview
This is a Python project for electricity price based task scheduling using FastAPI, designed for managing tasks based on electricity pricing data.

## Build Commands

### Install Dependencies
```bash
pip install -e ".[dev]"
```

### Run Development Server
```bash
uvicorn wattscheduler.main:app --reload
```

### Running Tests
```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_file.py

# Run a specific test function
pytest tests/test_file.py::test_function_name

# Run with coverage
pytest --cov=src

# Run tests in verbose mode
pytest -v

# Run tests in quiet mode
pytest -q
```

## Linting and Formatting

### Ruff (Code Linting and Formatting)
```bash
# Check for linting issues
ruff check src/

# Auto-fix linting issues
ruff check src/ --fix

# Format code
ruff format src/
```

### Mypy (Type Checking)
```bash
# Run type checking
mypy src/

# Run type checking with strict settings
mypy src/ --strict
```

## Code Style Guidelines

### Imports
- Import standard library modules before third-party modules
- Import third-party modules before local modules
- Use explicit relative imports (.) for local modules
- Group imports by standard library, third-party, and local

### Code Formatting
- Follow PEP 8 style guide
- Maximum line length: 100 characters (configured in pyproject.toml)
- Use 4 spaces for indentation
- Use snake_case for functions and variables
- Use PascalCase for classes
- Use UPPER_CASE for constants

### Naming Conventions
- Variables: snake_case
- Functions: snake_case
- Classes: PascalCase
- Constants: UPPER_CASE
- Private methods: _private_method

### Error Handling
- Use try/except blocks to handle expected errors
- Raise appropriate exceptions with descriptive messages
- Use specific exception types when possible
- Follow the principle of "fail fast"

### Type Hints
- Add type hints to all function parameters and return values
- Use `Optional[Type]` or `Union[Type1, Type2]` for complex types
- Utilize `typing` module for collections (`List`, `Dict`, etc.)

### Documentation
- Document all public functions with docstrings
- Use Google-style docstrings for complex functions
- Add module-level docstrings
- Comment complex logic sections

## Testing
- Tests should be in the `tests/` directory
- Test files should follow naming pattern: `test_*.py`
- Test function names should follow naming pattern: `test_*`
- Use pytest fixtures for common test set-up
- Test both positive and negative cases

## Development Workflow
1. Create feature branches from main
2. Run all checks before committing: `ruff check src/ --fix && mypy src/ && pytest`
3. All commits should pass CI checks
4. Keep tests updated with code changes

## Configuration
All configurations are defined in pyproject.toml:
- Line length: 100 characters
- Test paths: tests/
- Development dependencies: pytest, ruff, mypy

## Dependency source of truth
- only pyproject.toml, never requirements.txt.

## Build/Lint/Test Commands

### Install Dependencies
```bash
pip install -e ".[dev]"
```

### Run Development Server
```bash
uvicorn wattscheduler.main:app --reload
```

### Running Tests
```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_file.py

# Run a specific test function
pytest tests/test_file.py::test_function_name

# Run with coverage
pytest --cov=src

# Run tests in verbose mode
pytest -v

# Run tests in quiet mode
pytest -q
```

### Linting and Formatting

#### Ruff (Code Linting and Formatting)
```bash
# Check for linting issues
ruff check src/

# Auto-fix linting issues
ruff check src/ --fix

# Format code
ruff format src/
```

#### Mypy (Type Checking)
```bash
# Run type checking
mypy src/

# Run type checking with strict settings
mypy src/ --strict
```

## Code Style Guidelines

### Imports
- Import standard library modules before third-party modules
- Import third-party modules before local modules
- Use explicit relative imports (.) for local modules
- Group imports by standard library, third-party, and local

### Code Formatting
- Follow PEP 8 style guide
- Maximum line length: 100 characters (configured in pyproject.toml)
- Use 4 spaces for indentation
- Use snake_case for functions and variables
- Use PascalCase for classes
- Use UPPER_CASE for constants

### Naming Conventions
- Variables: snake_case
- Functions: snake_case
- Classes: PascalCase
- Constants: UPPER_CASE
- Private methods: _private_method

### Error Handling
- Use try/except blocks to handle expected errors
- Raise appropriate exceptions with descriptive messages
- Use specific exception types when possible
- Follow the principle of "fail fast"

### Type Hints
- Add type hints to all function parameters and return values
- Use `Optional[Type]` or `Union[Type1, Type2]` for complex types
- Utilize `typing` module for collections (`List`, `Dict`, etc.)

### Documentation
- Document all public functions with docstrings
- Use Google-style docstrings for complex functions
- Add module-level docstrings
- Comment complex logic sections
