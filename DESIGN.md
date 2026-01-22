# Design: gh-user-chronicle

## Overview

gh-user-chronicle is a GitHub CLI extension, written in Python, that generates comprehensive markdown reports of a GitHub user’s activity over a specified time period. The report includes commits, pull requests, code reviews, and categorizes work by project type.

Installed via `gh extension install gh-tui-tools/gh-user-chronicle` and invoked as `gh user-chronicle`.

## Goals

1. **Comprehensive activity tracking**: Capture all meaningful GitHub contributions — including commits on non-default branches of forks, which the GitHub contributions graph doesn’t show.

2. **Project categorization**: Automatically group repositories into meaningful categories (browser engines, web standards, developer tools, etc.) to give a high-level view of where effort is being spent.

3. **Accurate attribution**: Attribute fork commits to their parent repositories, so contributions to upstream projects are properly credited.

4. **Noise filtering**: Skip commits to copies/clones of major projects (Ladybird, Firefox, SerenityOS) that appear in search results due to GitHub’s commit-mirroring behavior.

5. **Performance**: Generate reports quickly using parallel API calls, even for a full year of data (~1000 commits in ~90 seconds).

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   CLI Parser    │────▶│  Data Gathering  │────▶│ Report Generator│
│  (argparse)     │     │  (GitHub APIs)   │     │   (Markdown)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
            ┌─────────────┐       ┌─────────────┐
            │  GraphQL    │       │  REST API   │
            │  (summary)  │       │  (details)  │
            └─────────────┘       └─────────────┘
```

### Data flow

1. **Parse arguments**: Determine username, date range, output destination
2. **Fetch contribution summary**: A GraphQL query for aggregate stats
3. **Fetch all commits**: Search API with pagination (up to 1000 results)
4. **Fetch fork commits**: Direct repository API for user’s forks of categorized repos
5. **Aggregate to parents**: Map fork commits to upstream repositories
6. **Fetch commit stats**: Parallel REST API calls for line additions/deletions
7. **Categorize repositories**: Apply heuristics and explicit mappings
8. **Generate markdown**: Structured report with tables and summaries

## GitHub API usage

### GraphQL API

Used for:
- **User profile** (`user.name`): Real name for report title
- **Contribution summary** (`contributionsCollection`): Aggregate counts for commits, PRs, reviews, issues
- **PR reviews** (`pullRequestReviewContributions`): Actual PRs reviewed within the date range, with pagination
- **Repository info** (`repository`): Fork status, parent repo, language, description
- **User forks** (`user.repositories`): List of user’s forked repos with parent info

Limitations:
- `contributionsCollection` only supports a 1-year span
- Batched queries limited to ~50 repos per request

### REST API (via `gh api`)

Used for:
- **Commit search** (`search/commits`): Find all commits by author in date range
- **Commit details** (`repos/{owner}/{repo}/commits/{sha}`): Line stats (additions/deletions)
- **Branch listing** (`repos/{owner}/{repo}/branches`): Find user branches in forks
- **Branch commits** (`repos/{owner}/{repo}/commits?sha={branch}`): Commits on specific branches
- **Language breakdown** (`repos/{owner}/{repo}/languages`): Byte counts by language
- **Repo topics** (`repos/{owner}/{repo}`): GitHub topics for fallback categorization

Limitations:
- Search API returns max 1000 results (10 pages of 100)
- Rate limits: 5000 requests/hour for authenticated users

## Key design decisions

### Fork commit attribution

**Problem**: When you contribute to an upstream project via a fork, the commits appear under your fork’s name in search results, not the upstream.

**Solution**:
1. Detect forks via `isFork` and `parent.nameWithOwner` from GraphQL
2. When aggregating commits, use the parent repo name as the key
3. Keep track of source repo for each SHA (needed for REST API calls)

```python
# If it’s a fork, attribute commits to the parent
target_repo = parent if is_fork and parent else repo_name
aggregated_commits[target_repo] += commit_count
```

### Non-default branch commits in forks

**Problem**: GitHub’s search API doesn’t index commits on non-default branches of forks. If you’re working on a feature branch in your fork, those commits won’t appear in search results.

**Solution**:
1. Get list of user’s forks via GraphQL
2. For forks of “interesting” repos (those in `PROJECT_CATEGORIES`), query the branches API
3. Filter to likely user-created branches (prefixes like `eng/`, `fix/`, `feat/`)
4. Fetch commits from each branch via REST API
5. De-duplicate by SHA

### Project copy filtering

**Problem**: When you commit to a major project like Ladybird, your commits are mirrored to dozens of forks/copies on GitHub. Search results include all of these, inflating commit counts.

**Solution**: Multi-layer filtering in `should_skip_repo()`:

1. **Explicit blocklists**: Known copies that evade other detection
   ```python
   LADYBIRD_COPIES = {"zechy0055/qosta-broswer", "lucasnascimento667/teste66", ...}
   ```

2. **Name patterns**: Skip repos with “lady” or “serenity” in name (unless allowlisted)

3. **Parent detection**: Skip if parent is a major project (`parent == "ladybirdbrowser/ladybird"`)

4. **Description matching**: Skip if description matches the original exactly

### Language detection

**Problem**: GitHub’s `primaryLanguage` is based on byte count, which can be misleading. A C++ project with many HTML test files might report as “HTML”.

**Solution**: For repos reporting certain languages (HTML, JavaScript, Python, Shell), fetch the full language breakdown and check if C++ is ≥10% of the codebase:

```python
cpp_bytes = languages.get("C++", 0) + languages.get("Objective-C++", 0)
cpp_percentage = (cpp_bytes / total_bytes) * 100
if cpp_percentage >= 10:
    return "C++"
