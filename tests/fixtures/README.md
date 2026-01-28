# Test Fixtures

This directory contains recorded API responses and golden output files for testing.

## Structure

```
fixtures/
├── api_responses/          # Recorded GitHub API responses
│   ├── user_sideshowbarker/  # Responses for a specific user
│   │   ├── manifest.json     # Maps call signatures to response files
│   │   ├── 001_graphql_contributions.json
│   │   ├── 002_search_commits.json
│   │   └── ...
│   └── org_w3c/             # Responses for org mode
│       └── ...
├── golden/                  # Expected output for snapshot tests
│   ├── user_report.md       # Expected user report
│   └── org_report.md        # Expected org report
└── README.md
```

## Recording New Fixtures

To record new API responses:

```python
from tests.api_recorder import ApiRecorder

# Start recording
recorder = ApiRecorder("fixtures/api_responses/user_newuser")
recorder.start_recording()

# Run the tool (will make real API calls)
# ...

# Stop and save
recorder.stop_recording()
```

Or use the command-line recorder:

```bash
python tests/record_fixtures.py --user sideshowbarker --days 7
```

## Updating Golden Files

When intentionally changing output format:

```bash
# Generate new golden file
pytest tests/test_snapshots.py --update-golden
```

Review the diff carefully before committing updated golden files.
