# gh-user-chronicle

gh CLI extension that generates a comprehensive markdown report of a user's GitHub activity over time

## Installation

```bash
gh extension install gh-tui-tools/gh-user-chronicle
```

### Requirements

- [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated
- Python 3.6+

## Usage

```bash
# Basic usage (last 30 days, current GitHub user)
gh user-chronicle

# Specify a different user
gh user-chronicle --user USERNAME

# Last week
gh user-chronicle --weeks 1

# Last 3 months
gh user-chronicle --months 3

# Last year
gh user-chronicle --year

# Specific date range
gh user-chronicle --since 2026-01-01 --until 2026-01-31

# Custom output filename
gh user-chronicle -o report.md

# Output to stdout instead of file
gh user-chronicle --stdout
```

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--user` | `-u` | GitHub username (default: current authenticated user) |
| `--days` | | Number of days to look back (default: 30) |
| `--weeks` | | Number of weeks to look back |
| `--months` | | Number of months to look back |
| `--year` | | Look back one year |
| `--since` | | Start date in YYYY-MM-DD format |
| `--until` | | End date in YYYY-MM-DD format (default: today) |
| `--output` | `-o` | Output file path (default: `<user>-<since>-to-<until>.md`) |
| `--stdout` | | Output to stdout instead of file |

## Report contents

See [SAMPLE.md](SAMPLE.md) for example output.

The generated report includes:

### Executive summary
- Commits (default branches and all branches)
- PRs created
- Pull request reviews given
- Issues created
- Repositories contributed to
- Lines added/deleted
- Test-related commits

### Languages
- Commits by programming language
- Lines added/deleted by language

### Code reviews
- PRs reviewed with lines of source reviewed
- PR discussions participated in
- Reviews received on authored PRs

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

### PRs reviewed
- Breakdown by repository with line counts

## Examples

Generate a monthly report for yourself:
```bash
gh user-chronicle --days 30
```

Generate a quarterly report with custom filename:
```bash
gh user-chronicle -u octocat --since 2026-01-01 --until 2026-03-31 -o Q1-2026.md
```

## Notes

- The GitHub API limits contribution queries to a 1-year span. For longer periods, the script automatically adjusts the start date.
- Commits to your forks are automatically aggregated under the parent repository (e.g., commits to `yourname/WebKit` appear under `WebKit/WebKit`).
- Private repositories and special profile repositories (`username/username`) are automatically excluded.
- For repositories with significant C++ code (>=10% of codebase), the language is reported as C++ even if test files cause GitHub to detect a different primary language.
- Report generation for a full year (~1000 commits) takes about 90 seconds.

## Uninstall

```bash
gh extension remove user-chronicle
```
