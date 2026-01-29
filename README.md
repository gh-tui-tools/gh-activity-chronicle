# gh-activity-chronicle

gh-activity-chronicle generates comprehensive reports of GitHub activity — for users or organizations — over a specified time period. By default it writes all three output formats (Markdown, JSON, and HTML); use `--format` to select just one.

## Installation

```bash
gh extension install gh-tui-tools/gh-activity-chronicle
```

### Requirements

- [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated
- Python 3.6+

> [!WARNING]
> **API Rate Limits**: This tool makes many GitHub API calls. A single-user report uses ~50-200 calls. Organization reports use significantly more — a 7-day report for a 500-member org uses ~1,300 calls (~26% of your 5,000/hour limit).
>
> **To minimize API usage:**
> - Use shorter time periods (7 days is the default)
> - For orgs, use `‑‑team` to report on specific teams instead of all members
> - Avoid running multiple org reports in quick succession

## Usage

```bash
# Basic usage (last 7 days, current GitHub user)
# Writes .md, .json, and .html files
gh activity-chronicle

# Specify a different user
gh activity-chronicle --user USERNAME

# Last week
gh activity-chronicle --weeks 1

# Last 3 months
gh activity-chronicle --months 3

# Last year
gh activity-chronicle --year

# Specific date range
gh activity-chronicle --since 2026-01-01 --until 2026-01-31

# Custom output stem (writes report.md, report.json, report.html)
gh activity-chronicle -o report.md

# Single format only
gh activity-chronicle --format json
gh activity-chronicle --format html
gh activity-chronicle --format markdown

# Single format inferred from output file extension
gh activity-chronicle -o report.json
gh activity-chronicle -o report.html

# Output to stdout (requires --format)
gh activity-chronicle --stdout --format markdown

# Organization mode (public members only, the default)
gh activity-chronicle --org w3c

# Organization mode including private members
gh activity-chronicle --org w3c --private

# Organization owners only
gh activity-chronicle --org w3c --owners

# Organization + team mode (reports on specific team members)
gh activity-chronicle --org w3c --team accessibility-specialists
```

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `‑‑user` | `‑u` | GitHub username (default: current authenticated user) |
| `‑‑org` | | GitHub organization name (mutually exclusive with `‑‑user`) |
| `‑‑team` | | Team slug within org (requires `‑‑org`) |
| `‑‑owners` | | Report on org owners only (requires `‑‑org`) |
| `‑‑private` | | Include private members (default is public members only; requires `‑‑org`) |
| `‑‑days` | | Number of days to look back (default: 7) |
| `‑‑weeks` | | Number of weeks to look back |
| `‑‑months` | | Number of months to look back |
| `‑‑year` | | Look back one year |
| `‑‑since` | | Start date in YYYY-MM-DD format |
| `‑‑until` | | End date in YYYY-MM-DD format (default: today) |
| `‑‑output` | `‑o` | Output file path / stem (default: `<name>-<since>-to-<until>`) |
| `‑‑stdout` | | Output to stdout instead of file (requires `‑‑format`) |
| `‑‑format` | `‑f` | Output format: `markdown`, `json`, or `html` (default: all three; or inferred from `‑‑output` extension) |

## Report contents

See [SAMPLE.md](SAMPLE.md) for example user mode output, or [SAMPLE-ORG.md](SAMPLE-ORG.md) for org mode output.

The generated report includes:

### Executive summary
- Commits (default branches and all branches)
- PRs created
- PR reviews given
- Issues created
- Repositories contributed to
- Lines added/deleted
- Test-related commits

### Languages
- Commits by programming language
- Lines added/deleted by language

### PRs reviewed
- Breakdown by repository with line counts

### Projects by category
Repositories are automatically categorized into:
- **W3C working-group areas**: Accessibility (WAI), Internationalization (i18n), Digital publishing, Security, Privacy, Immersive Web (WebXR), Verifiable Credentials, Web of Things, WebRTC, Web Audio, Media, Devices and sensors, Graphics, Machine Learning, Semantic Web, Sustainability, AI and agents, Payments, Performance
- **W3C operations**: W3C Process, W3C TAG, W3C Infrastructure
- **Standards ecosystem**: Specification tooling, Standards positions, Web standards and specifications (catch-all)
- **Testing and quality**: Web Platform Tests, HTML/CSS checking (validation), Browser interop, Testing frameworks
- **Documentation**: MDN, Documentation platforms (Docusaurus, Sphinx, etc.)
- **Implementation**: Browser engines, Developer tools, GitHub analytics
- **Programming languages**: Programming languages, JavaScript runtimes, TypeScript
- **Web development**: Web frameworks, Frontend frameworks, UI component libraries, Mobile development, 3D/WebGL
- **Data and ML**: Data science, ML frameworks
- **DevOps and infrastructure**: DevOps, CI/CD, Package managers, Build tools
- **IoT and embedded**: Home automation and Embedded systems
- **Databases**: Databases (MongoDB, PostgreSQL, MySQL, Redis, etc.)
- **Gaming**: Game development
- **Blockchain**: Blockchain and cryptocurrency
- **Other**: Everything else

### PRs created
- Status breakdown (merged, open, closed)
- Notable PRs sorted by lines changed
- Reviews received on created PRs

## Examples

Generate a weekly report for yourself:
```bash
gh activity-chronicle
```

Generate a quarterly report with custom filename:
```bash
gh activity-chronicle -u octocat --since 2026-01-01 --until 2026-03-31 -o Q1-2026.md
```

## Organization mode

When using `‑‑org`, the report aggregates activity from organization members:

- **Default**: Reports on public members only (those who’ve made their membership visible)
- **With `‑‑private`**: Include all members (public and private)
- **With `‑‑owners`**: Reports on organization owners (admin members) only
- **With `‑‑team`**: Reports on members of the specified team

Note: `‑‑private`, `‑‑owners`, and `‑‑team` are mutually exclusive.

The report shows combined totals across all members, with PRs and reviews de-duplicated by URL. Data for each member is gathered in parallel (30 concurrent workers).

Output filename stem:
- Org only: `{org}-{since}-to-{until}`
- Org + team: `{org}-{team}-{since}-to-{until}`

By default all three extensions (`.md`, `.json`, `.html`) are written. With `--format`, only the matching extension is written.

## Notes

- The GitHub API limits contribution queries to a 1-year span. For longer periods, the script automatically adjusts the start date.
- Commits to your forks are automatically aggregated under the parent repository (e.g., commits to `yourname/WebKit` appear under `WebKit/WebKit`).
- Private repositories and special profile repositories (`username/username`) are automatically excluded.
- For repositories with significant C++ code (>=10% of codebase), the language is reported as C++ even if test files cause GitHub to detect a different primary language.
- Report generation for a full year (~1000 commits) takes about 90 seconds.
- Organization mode requires that you have permission to view org membership (typically org members or public membership).

## Testing

The project includes a comprehensive test suite (416 tests):

```bash
# Install test dependencies
pip install pytest pytest-mock

# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_helpers.py -v      # Unit tests for helper functions
pytest tests/test_snapshots.py -v    # Snapshot comparison tests
pytest tests/test_e2e.py -v          # End-to-end data flow tests
```

**Test categories:**
- **Unit tests** — Pure functions (categorization, rate limits, formatting)
- **Integration tests** — Data flow with mocked GitHub API
- **Regression tests** — Output structure, JSON/HTML converters, section builders
- **Snapshot tests** — Compare full reports against golden baselines
- **End-to-end tests** — Complete pipeline verification
- **CLI tests** — Argument parsing, format selection, output dispatch

To update golden files after intentional output changes:
```bash
pytest tests/test_snapshots.py --update-golden
```

See [tests/README.md](tests/README.md) for details.

## Uninstall

```bash
gh extension remove activity-chronicle
```
