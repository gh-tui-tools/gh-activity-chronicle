# Contributing

## Setup

Install test and lint dependencies:

```sh
pip install pytest pytest-mock ruff
```

## Pre-commit hooks

This project uses [pre-commit](https://pre-commit.com/) to run
[ruff](https://docs.astral.sh/ruff/) checks automatically before each
commit. Install it once after cloning:

```sh
pip install pre-commit
pre-commit install
```

This sets up two hooks:

- **ruff** — lints and auto-fixes issues (`ruff check --fix`)
- **ruff-format** — checks formatting (`ruff format`)

To run the hooks manually against all files:

```sh
pre-commit run --all-files
```

Or run ruff directly:

```sh
ruff check gh-activity-chronicle tests/
ruff format --check gh-activity-chronicle tests/
```

## Running tests

```sh
pytest tests/ -v
```

## Updating golden files

After intentional changes to report output, update the snapshot baselines:

```sh
pytest tests/test_snapshots.py --update-golden
```
