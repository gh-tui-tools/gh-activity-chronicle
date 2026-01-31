# Contributing to gh-activity-chronicle

This document provides guidelines and instructions for contributing to gh-activity-chronicle development.

## Development Setup

### Prerequisites

- Python 3.6+
- [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated
- Git

### Getting Started

1. Fork and clone the repository:

```bash
git clone https://github.com/gh-tui-tools/gh-activity-chronicle.git
cd gh-activity-chronicle
```

2. Install commit hooks:

   The repository contains a file called `.pre-commit-config.yaml` that defines “commit hook” behavior to be run locally in your environment each time you commit a change to the sources. To enable that “commit hook” behavior, first follow the installation instructions at https://pre-commit.com/#install, and then run this:

   ```bash
   pre-commit install
   ```

   This sets up two hooks:

   - **ruff** — lints and auto-fixes issues (`ruff check --fix`)
   - **ruff-format** — checks formatting (`ruff format`)

3. Install dependencies:

```bash
pip install .[test,lint]
```

4. Run tests:

```bash
pytest tests/ -v
```

## Development Workflow

### Testing Locally

To test the extension locally without installing it:

```bash
./gh-activity-chronicle --user USERNAME
./gh-activity-chronicle --org ORGNAME
```

Or install it as a local extension:

```bash
gh extension install .
gh activity-chronicle --user USERNAME
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories (--no-cov skips coverage)
pytest tests/test_helpers.py -v --no-cov
pytest tests/test_snapshots.py -v --no-cov
pytest tests/test_e2e.py -v --no-cov
```

### Code Quality

```bash
# Run linter
ruff check gh-activity-chronicle tests/

# Check formatting
ruff format --check gh-activity-chronicle tests/

# Run all pre-commit hooks against all files
pre-commit run --all-files
```

### Updating Golden Files

After you’ve made any intentional changes to the format of report output, update the snapshot baselines:

```bash
pytest tests/test_snapshots.py --update-golden
```

Then review the diff and commit the updated golden files.

## Making Changes

### Branch Naming

- Feature: `feature/description`
- Bug fix: `fix/description`
- Documentation: `docs/description`

### Commit Messages

Use [conventional commit](https://www.conventionalcommits.org/) prefixes. [Refined GitHub](https://github.com/refined-github/refined-github) renders these as colored labels:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `test:` add or update tests
- `refactor:` code restructuring (no behavior change)
- `ci:` CI/CD changes
- `build:` build system or dependencies
- `perf:` performance improvement
- `style:` formatting (no code change)
- `chore:` maintenance
- `revert:` revert a previous commit

### Pull Request Process

1. Create a new branch for your changes
2. Make your changes with clear, descriptive commits
3. Add or update tests as needed
4. Ensure all tests pass: `pytest tests/ -v`
5. Ensure code passes lint and format checks: `pre-commit run --all-files`
6. Push your branch and create a pull request
7. Describe your changes in the PR description
8. Wait for review and address any feedback

## Project Structure

```
.
├── gh-activity-chronicle       # Main script (single-file CLI extension)
├── pyproject.toml              # Project metadata and tool configuration
├── .pre-commit-config.yaml     # Pre-commit hook configuration
├── .github/workflows/ci.yml    # CI workflow
├── schema.json                 # JSON output schema
├── tests/
│   ├── conftest.py             # Shared fixtures and module loader
│   ├── test_helpers.py         # Unit tests for helper functions
│   ├── test_categorization.py  # Repository categorization tests
│   ├── test_rate_limit.py      # Rate limit estimation tests
│   ├── test_aggregation.py     # Language/org data aggregation tests
│   ├── test_integration.py     # Integration tests (mocked API)
│   ├── test_regression.py      # Output structure and section tests
│   ├── test_html.py            # Markdown-to-HTML converter tests
│   ├── test_cli.py             # Argument parsing and CLI tests
│   ├── test_e2e.py             # End-to-end pipeline tests
│   ├── test_snapshots.py       # Golden file snapshot tests
│   └── fixtures/               # Test data and golden baselines
├── DESIGN.md                   # Design decisions and architecture
├── README.md                   # User-facing documentation
└── CONTRIBUTING.md             # This file
```

## Testing Guidelines

- Write tests for all new functionality
- Aim for good test coverage (the project enforces a 98% threshold)
- Test edge cases and error conditions
- See [tests/README.md](tests/README.md) for detailed testing documentation

### Coverage Reporting

The test suite enforces a **98% coverage threshold** (`fail_under = 98` in `pyproject.toml`). Lines that are genuinely untestable (terminal I/O, threading callbacks) are marked with `# pragma: no cover`.

```bash
# Run tests with coverage report
pytest tests/
```

Coverage is configured in `pyproject.toml` and runs automatically with `pytest`.

## Reporting Issues

When reporting issues:

1. Use the issue tracker
2. Provide a clear title and description
3. Include steps to reproduce
4. Specify your environment (OS, Python version, `gh` version)
5. Include relevant error messages or output

## Questions?

Feel free to open an issue for any questions or discussions about contributing.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
