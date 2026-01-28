# Test Suite for gh-activity-chronicle

## Quick Start

```bash
# Install test dependencies
pip install pytest pytest-mock

# Run all tests (157 tests)
pytest tests/ -v

# Run specific test file
pytest tests/test_helpers.py -v

# Run with coverage (requires pytest-cov)
pip install pytest-cov
pytest tests/ --cov=. --cov-report=term-missing
```

## Test Organization

### Unit Tests (no mocking required)

| File | Tests | Coverage |
|------|-------|----------|
| `test_helpers.py` | 24 | `format_number`, anchors, links, `is_bot`, Colors |
| `test_categorization.py` | 24 | `matches`, topics, `should_skip_repo`, priority |
| `test_rate_limit.py` | 19 | `estimate_org_api_calls`, `should_warn_rate_limit` |
| `test_aggregation.py` | 23 | Language stats, org data, PR tables, ordering |

These test pure functions that don't call the GitHub API.

### Integration Tests (with mocking)

| File | Tests | Coverage |
|------|-------|----------|
| `test_integration.py` | 21 | API wrapper, data gathering, report generation |

Mocks `run_gh_command()` and related functions to test data flow without network calls.

### Regression Tests

| File | Tests | Coverage |
|------|-------|----------|
| `test_regression.py` | 35 | Report structure, markdown validity, known behaviors |

Verifies output structure is correct (sections exist, tables formatted properly, etc.).

### Snapshot Tests

| File | Tests | Coverage |
|------|-------|----------|
| `test_snapshots.py` | 2 | User report, org report golden file comparison |

Compares full report output against baseline files in `fixtures/golden/`.

### End-to-End Tests

| File | Tests | Coverage |
|------|-------|----------|
| `test_e2e.py` | 9 | Full data flow, report generation, data consistency |

Tests complete pipeline with `MockGhCommand` simulating API responses.

## Fixtures

### Golden Files (`fixtures/golden/`)

Expected report output for snapshot comparison:
- `user_report.md` — Expected user mode report
- `org_report.md` — Expected org mode report

### API Responses (`fixtures/api_responses/`)

Recorded GitHub API responses for replay testing. Structure:
```
api_responses/
└── user_testuser/
    ├── manifest.json           # Maps call signatures to response files
    ├── 001_abc123.json         # Recorded response
    └── ...
```

## Updating Golden Files

When output format changes intentionally:

```bash
# Option 1: Use pytest flag
pytest tests/test_snapshots.py --update-golden

# Option 2: Run script directly
python tests/test_snapshots.py
```

Then review the diff and commit the updated golden files.

## Recording API Fixtures

To record real API responses for testing:

```python
from tests.api_recorder import ApiRecorder

recorder = ApiRecorder("tests/fixtures/api_responses/user_newuser")
with recorder.recording():
    # Run code that makes real API calls
    result = gather_user_data("newuser", "2026-01-01", "2026-01-07")
```

## Adding New Tests

### For pure functions

Add to the appropriate `test_*.py` file:

```python
class TestNewFunction:
    def test_basic_case(self, mod):
        result = mod.new_function("input")
        assert result == "expected"
```

### For API-dependent code

Use the `mock_gh_command` fixture or create a `MockGhCommand`:

```python
def test_with_mock(self, mod):
    mock = MockGhCommand({"graphql_contributions": {...}})
    with patch.object(mod, "run_gh_command", mock):
        result = mod.gather_user_data(...)
```

### For output verification

Add to `test_regression.py`:

```python
def test_new_section_exists(self, mod, complete_user_data):
    with patch.object(mod, "gather_user_data", return_value=complete_user_data):
        report = mod.generate_report("user", "2026-01-01", "2026-01-31")
    assert "New Section" in report
```

## Mock Data Format

When creating mock data, match the actual data structure returned by functions. Key fields:

```python
{
    "username": "testuser",
    "user_real_name": "Test User",          # Not "real_name"
    "total_commits_default_branch": 100,    # Not "total_commits"
    "total_commits_all": 120,
    "total_prs": 15,                         # Not "total_prs_created"
    "total_pr_reviews": 20,                  # Not "total_reviews"
    "repos_contributed": 5,                  # Integer, not list
    "repos_by_category": {...},
    "prs_nodes": [...],                      # Not "prs_created"
    "reviewed_nodes": [...],                 # Not "prs_reviewed"
    "is_light_mode": True,                   # For org mode data
}
```

Check the source for exact field names if tests fail with `KeyError`.

## Troubleshooting

### "No module named pytest"
```bash
pip install pytest pytest-mock
```

### Golden file mismatch after intentional change
```bash
pytest tests/test_snapshots.py --update-golden
git diff tests/fixtures/golden/  # Review changes
```

### Tests fail with KeyError
The mock data structure doesn't match what the code expects. Check the actual function return values in the source code.

### Module loading fails
The test suite loads `gh-activity-chronicle` despite lacking `.py` extension. If this fails, check that `conftest.py` is present and the script path is correct.