```

### Accurate PR review tracking

**Problem**: GitHub’s search API (`reviewed-by:user updated:>=date`) doesn’t filter by when the review was given — it filters by when the PR was updated. A PR reviewed a year ago but updated recently would appear in results; a PR reviewed recently but not updated since would be missed.

**Solution**: Use `contributionsCollection.pullRequestReviewContributions`, which accurately tracks reviews given within the date range:

```python
query = '''
{
  user(login: "username") {
    contributionsCollection(from: "...", to: "...") {
      pullRequestReviewContributions(first: 100, after: cursor) {
        nodes { pullRequest { title, url, additions, deletions, ... } }
        pageInfo { hasNextPage, endCursor }
      }
    }
  }
}
'''
```

Results are de-duplicated by PR URL (a user may submit multiple reviews on the same PR).

### Parallel API fetching

**Problem**: Fetching line stats for 1000 commits sequentially takes ~10 minutes.

**Solution**: Use `ThreadPoolExecutor` with 30 concurrent workers for commit stats and 10 workers for language detection:

```python
# Commit stats: 30 concurrent requests
with ThreadPoolExecutor(max_workers=30) as executor:
    futures = [executor.submit(fetch_commit_stats, c) for c in all_commits]
    for future in as_completed(futures):
        target_repo, additions, deletions = future.result()
        repo_line_stats[target_repo]["additions"] += additions

# Language detection: 10 concurrent requests
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(fetch_lang, repo) for repo in repos_needing_check]
```

Worker counts are tuned to avoid GitHub’s secondary rate limits (abuse detection). 40+ workers triggers rate limiting; 30 is the practical maximum.

Results: ~1000 commits in ~90 seconds.

## Report structure

```markdown
# github user chronicle: [username](https://github.com/username) (Real Name)

## Notable PRs
- Top 15 PRs by lines changed (first, most visible table)

## Projects by category
- Web standards and specifications
- Browser engines
- Developer tools
- etc.

## Executive summary
- Commits, PRs, reviews, issues counts
- Lines added/deleted
- Repositories contributed to

## Languages
- Commits and lines by programming language

## Code reviews
- Reviews performed (count, lines reviewed)
- Reviews received on user's PRs

## PRs created
- Status breakdown (merged/open/closed)

## PRs reviewed
- By repository with line counts

