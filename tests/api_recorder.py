"""API call recording and replay for end-to-end testing.

This module provides mechanisms to:
1. Record real GitHub API responses to fixture files
2. Replay recorded responses during tests (no network calls)

Usage for recording:
    recorder = ApiRecorder("tests/fixtures/api_responses/user_test")
    with recorder.recording():
        # Run code that makes API calls
        result = gather_user_data("testuser", "2026-01-01", "2026-01-07")

Usage for replay:
    replayer = ApiReplayer("tests/fixtures/api_responses/user_test")
    with replayer.replaying():
        # API calls return recorded responses
        result = gather_user_data("testuser", "2026-01-01", "2026-01-07")
"""

import hashlib
import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch


class ApiRecorder:
    """Records API calls and responses to fixture files."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.manifest: List[Dict[str, Any]] = []
        self.call_count = 0
        self._original_run = None

    def _make_call_id(self, args: List[str]) -> str:
        """Create a unique ID for an API call based on arguments."""
        # Create a hash of the arguments for uniqueness
        args_str = json.dumps(args, sort_keys=True)
        hash_suffix = hashlib.md5(args_str.encode()).hexdigest()[:8]
        return f"{self.call_count:03d}_{hash_suffix}"

    def _recording_wrapper(self, args, **kwargs):
        """Wrapper that records subprocess calls."""
        # Only record 'gh' commands
        if args and args[0] == "gh":
            self.call_count += 1
            call_id = self._make_call_id(args)

            # Make the actual call
            result = self._original_run(args, **kwargs)

            # Record the call and response
            response_file = f"{call_id}.json"
            record = {
                "call_id": call_id,
                "args": args,
                "response_file": response_file,
                "returncode": result.returncode,
            }

            # Save response content
            self.output_dir.mkdir(parents=True, exist_ok=True)
            response_path = self.output_dir / response_file

            response_data = {
                "stdout": result.stdout,
                "stderr": result.stderr if hasattr(result, 'stderr') else "",
                "returncode": result.returncode,
            }
            response_path.write_text(
                json.dumps(response_data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            self.manifest.append(record)
            return result
        else:
            return self._original_run(args, **kwargs)

    @contextmanager
    def recording(self):
        """Context manager to record API calls."""
        self._original_run = subprocess.run
        self.manifest = []
        self.call_count = 0

        try:
            with patch("subprocess.run", side_effect=self._recording_wrapper):
                yield self
        finally:
            # Save manifest
            self.output_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = self.output_dir / "manifest.json"
            manifest_path.write_text(
                json.dumps(self.manifest, indent=2),
                encoding="utf-8"
            )


class ApiReplayer:
    """Replays recorded API responses for testing."""

    def __init__(self, fixture_dir: str):
        self.fixture_dir = Path(fixture_dir)
        self.manifest: List[Dict[str, Any]] = []
        self.call_index = 0
        self._responses: Dict[str, Dict] = {}

    def _load_fixtures(self):
        """Load manifest and response files."""
        manifest_path = self.fixture_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"No manifest found at {manifest_path}. "
                "Run recording first to create fixtures."
            )

        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        # Pre-load all response files
        for record in self.manifest:
            response_path = self.fixture_dir / record["response_file"]
            if response_path.exists():
                self._responses[record["call_id"]] = json.loads(
                    response_path.read_text(encoding="utf-8")
                )

    def _make_mock_result(self, response_data: Dict) -> subprocess.CompletedProcess:
        """Create a mock CompletedProcess from recorded data."""
        return subprocess.CompletedProcess(
            args=[],
            returncode=response_data.get("returncode", 0),
            stdout=response_data.get("stdout", ""),
            stderr=response_data.get("stderr", ""),
        )

    def _replay_wrapper(self, args, **kwargs):
        """Wrapper that returns recorded responses."""
        # Only replay 'gh' commands
        if args and args[0] == "gh":
            if self.call_index >= len(self.manifest):
                raise RuntimeError(
                    f"More API calls than recorded. "
                    f"Expected {len(self.manifest)}, got call #{self.call_index + 1}"
                )

            record = self.manifest[self.call_index]
            self.call_index += 1

            # Verify the call matches (optional, can be relaxed)
            # For now, just return the recorded response in order
            response_data = self._responses.get(record["call_id"], {})
            return self._make_mock_result(response_data)
        else:
            # For non-gh commands, actually run them
            return subprocess.run(args, **kwargs)

    @contextmanager
    def replaying(self):
        """Context manager to replay recorded API calls."""
        self._load_fixtures()
        self.call_index = 0

        try:
            with patch("subprocess.run", side_effect=self._replay_wrapper):
                yield self
        finally:
            pass  # Could verify all calls were consumed


def create_mock_responses_for_user(username: str, days: int = 7) -> Dict[str, Any]:
    """Create a minimal set of mock API responses for testing.

    This creates synthetic responses without hitting the real API.
    Useful for creating baseline fixtures quickly.
    """
    from datetime import datetime, timedelta

    until_date = datetime.now().strftime("%Y-%m-%d")
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    return {
        "contribution_summary": {
            "data": {
                "user": {
                    "name": f"Test User ({username})",
                    "company": "@testorg",
                    "contributionsCollection": {
                        "totalCommitContributions": 25,
                        "restrictedContributionsCount": 0,
                        "totalPullRequestContributions": 5,
                        "totalIssueContributions": 2,
                        "totalPullRequestReviewContributions": 10,
                        "totalRepositoriesWithContributedCommits": 3,
                        "commitContributionsByRepository": [
                            {
                                "repository": {
                                    "nameWithOwner": "testorg/repo1",
                                    "isFork": False,
                                    "parent": None,
                                    "isPrivate": False,
                                    "primaryLanguage": {"name": "Python"},
                                    "description": "Test repository 1"
                                },
                                "contributions": {"totalCount": 15}
                            },
                            {
                                "repository": {
                                    "nameWithOwner": "testorg/repo2",
                                    "isFork": False,
                                    "parent": None,
                                    "isPrivate": False,
                                    "primaryLanguage": {"name": "JavaScript"},
                                    "description": "Test repository 2"
                                },
                                "contributions": {"totalCount": 10}
                            }
                        ]
                    }
                }
            }
        },
        "commits_search": {
            "total_count": 25,
            "items": [
                {
                    "sha": f"abc{i:03d}",
                    "repository": {"full_name": "testorg/repo1"},
                    "commit": {"message": f"Test commit {i}"}
                }
                for i in range(25)
            ]
        },
        "prs_created": {
            "search": {
                "issueCount": 2,
                "nodes": [
                    {
                        "title": "Add new feature",
                        "url": "https://github.com/testorg/repo1/pull/1",
                        "state": "MERGED",
                        "merged": True,
                        "additions": 150,
                        "deletions": 30,
                        "repository": {
                            "nameWithOwner": "testorg/repo1",
                            "primaryLanguage": {"name": "Python"}
                        }
                    },
                    {
                        "title": "Fix bug",
                        "url": "https://github.com/testorg/repo2/pull/5",
                        "state": "OPEN",
                        "merged": False,
                        "additions": 50,
                        "deletions": 10,
                        "repository": {
                            "nameWithOwner": "testorg/repo2",
                            "primaryLanguage": {"name": "JavaScript"}
                        }
                    }
                ]
            }
        },
        "prs_reviewed": [],
        "user_forks": [],
    }