---
*Report generated on 2026-01-23 14:30:45 +0900*
```

The title includes:
- A hyperlink to the user's GitHub profile
- The user's real name (if set in their GitHub profile) in parentheses

The footer includes the generation timestamp with timezone offset.

See [SAMPLE.md](SAMPLE.md) for example output.

## Configuration

### Project categories

Repositories are categorized using a combination of explicit mappings and heuristics:

**Explicit mappings** in `PROJECT_CATEGORIES` dict:
- Exact name match (e.g., `validator/validator`)
- Fork name suffix match (e.g., `user/ladybird` matches `LadybirdBrowser/ladybird`)

**Org-based auto-detection**:
- `w3c/*`, `w3c-cg/*`, `whatwg/*`, `wicg/*` → Web standards (with pattern overrides)
- `tc39/*`, `webassembly/*`, `khronos-group/*` → Web standards
- `immersive-web/*` → Immersive Web (WebXR)
- `webaudio/*` → Web Audio
- `webmachinelearning/*` → Machine Learning
- `json-ld/*` → Semantic Web
- `act-rules/*` → Accessibility (WAI)
- `r12a/*` → Internationalization (i18n)
- `speced/*`, `jsdom/*` → Specification tooling
- `web-platform-dx/*` → Interop
- `w3cping/*` → Privacy
- `w3ctag/*` → W3C TAG
- `mdn/*` → Documentation
- `*/standards-positions` → Standards positions

**Pattern-based detection** (within standards orgs):
- `wai-*`, `wcag*` → Accessibility (WAI)
- `i18n*`, `charmod*` → Internationalization (i18n)
- `epub-*`, `publ-*`, `dpub*`, `audiobook*` → Digital Publishing
- `security*` → Security
- `privacy*`, `fingerprint*`, `ping`, `privacywg`, `gpc`, `dpv` → Privacy
- `vc-*`, `did*`, `credential*`, `verifiable*` → Verifiable Credentials
- `wot*`, `wotwg` → Web of Things
- `webrtc*`, `mediacapture*`, `ortc` → WebRTC
- `media*` (non-mediacapture), `encrypted-media`, `mediasession` → Media
- `*sensor*`, `battery`, `nfc`, `web-nfc` → Devices and Sensors
- `svgwg`, `png`, `gpuweb-wg`, `graphics-*`, `svg-*` → Graphics
- `rdf*`, `sparql*`, `shacl*` → Semantic Web
- `sustainab*` → Sustainability
- `ai-agent*`, `aikr`, `agent-comm*`, `cogai` → AI and agents
- `payment*`, `webpayments` → Payments
- `perf*`, `performance*`, `*-timing`, `resource-hints` → Performance
- `logos`, `w3c-website*` → W3C Infrastructure
- `guide`, `initiatives`, `charter-drafts`, `tpac*`, `breakout*`, `ab-public` → W3C Process
- `reffy`, `spec-families`, `respec`, `bikeshed` → Specification tooling
- `interop*` → Browser interop

**Org-based detection** (non-standards orgs):
- `golang`, `rust-lang`, `swiftlang`, `julialang`, `elixir-lang`, `python`, `ruby` → Programming languages
- `nodejs`, `denoland` → JavaScript runtimes
- `spring-projects`, `laravel`, `symfony` → Web frameworks
- `vuejs`, `sveltejs`, `angular`, `vitejs` → Frontend frameworks
- `flutter` → Mobile development
- `numpy`, `pandas-dev`, `scipy`, `scikit-learn`, `matplotlib`, `tidyverse`, `jupyter` → Data science
- `tensorflow`, `pytorch`, `keras-team`, `huggingface`, `openai` → ML frameworks
- `kubernetes`, `moby`, `docker`, `ansible`, `hashicorp`, `pulumi`, `chef` → DevOps
- `jenkinsci`, `actions`, `circleci`, `travis-ci`, `drone` → CI/CD
- `homebrew`, `nixos`, `npm`, `yarnpkg`, `pnpm`, `pypa`, `rubygems` → Package managers
- `gradle`, `bazelbuild`, `cmake` → Build tools
- `seleniumhq`, `puppeteer`, `cypress-io`, `jestjs`, `mochajs`, `pytest-dev`, `chaijs`, `sinonjs` → Testing frameworks
- `home-assistant`, `esphome`, `arduino`, `raspberrypi`, `micropython`, `espressif` → Home automation and Embedded systems
- `mongodb`, `postgres`, `mysql`, `redis`, `elastic`, `cockroachdb`, `influxdata` → Databases
- `godotengine`, `bevyengine`, `libgdx`, `phaserjs` → Game development
- `bitcoin`, `ethereum`, `solana-labs`, `cosmos`, `hyperledger`, `openzeppelin` → Blockchain

**Topic-based detection** (fallback for uncategorized repos):

As a final fallback before categorizing a repo as "Other", the tool fetches the repo’s GitHub topics and maps them to a set of categories. This allows dynamic categorization without hardcoding every repo. Topics are cached to avoid redundant API calls.

Example topic mappings:
- `machine-learning`, `deep-learning`, `tensorflow`, `pytorch`, `nlp`, `computer-vision` → ML frameworks
- `kubernetes`, `docker`, `containers`, `devops`, `aws`, `serverless` → DevOps
- `testing`, `selenium`, `e2e-testing` → Testing frameworks
- `react`, `vue`, `svelte`, `frontend` → Frontend frameworks
- `home-automation`, `iot`, `arduino`, `raspberry-pi`, `embedded` → Home automation and Embedded systems
- `database`, `mongodb`, `postgresql`, `mysql`, `redis` → Databases
- `game-development`, `unity`, `godot`, `game-engine` → Game development
- `blockchain`, `cryptocurrency`, `bitcoin`, `ethereum`, `web3` → Blockchain
- `accessibility`, `a11y`, `wcag` → Accessibility (WAI)
- `webxr`, `virtual-reality`, `ar`, `vr` → Immersive Web (WebXR)

The full mapping is in `TOPIC_CATEGORIES` dict in the source.

**Current categories**:

*W3C Working Group Areas:*
- Accessibility (WAI)
- Internationalization (i18n)
- Digital Publishing
- Security
- Privacy
- Immersive Web (WebXR)
- Verifiable Credentials
- Web of Things
- WebRTC
- Web Audio
- Media
- Devices and Sensors
- Graphics
- Machine Learning (WebNN)
- Semantic Web
- Sustainability
- AI and agents
- Payments
- Performance

*W3C Operations:*
- W3C Process
- W3C TAG
- W3C Infrastructure

*Standards Ecosystem:*
- Specification tooling
- Standards positions
- Web standards and specifications (catch-all)

*Testing and Quality:*
- HTML/CSS checking (validation)
- Web Platform Tests
- Browser interop
- Testing frameworks

*Documentation:*
- Documentation
- Documentation platforms

*Implementation:*
- Browser engines
- Developer tools
- GitHub analytics

*Programming Languages and Runtimes:*
- Programming languages
- JavaScript runtimes
- TypeScript

*Web Development:*
- Web frameworks
- Frontend frameworks
- UI component libraries
- Mobile development
- 3D/WebGL

*Data and ML:*
- Data science
- ML frameworks

*DevOps and Infrastructure:*
- DevOps
- CI/CD
- Package managers
- Build tools

*IoT and Embedded:*
- Home automation and Embedded systems

*Databases:*
- Databases

*Gaming:*
- Game development

*Blockchain:*
- Blockchain

*Other:*
- Other

### Blocklists

Three sets for filtering project copies:
- `LADYBIRD_COPIES`
- `FIREFOX_COPIES`
- `SERENITY_COPIES`

Add new entries when copies evade automatic detection.

### Rate limit handling

**Problem**: When the user hits GitHub’s rate limit, showing “Could not detect GitHub username” is confusing and unhelpful.

**Solution**: Detect rate limit errors and show when the limit resets:

```
Error: GitHub API rate limit exceeded.
Try again after 08:27:13 (local time).
```

The reset time is fetched from GitHub’s `rate_limit` API endpoint.

## Limitations

1. **1000 commit limit**: GitHub search API caps at 1000 results. For very active users over long periods, some commits may be missing.

2. **1-year contribution summary**: GitHub’s `contributionsCollection` GraphQL field only supports 1-year spans.

3. **Fork branch heuristics**: The branch filtering for forks may miss some user branches or include upstream branches in some cases.

4. **Rate limits**: Heavy usage may hit GitHub’s 5000 requests/hour limit, especially for long periods with many repositories. Exceeding ~30 concurrent requests triggers secondary rate limits (abuse detection).

## Future improvements

- Cache API responses to avoid redundant calls on re-runs
- Add more-sophisticated branch detection for forks
- Implement incremental updates (only fetch new data since last run)
