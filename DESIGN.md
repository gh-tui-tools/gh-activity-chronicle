# Design: gh-activity-chronicle

## Overview

gh-activity-chronicle is a GitHub CLI extension, written in Python, that generates comprehensive reports of GitHub activity — for individual users or organizations — over a specified time period. Reports include commits, pull requests, code reviews, and categorize work by project type. Output is available in Markdown, JSON (machine-readable), and HTML (standalone page with embedded CSS) — by default all three are written.

Installed via `gh extension install gh-tui-tools/gh-activity-chronicle` and invoked as `gh activity-chronicle`.

## Goals

1. **Comprehensive activity tracking**: Capture all meaningful GitHub contributions — including commits on non-default branches of forks, which the GitHub contributions graph doesn’t show.

2. **Project categorization**: Automatically group repositories into meaningful categories (browser engines, web standards, developer tools, etc.) to give a high-level view of where effort is being spent.

3. **Accurate attribution**: Attribute fork commits to their parent repositories, so contributions to upstream projects are properly credited.

4. **Noise filtering**: Skip commits to copies/clones of major projects (Ladybird, Firefox, SerenityOS) that appear in search results due to GitHub’s commit-mirroring behavior.

5. **Performance**: Generate reports quickly using parallel API calls, even for a full year of data (~1000 commits in ~90 seconds).

6. **Organization support**: Generate aggregated reports for GitHub organizations, analyzing activity from all members, public members, owners, or specific teams.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   CLI Parser    │────▶│  Data Gathering  │────▶│ Report Generator│
│  (argparse)     │     │  (GitHub APIs)   │     │ (MD/JSON/HTML) │
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
8. **Generate report**: Structured output as Markdown, JSON, or HTML

## GitHub API usage

### GraphQL API

Used for:
- **User profile** (`user.name`, `user.company`): Real name for report title, company for member display
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

### Bot filtering

**Problem**: PRs authored by bots (dependabot, renovate, etc.) can appear in the "PRs reviewed" list, inflating review counts with trivial dependency updates.

**Solution**: Filter out bot-authored PRs from review lists using `is_bot()`:

```python
def is_bot(login):
    """Check if a user login appears to be a bot."""
    login_lower = login.lower()
    return login_lower.endswith("bot") or login_lower.endswith("[bot]")
```

This filters:
- GitHub Apps (e.g., `dependabot[bot]`, `renovate[bot]`)
- Bot accounts (e.g., `greenkeeper-bot`, `snyk-bot`)

Bot filtering is applied to the reviewed PRs list before counting and display.

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

Worker counts are tuned to avoid GitHub's secondary rate limits (abuse detection). 40+ workers triggers rate limiting; 30 is the practical maximum.

Results: ~1000 commits in ~90 seconds.

### Org mode commit linking

**Problem**: For org reports, we want commit counts to link to GitHub searches showing those commits. The naive approach is to OR all team members together:

```
repo:w3c/csswg-drafts (author:user1 OR author:user2 OR ... author:user39) author-date:2025-12-26..2026-01-25
```

But GitHub search has undocumented query complexity limits. With 30+ ORed authors, the search silently returns zero results — no error, just empty. There's also no `team:` or `org:` qualifier to filter commits by organization membership.

**Solution**: A two-level linking approach:

1. Commit counts in tables link to **anchors within the document** (not GitHub search)
2. A **"Commit details by repository" section** at the end lists per-member breakdowns
3. Each **individual member's count** links to a single-author GitHub search (which works fine)

```markdown
## Commit details by repository

### <a id="commits-w3c-csswg-drafts"></a>w3c/csswg-drafts (47 commits)

- [svgeesus](https://github.com/svgeesus): [23](https://github.com/search?q=repo:...+author:svgeesus+...)
- [r12a](https://github.com/r12a): [15](https://github.com/search?q=repo:...+author:r12a+...)
```

This provides:
- Working links (single-author searches have no complexity issues)
- Valuable breakdown showing who contributed what
- Clean main tables that link to detailed sections

See also: [Commit hyperlinks](#commit-hyperlinks) section for full implementation details.

## Report structure

### User mode

```markdown
# github activity chronicle: [username](https://github.com/username) (Real Name)

**Period:** 2026-01-01 to 2026-01-31

## Notable PRs
- Top PRs by total lines changed (additions + deletions), first and most visible table
- Default count scales with date range: 15 (≤14d), 25 (≤60d), 35 (≤180d), 50 (>180d)
- Override with `--notable-prs N`

## Projects by category
- Category name
  - Table: Repository | Commits | PRs | Lines | Language | Description
  - Commits link to GitHub search

## Executive summary
- Commits, PRs, reviews, issues counts
- Lines added/deleted
- Repositories contributed to

## Languages
- Table: Language | Commits | PRs | Lines
- Commits link to GitHub search filtered by language

## PRs reviewed
- By repository with line counts

## PRs created
- Status breakdown (merged/open/closed)
- Reviews received on created PRs

---
*Report generated on 2026-01-23 14:30:45 +0900*
```

### Organization mode

Org mode reports have the same structure as user mode, plus four collapsible detail sections wrapped in `<details><summary>` for better UX:

```html
<details name="commit-details">
<summary><h2>Commit details by language</h2></summary>

- Per-language sections with anchor IDs
- Each section lists members who committed in that language
- Backlinks to the Languages table

### <a id="lang-python"></a>Python (N commits) [↩](#row-lang-python)
- [member1](...): count

</details>

<details>
<summary><h2>Commit details by repository</h2></summary>

- Per-repo sections with anchor IDs
- Each section lists members who contributed
- Each member's commit count links to GitHub search

### <a id="commits-org-repo"></a>[org/repo](...) (N commits)
- [member1](...): [count](search-link)

</details>

<details>
<summary><h2>Commit details by user</h2></summary>

- Per-user sections showing their repository breakdown
- Each repo's commit count links to GitHub search
- User's company shown in parentheses (hidden for `--owners` mode)
- Company @mentions link to GitHub orgs
- Backlinks (↩) to user's list item in "Commit details by organization"

### <a id="user-ljharb"></a>[Jordan Harband](...) ([@socketdev](...) [@tc39](...)) (123 commits) [↩](#org-socketdev-ljharb) [↩](#org-tc39-ljharb)
- [org/repo1](...): [count](search-link)

</details>

<details>
<summary><h2>Commit details by organization</h2></summary>

- Groups users by their company (both @mentions and plain text)
- @org mentions get GitHub-linked headings; plain text companies don't
- Users can appear under multiple orgs if they list several @mentions
- Each user has an anchor for backlinks and links to "Commit details by user"
- Users with no company are grouped under "Unaffiliated"
- Hidden for `--owners` mode

### <a id="org-tc39"></a>[tc39](...) (456 commits)
- <a id="org-tc39-ljharb"></a>[Jordan Harband](#user-ljharb) (234)

### <a id="org-dwango-co-ltd"></a>DWANGO Co.,Ltd. (15 commits)
- <a id="org-dwango-co-ltd-berlysia"></a>[berlysia](#user-berlysia) (15)

### <a id="org-unaffiliated"></a>Unaffiliated (42 commits)
- <a id="org-unaffiliated-someuser"></a>[someuser](#user-someuser) (42)

</details>
```

These sections are collapsed by default on GitHub, making long org reports less overwhelming. All four sections share the same `name="commit-details"` attribute, which creates **accordion behavior** — opening one section automatically closes any other open section in the group. This prevents users from having multiple large detail sections expanded simultaneously, keeping the page manageable. The "Commit details by language" section provides per-language breakdowns. The "by repository" section enables commit count links in the Projects tables. The "by user" section shows each member's contribution breakdown with company affiliation and backlinks to navigate back to their exact position in the org list. The "by organization" section groups users by company for a quick view of which organizations are most active.

### Report elements

**Title**: Hyperlink to user/org GitHub profile, with real name in parentheses.

**Period**: Date range clearly displayed at the top.

**Projects by category tables**: Commits are clickable (direct GitHub search for user mode, anchor links for org mode).

**Languages table**: Commit counts link to language-filtered GitHub searches in user mode.

**Footer**: Generation timestamp with timezone offset.

See [SAMPLE.md](SAMPLE.md) for example user mode output, or [SAMPLE-ORG.md](SAMPLE-ORG.md) for org mode output.

## Output formats

Three output formats are supported. By default all three are written; `--format` selects a single one (or it's inferred from the `--output` file extension):

### Markdown

The primary output format. Renders well on GitHub, in markdown viewers, and in text editors. This is what `generate_report()` and `generate_org_report()` produce directly.

### JSON

Machine-readable output for downstream processing. Structure:

```json
{
  "meta": {
    "tool": "gh-activity-chronicle",
    "generated_at": "2026-01-07T14:30:45+09:00",
    "username": "octocat",
    "since_date": "2026-01-01",
    "until_date": "2026-01-07"
  },
  "data": { /* raw gather_user_data() / aggregate_org_data() output */ },
  "report": { /* structured sections: notable_prs, languages, etc. */ }
}
```

The `data` key contains the full raw data dict. The `report` key contains pre-computed structured sections (notable PRs, projects by category, executive summary, languages, PRs created/reviewed) — saving consumers from re-deriving the same computations that the markdown formatter performs.

The section computation is done by `build_user_report_sections()` and `build_org_report_sections()`, which serve as the shared computation layer consumed by both the JSON serializer and (indirectly) the markdown formatter.

### HTML

Standalone HTML page with embedded CSS. Produced by converting the markdown output through `markdown_to_html()`, a bundled ~100-line regex-based converter that handles the exact markdown subset used in reports:

- `#` through `######` headings
- `| table | rows |` with separator detection
- `- bullet` lists
- `**bold**`, `*italic*`, `[text](url)` inline markup
- `---` horizontal rules
- HTML passthrough (`<details>`, `<summary>`, `<span>`, `<a>`)

The CSS provides: system font stack, max-width 960px container, table borders with zebra striping, link styling, and `<details>`/`<summary>` cursor styling. Zero external dependencies.

### Format selection logic

1. Explicit `--format` flag takes precedence — writes a single file
2. If `--format` not given but `--output` has a recognized extension (`.json`, `.html`/`.htm`), infer that single format
3. Default (no `--format`, no recognized extension): write all three files (`.md`, `.json`, `.html`) using the same stem
4. `--stdout` requires `--format` (can't stream all three to stdout)

Output filenames share a common stem (`{name}-{since}-to-{until}`) with the format-appropriate extension. When `--output` is given in the all-formats case, any recognized extension is stripped to derive the stem (e.g. `--output report.md` → `report.md`, `report.json`, `report.html`).

To avoid double API calls in the all-formats path, `gather_user_data()` is called once and the result is passed to both `generate_report(data=...)` and `format_user_data_json()`. The `_resolve_stem()` helper computes the base filename.

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

**Pattern-based detection** (general):
- `draft-*-*` → IETF standards (IETF draft naming convention)
- `*audio-worklet*`, `web-audio*`, `*webaudio*` → Audio/MIDI libraries
- `*passkey*`, `*webauthn*` → Passkeys
- `*.github.io` (matching username) → Personal projects
- `postcss-*`, `stylelint-*` → CSS tooling
- `proposal-*` → Web standards and specifications (TC39/WHATWG proposals)
- `*-extension`, `browser-extension*` → Browser extensions
- `llvm*`, `clang*`, `gcc*`, `*wasm*`, `binaryen*` → Compilers
- `socket-*` → Supply chain security

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
- `httpwg`, `oauth-wg`, `ietf-wg-*` → IETF standards
- `chrisguttandin/*` → Audio/MIDI libraries
- `es-shims`, `inspect-js` → ES shims
- `jaegertracing` → Observability
- `comunica`, `rdfjs` → RDF tooling
- `passkeydeveloper` → Passkeys
- `emscripten-core` → Compilers
- `csstools` → CSS tooling
- `zotero` → Reference management
- `SocketDev` → Supply chain security
- `HTTPArchive` → Web analytics
- `SolidOS`, `SolidLabResearch`, `hackers4peace` → Semantic Web (Solid protocol)
- `matrix-org` → Semantic Web (decentralized)
- `agentplexus`, `langchain-ai` → AI and agents

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
- IETF standards
- HTTP tooling
- Specification tooling
- Standards positions
- Web standards and specifications (catch-all)

*Testing and Quality:*
- HTML/CSS checking (validation)
- Web Platform Tests
- Browser interop
- Testing frameworks
- Web analytics (HTTPArchive)
- Supply chain security

*Documentation:*
- Documentation
- Documentation platforms

*Implementation:*
- Browser engines
- Browser extensions
- Compilers
- CSS tooling
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
- RDF tooling (Linked Data)
- Observability

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

*Specialty Libraries:*
- Audio/MIDI libraries
- ES shims (polyfills)
- Passkeys (WebAuthn)
- Reference management (Zotero)

*Miscellaneous:*
- Personal projects
- Other

### Category development methodology

Categories are developed iteratively by analyzing real report output. The process:

1. **Generate a report** for a large org (e.g., w3c with 40+ members over 30 days)
2. **Examine the "Other" category** — this is the uncategorized pile
3. **Look for patterns**:
   - Org ownership: e.g., all `CyclopsMC/*` repos are Minecraft mods
   - Repo name patterns: e.g., `postcss-*` repos are CSS tooling
   - Description/purpose: e.g., repos for tracing/metrics → observability
   - Ecosystem groupings: e.g., Solid protocol repos across multiple orgs
4. **Add categorization rules** in order of specificity:
   - `ORG_CATEGORIES` for whole organizations
   - `EXPLICIT_REPOS` for specific repos that don't fit patterns
   - `GENERAL_PATTERNS` for name-based matching
   - `TOPIC_CATEGORIES` for GitHub topic-based fallback
5. **Re-run the report** to verify the "Other" pile shrinks
6. **Iterate** — repeat steps 2-5 until "Other" is manageable

**Principles:**
- Categories should be meaningful groupings, not just "reduce Other"
- Prefer org-level rules over per-repo rules where possible
- Pattern matching (prefixes, suffixes) scales better than explicit lists
- Topic-based fallback catches repos that follow community conventions
- It's OK to have some repos in "Other" — not everything needs categorizing

**Example discovery process (from w3c org report):**

The w3c org report showed 858 repos in "Other". Analysis revealed:
- `chrisguttandin/*` repos: all audio worklet/MIDI/WebAudio libraries
- `es-shims/*` and `inspect-js/*`: JavaScript polyfills and shims
- `httpwg/*`, `oauth-wg/*`: IETF working group repos
- `mnot/*`: HTTP spec tooling (author of HTTP RFCs)
- `*.github.io` matching username: personal project sites
- `CyclopsMC/*`: Minecraft modding (not relevant to w3c — stays in Other)
- `emscripten-core/*`: WebAssembly compiler toolchain
- `csstools/*`: PostCSS and CSS tooling
- `zotero/*`: Reference management software
- `SocketDev/*`: npm supply chain security

This analysis led to adding 15 new categories in two passes, reducing "Other" from 858 to ~200 repos for the w3c org.

### Blocklists

Three sets for filtering project copies:
- `LADYBIRD_COPIES`
- `FIREFOX_COPIES`
- `SERENITY_COPIES`

Add new entries when copies evade automatic detection.

### Rate limit handling

**Problem**: When the user hits GitHub's rate limit, showing "Could not detect GitHub username" is confusing and unhelpful.

**Solution**: Detect rate limit errors and show when the limit resets:

```
Error: GitHub API rate limit exceeded.
Try again after 08:27:13 (local time).
```

The reset time is fetched from GitHub's `rate_limit` API endpoint.

**Important**: The tool checks the **GraphQL** rate limit, not the REST API "core" limit. GitHub has separate quotas:
- REST API (core): 5,000/hour
- GraphQL: 5,000/hour (separate pool)

The tool primarily uses GraphQL for contribution summaries, PR data, and activity checking. Users can have 3,000+ REST calls remaining but 0 GraphQL calls — checking the wrong limit would give misleading information.

### Rate limit warning (org mode)

**Problem**: Org reports can use a significant portion of the hourly rate limit. Users should be warned before starting an expensive operation, especially if their remaining quota is low.

**Solution**: Before gathering data, estimate API calls and warn if the job would use a significant portion of the remaining limit.

**Estimation formula:**

```python
def estimate_org_api_calls(num_members, days):
    # Phase 1: batch GraphQL queries (10 users per query)
    phase1 = (num_members + 9) // 10

    # Phase 2: data gathering for active members
    # Empirical base: ~2.4 calls per member per week
    # Time scaling: sublinear — 30 days uses ~1.7x the calls of 7 days, not 4.3x
    base_rate = 2.4
    time_factor = (days / 7) ** 0.4
    phase2 = num_members * base_rate * time_factor

    return phase1 + phase2
```

This formula was calibrated against real usage (w3c org, 524 members):
- 7 days: ~1,300 actual → 1,310 estimated
- 30 days: ~2,200 actual → 2,303 estimated

**Warning thresholds:**

| Condition | Threshold | Rationale |
|-----------|-----------|-----------|
| Large job (absolute) | Estimated > 50% of 5,000 total | Job is significant regardless of current usage |
| Exhaustion risk | Estimated > 80% of remaining | Job might exhaust current quota |

Both conditions check the *actual remaining GraphQL limit* (via `gh api rate_limit .resources.graphql`) rather than assuming a full 5,000.

**Early exit when exhausted:**

If GraphQL remaining is < 50 calls, the tool doesn't ask "Proceed anyway?" — it immediately shows the rate limit error with reset time and exits. There's no point asking when there's nothing left to work with.

**User prompt:**

```
Warning: Generating a report will use an estimated ~2,303 GitHub API calls (~52% of your 4,423 remaining limit).
To reduce the number of calls, consider specifying a shorter time period (--days 7) and/or using a --team value.

Proceed anyway? [y/N]
```

- Default is No — pressing Enter aborts
- User must type `y` or `yes` to proceed
- The `--yes` / `-y` flag skips the prompt (for scripting)

**Why warn proactively?**

- Hitting rate limits mid-run is frustrating (must wait up to an hour)
- The warning appears *before* any expensive API calls
- Shows exact numbers so users can make informed decisions
- Suggests mitigations (shorter period, use `--team`)

**When warnings appear:**

| Scenario | Members | Days | Estimated | Warning? |
|----------|---------|------|-----------|----------|
| Default | 524 | 7 | ~1,310 | No (26%) |
| Monthly | 524 | 30 | ~2,303 | No (46%) |
| Small team | 20 | 30 | ~88 | No (2%) |
| Low remaining | 524 | 7 | ~1,310 | Yes if <1,638 remaining |

### Transient error handling

**Problem**: GitHub's API occasionally returns transient HTTP errors (502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout) during high-load periods or brief service disruptions. A single failed request shouldn't abort an entire report.

**Solution**: Retry failed requests with exponential backoff:

```python
def run_gh_command(args, parse_json=True, raise_on_rate_limit=False, max_retries=3):
    transient_errors = ["HTTP 502", "HTTP 503", "HTTP 504"]

    for attempt in range(max_retries + 1):
        try:
            result = subprocess.run(["gh"] + args, ...)
            return result
        except subprocess.CalledProcessError as e:
            if any(err in e.stderr for err in transient_errors):
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    time.sleep(wait_time)
                    continue
            # ... handle other errors
```

**Retry schedule:**

| Attempt | Wait before retry |
|---------|-------------------|
| 1 | 1 second |
| 2 | 2 seconds |
| 3 | 4 seconds |

After 3 retries (7 seconds total wait), the request is treated as failed and the tool silently continues with remaining work. No error is shown to the user — since the report still completes successfully, there's no need to alarm them about transient infrastructure issues. For org mode, a single member's failed API call won't prevent the report from completing; that member's data is simply skipped.

**Why exponential backoff?**

- Gives transient issues time to resolve
- Avoids hammering a struggling server
- 7 seconds total wait is acceptable; longer waits would frustrate users

## Organization mode

### Architecture

Organization mode extends the tool to generate reports for GitHub organizations:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   CLI Parser    │────▶│  gather_org_data │────▶│generate_org_rpt │
│(--org,--private,│     │                  │     │ (MD/JSON/HTML) │
│ --owners,--team)│     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
            ┌─────────────┐       ┌─────────────────┐
            │  Get members│       │gather_user_data │
            │(public,all, │       │  (per member,   │
            │owners,team) │       │   in parallel)  │
            └─────────────┘       └─────────────────┘
                                         │
                                         ▼
                               ┌─────────────────┐
                               │aggregate_org_   │
                               │     data        │
                               └─────────────────┘
```

### Data flow

1. **Fetch org/team info**: Get organization metadata and optionally team info
2. **Get members**: Fetch public members (default), all members (`--private`), owners (`--owners`), or team members (`--team`)
3. **Filter to active members**: Batch query contribution summaries to find members with any activity in the date range (see [Active contributors optimization](#active-contributors-optimization))
4. **Gather per-member data**: Call `gather_user_data_light()` for each *active* member in parallel (30 workers)
5. **Aggregate data**: Combine all member data:
   - Sum scalar metrics (commits, PRs, reviews, issues, lines)
   - Union of repos contributed (counted uniquely)
   - Merge repos by category, summing commits for duplicates
   - **Track per-member commits per repo** (`repo_member_commits` dict) for the breakdown section
   - De-duplicate PRs and reviews by URL
   - Merge line stats per repo (sum)
5. **Generate report**: Same structure as user report with aggregated data, plus:
   - Commit counts link to anchors (not GitHub search, due to query complexity limits)
   - "Commit details by repository" section with per-member breakdowns
   - "Commit details by user" section with per-repo breakdowns (inverse view)
   - "Commit details by organization" section grouping users by company @mentions
   - Members list passed to report generator for anchor link construction

### API endpoints

Organization mode uses these additional REST API endpoints:

- `GET /orgs/{org}` — Organization info (name, description)
- `GET /orgs/{org}/members` — All org members (with pagination)
- `GET /orgs/{org}/public_members` — Public org members only (with pagination)
- `GET /orgs/{org}/members?role=admin` — Org owners only (with pagination)
- `GET /orgs/{org}/teams/{team_slug}` — Team info
- `GET /orgs/{org}/teams/{team_slug}/members` — Team members (with pagination)

### Privacy warning for `--private`

**Problem**: GitHub allows org members to set their membership visibility to "private," meaning only org admins can see they're a member. If someone generates a report with `--private` and publishes it, they would expose these members' private membership status.

**Solution**: Warn users when they use `--private`:

```
Warning: The --private flag includes members who have chosen to hide their org membership.
Publishing the resulting report publicly would expose their membership against their wishes.

Proceed anyway? [y/N]
```

- Default is No — pressing Enter aborts
- User must explicitly type `y` or `yes` to proceed
- The `--yes` flag skips the prompt (user accepts responsibility)

This ensures users understand the privacy implications before generating a report that could expose information members intentionally chose to hide.

### Concurrency

Member data gathering uses 30 concurrent workers (via `ThreadPoolExecutor`), same as commit stats fetching. This is feasible because `gather_user_data_light()` makes only ~5-10 API calls per member (vs 100-1000+ in full mode).

### Active contributors optimization

**Problem**: Large organizations (e.g., w3c with 524 public members) would exhaust GitHub's 5,000 API calls/hour rate limit when gathering data for all members — even with light mode's reduced per-member cost.

**Solution**: A two-phase approach that first identifies which members had *any* activity during the report period, then gathers detailed data only for those active members.

**Phase 1 — Find active members (fast scraping):**

Instead of slow sequential GraphQL queries, we scrape GitHub's contribution graph endpoint in parallel:

```
https://github.com/users/{username}/contributions?from=2026-01-19&to=2026-01-26
```

This endpoint returns HTML with contribution squares showing activity levels:
```html
<td data-date="2026-01-20" data-level="2">...</td>  <!-- level > 0 = active -->
```

**Why scraping is faster:**
- Web requests don't count against GitHub's API rate limits
- Can use 50 concurrent workers (vs sequential API calls)
- The endpoint is designed to be fast (powers the GitHub UI)
- Contribution graph includes ALL contributions (commits, PRs, issues, reviews)

For users where scraping fails (404, timeout, private profile), we fall back to GraphQL batch queries.

**Phase 2 — Gather data for active members only:**

Only call `gather_user_data_light()` for members who passed the activity filter. For the w3c org over 7 days, this typically filters 524 members down to ~300 active members.

**Performance comparison (w3c, 524 members):**

| Approach | Activity check time | Method |
|----------|--------------------:|--------|
| Old (GraphQL) | ~2m 17s | Sequential batches of 10 |
| New (scraping) | **~26s** | 50 parallel workers + fallback |

**Speedup: ~5x faster** for the activity checking phase.

**API call comparison (w3c, 524 members):**

| Time period | API calls | Rate limit impact |
|-------------|----------:|-------------------|
| 7 days (default) | ~1,300 | 26% of limit |
| 30 days | ~2,100 | 42% of limit |

Note: Scraping doesn't count against the API limit, so the actual API usage is lower — only the GraphQL fallback (typically ~5% of users) and Phase 2 data gathering use API calls.

**Benefits:**

- **Much faster**: 26 seconds vs 2+ minutes for activity checking
- **Enables repeatability**: Can run multiple reports per hour without hitting rate limits
- **Leaves headroom**: Other `gh` commands won't fail due to exhausted limits
- **Graceful fallback**: Users with private profiles or errors still get checked via API

**Progress indication:**

Phase 1 shows progress and timing:
```
⠋ Checking activity for 450/524 members (latest: username)
Falling back to API for 24 users...
Checking activity for 524 w3c members took 26s
Found 316 active members out of 524
```

**Rate limit handling:**

If the GraphQL fallback hits the rate limit, the tool waits for reset (up to 3 minutes) or shows the reset time and exits.

### Data scope (light mode)

Org mode uses `gather_user_data_light()` which fetches only essential data to avoid exhausting GitHub's API rate limit. This means org reports **include only commits to upstream/canonical repositories** — not commits to members' personal forks.

Another way to think about it: org mode captures **merged work** — commits from PRs that have been merged into upstream repositories. It doesn't capture **work-in-progress** — commits on fork branches for PRs that haven't been merged yet.

**What's included:**
- Commits from GitHub's contribution summary (repos where the user has push access)
- PRs created by members
- PRs reviewed by members

**What's excluded:**
- Commits to members' forks of repositories (these are captured in user mode via fork scanning)
- Commits on non-default branches of forks (work-in-progress for unmerged PRs)
- Per-commit line stats (additions/deletions)
- Test commit detection

This tradeoff prioritizes API efficiency: full data gathering can require 100-1000+ API calls per member, while light mode requires only ~5-10 calls per member. For an org with 40 members, this is the difference between 4000-40000 calls (likely hitting rate limits) vs 200-400 calls (completing comfortably).

For complete commit tracking including fork contributions, generate individual user reports.

### Progress indicators

Org mode shows progress through multiple phases, each with a spinner and status message:

1. **Fetching org members**: `⠋ Fetching org members (400 so far)...`
   - Shows running count as members are paginated (100 per API call)
   - Provides feedback during what can be a multi-second operation for large orgs

2. **Checking activity**: `⠋ Checking activity for 450/524 members (latest: username)`
   - Uses fast parallel web scraping (50 workers)
   - Falls back to API for users where scraping fails
   - Followed by timing summary: `Checking activity for 524 w3c members took 26s`

3. **Gathering member data**: `⠇ Gathered data for 65/145 active members (30 in progress)`
   - Shows *completed* count (not started count) to accurately reflect progress
   - Shows how many workers are still fetching data ("N in progress")
   - Updates as each member's data finishes (not when it starts)
   - The "in progress" count explains apparent pauses when slow members (those with lots of PRs/reviews) are being processed

4. **Gathering complete**: `⠇ Gathered data for all 145 active members`
   - Brief transition message (0.3s) showing the gathering phase is complete
   - Provides clear visual cue before moving to aggregation

5. **Aggregating data**: `⠇ Aggregating member data...`
   - Brief phase combining all member data

6. **Generating report**: `⠇ Generating report...`
   - Writing the markdown output

**Timing summaries:**

Two timing messages are displayed:
- `Checking activity for 524 w3c members took 26s` — Activity check duration
- `Gathering data for org w3c took 1m 9s` — Total gathering duration (all phases)

**Why progress indicators matter:**

- Large orgs (500+ members) take several minutes to process
- Without feedback, users might think the tool is stuck
- Running counts show the tool is actively working
- Timing summaries help users plan future runs

This design ensures the progress indicator reflects actual completion rather than just task initiation — important because parallel tasks complete in unpredictable order.

### Report title format

**Org only:**
```markdown
# github activity chronicle: [w3c](https://github.com/w3c) (World Wide Web Consortium)
```

**Org + team:**
```markdown
# github activity chronicle: [w3c](https://github.com/w3c) – team-slug (World Wide Web Consortium – Team Name)
```

### Output filename

- Org only: `{org}-{since}-to-{until}.{ext}`
- Org + team: `{org}-{team}-{since}-to-{until}.{ext}`

where `{ext}` is `.md`, `.json`, or `.html`. By default all three extensions are written; with `--format`, only the matching extension is written.

## Commit hyperlinks

Commit counts in the report tables are clickable links to GitHub searches showing the actual commits.

### User mode

For individual user reports, commit counts link directly to GitHub search:

**Projects by category tables:**
```
repo:{repo} author:{username} author-date:{since}..{until}
```

Example: `[12](https://github.com/search?q=repo%3Adlvhdr/gh-dash%20author%3Asideshowbarker%20author-date%3A2026-01-18..2026-01-25&type=commits)`

**Languages table:**
```
author:{username} language:{lang} author-date:{since}..{until}
```

Example: `[18](https://github.com/search?q=author%3Asideshowbarker%20language%3AGo%20author-date%3A2026-01-18..2026-01-25&type=commits)`

> **Note**: GitHub commit search has limited support for the `language:` qualifier. These links may not return results in all cases. See [GitHub search limitations](#github-search-limitations) below.

### Organization mode — the challenge

For org reports, we aggregate commits from multiple members. The naive approach would be to OR all authors together:

```
repo:w3c/csswg-drafts (author:user1 OR author:user2 OR author:user3 ...) author-date:...
```

**Problem discovered**: GitHub search has undocumented query complexity limits. When ORing 30+ authors together, GitHub returns zero results — silently, with no error message. There's also no `team:` or `org:` qualifier that would filter commits by organization membership.

### Organization mode — the solution

Since GitHub search can't handle multi-author queries at scale, org mode uses a two-level linking approach:

1. **Commit counts in tables link to anchors** within the same document:
   ```markdown
   | [w3c/csswg-drafts](https://github.com/w3c/csswg-drafts) | [47](#commits-w3c-csswg-drafts) | ...
   ```

2. **"Commit details by repository" section** at the end of the report provides per-member breakdowns:
   ```markdown
   ## Commit details by repository

   ### <a id="commits-w3c-csswg-drafts"></a>[w3c/csswg-drafts](https://github.com/w3c/csswg-drafts) (47 commits)

   - [svgeesus](https://github.com/svgeesus): [23](https://github.com/search?q=repo%3Aw3c/csswg-drafts%20author%3Asvgeesus%20author-date%3A...)
   - [r12a](https://github.com/r12a): [15](https://github.com/search?q=repo%3Aw3c/csswg-drafts%20author%3Ar12a%20author-date%3A...)
   - [iherman](https://github.com/iherman): [9](https://github.com/search?q=repo%3Aw3c/csswg-drafts%20author%3Aiherman%20author-date%3A...)
   ```

3. **Individual member links work perfectly** because single-author GitHub searches have no complexity issues.

This approach:
- Keeps the main tables clean and scannable
- Provides drill-down to see who contributed what
- All links actually work (no GitHub search limitations)
- Shows the team breakdown which is valuable information anyway

### Organization mode — Languages table

The Languages table in org mode also uses anchor links to a "Commit details by language" section. However, unlike the repository breakdown, **the per-member counts in the language section are plain numbers without GitHub links**.

Why? GitHub commit search doesn't support filtering by programming language:
- `language:` is a code search qualifier, not a commit search qualifier
- Using `language:` in a commit search causes GitHub to interpret it as code search
- Code search doesn't support `author:` — so we can't filter by both

We attempted workarounds:
1. **Multi-repo queries**: Find repos of that language the user committed to, construct `(repo:x OR repo:y) author:user`. But GitHub still interprets this as code search when repos span multiple languages.

The result: Language detail sections show who contributed how many commits, with links to their GitHub profiles, but no direct links to those specific commits.

### GitHub search limitations

GitHub's search APIs have several undocumented limitations that affect commit linking:

| Limitation | Impact | Workaround |
|------------|--------|------------|
| **Query complexity limit** | ORing 30+ authors returns zero results silently | Use per-member breakdowns with single-author links |
| **No team/org filter** | Can't filter commits by org membership | List authors explicitly (hits complexity limit) |
| **No language filter for commits** | `language:` is code-search only; using it triggers code search mode | No workaround; show plain counts for language breakdowns |
| **Code search lacks author** | Can't combine `language:` with `author:` | No workaround |

### Implementation

Helper functions in the codebase:

```python
def make_commit_link(repo_name, count, since_date, until_date, authors=None):
    """Create a markdown link to GitHub commit search.

    authors: Single username (str) or list of usernames.
    For lists, constructs (author:x OR author:y OR ...) syntax,
    though this hits GitHub limits with 30+ authors.
    """

def make_repo_anchor(repo_name):
    """Create an anchor ID from a repo name (e.g., 'w3c/csswg-drafts' -> 'w3c-csswg-drafts')."""

def make_lang_anchor(language):
    """Create an anchor ID from a language name (e.g., 'C++' -> 'cplusplus')."""

def make_org_anchor(org_or_company):
    """Create an anchor ID from org/company (e.g., 'tc39' -> 'org-tc39', 'DWANGO Co.,Ltd.' -> 'org-dwango-co-ltd')."""
```

The `aggregate_org_data()` function tracks:
- `repo_member_commits` — `{repo_name: {username: commit_count}}` for repository breakdowns
- `lang_member_commits` — `{language: {username: commit_count}}` for language breakdowns
- `member_real_names` — `{username: real_name}` for display name lookup

Both commit tracking dicts are used to generate the detail sections with bidirectional anchor links (table → detail section → back to table row).

### Member name and company display

In the detail sections, members are displayed using their **real name** (from their GitHub profile) when available, with the **username as fallback**:

```markdown
- [Chris Lilley](https://github.com/svgeesus): [13](...)
- [sideshowbarker](https://github.com/sideshowbarker): [1](...)
```

The link always points to the GitHub profile using the username, but the display text shows the more readable real name when the user has one configured.

In the "Commit details by user" section, the member's **company** is also shown (unless using `--owners` mode, where it would be redundant). Company `@mentions` are converted to GitHub org links, and backlinks point to the user's specific list item in the "Commit details by organization" section:

```markdown
### [Jordan Harband](https://github.com/ljharb) ([@socketdev](https://github.com/socketdev) [@tc39](https://github.com/tc39)) (123 commits) [↩](#org-socketdev-ljharb) [↩](#org-tc39-ljharb)
```

Multiple `@org` mentions are supported — each becomes a separate link with its own backlink. Org names can include periods (e.g., `@mesur.io`). Plain text companies (without `@`) are shown as-is and also get backlinks to their list item in the company group. This enables sequential navigation through an org's member list — view a user's details, then use the backlink to return to exactly where you left off.

### Company name normalization

GitHub users enter their company field as free text, leading to inconsistent variations:
- Case differences: `babel`, `Babel`, `BABEL`
- Format differences: `W3C`, `@w3c`, `@W3C`

To group users consistently in the "Commit details by organization" section, company names are normalized:

1. **Case normalization**: All variations of the same word are grouped together. Plain text gets initial capitalization (e.g., `babel` → `Babel`).

2. **@mention preference**: If any user has a company with an `@org` mention, all users with the same plain-text variation are grouped under the `@org` form. For example, if one user has `@w3c` and another has `W3C`, both appear under `@w3c` in the organization groupings.

3. **Mixed values**: Users with both `@org` mentions and plain text in their company field have each component normalized separately.

This ensures that minor formatting differences don't split users who work at the same organization into separate groups.

## Limitations

1. **1000 commit limit**: GitHub search API caps at 1000 results. For very active users over long periods, some commits may be missing.

2. **1-year contribution summary**: GitHub's `contributionsCollection` GraphQL field only supports 1-year spans.

3. **Fork branch heuristics**: The branch filtering for forks may miss some user branches or include upstream branches in some cases.

4. **Rate limits**: Heavy usage may hit GitHub's 5000 requests/hour limit, especially for long periods with many repositories. Exceeding ~30 concurrent requests triggers secondary rate limits (abuse detection). The [active contributors optimization](#active-contributors-optimization) mitigates this for org mode — a 7-day report (the default) for 524 members uses ~1,300 API calls (~26% of the hourly limit).

5. **Organization permissions**: Org mode requires permission to view org membership. For private orgs or orgs with hidden membership, you must be a member.

6. **GitHub search query complexity**: GitHub silently returns zero results for complex search queries (e.g., 30+ ORed authors). This limits the ability to create single links that filter by multiple authors. The workaround is to use anchor links with per-member breakdowns (see "Commit hyperlinks" section).

## Code style

The source code is optimized for both **readability** and **concision** — two goals that are often in tension but can reinforce each other when balanced carefully.

### What this means

**Readability** means the code is easy to understand at a glance:
- Descriptive variable and function names
- Logical grouping of related code
- Comments where the *why* isn't obvious from the code itself

**Concision** means avoiding unnecessary verbosity:
- No redundant comments that just restate what the code does
- Compact expressions where they're clearer than verbose alternatives
- PEP 8 compliance (79-character line limit) which forces thoughtful line breaks

### Examples

**Intermediate variables for clarity without bloat:**

```python
# Clear: variable name explains what this expression means
pct = estimated_calls * 100 // remaining_calls
limit_str = f"{remaining_calls:,} remaining limit"
msg = f"~{estimated_calls:,} API calls (~{pct}% of your {limit_str})"
```

Not:
```python
# Verbose: unnecessary intermediate steps
percentage_of_rate_limit_that_will_be_used = estimated_calls * 100 // remaining_calls
human_readable_limit_description = f"{remaining_calls:,} remaining limit"
warning_message_to_display_to_user = f"~{estimated_calls:,} API calls (~{percentage_of_rate_limit_that_will_be_used}% of your {human_readable_limit_description})"
```

**Compact conditionals when the intent is clear:**

```python
# Concise and readable
target_repo = parent if is_fork and parent else repo_name
```

Not:
```python
# Overly verbose
if is_fork and parent is not None:
    target_repo = parent
else:
    target_repo = repo_name
```

**Breaking long lines at logical boundaries:**

```python
# Good: breaks at logical points, easy to scan
if (remaining_calls is not None
        and estimated_calls > remaining_calls * WARN_THRESHOLD_REMAINING):
    return True, msg
```

Not:
```python
# Bad: arbitrary break mid-expression
if remaining_calls is not None and estimated_calls > remaining_calls * \
        WARN_THRESHOLD_REMAINING:
```

**Comments explain *why*, not *what*:**

```python
# Good: explains the non-obvious reasoning
# 30 workers is the practical maximum — 40+ triggers GitHub's abuse detection
with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
```

Not:
```python
# Bad: restates the obvious
# Create a thread pool executor with 30 workers
with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
```

### Named constants over magic numbers

Tuning parameters are defined as constants at the top of the file:

```python
MAX_PARALLEL_WORKERS = 30         # Max threads for parallel API calls
ACTIVITY_CHECK_WORKERS = 50       # Workers for activity checking (scraping)
GRAPHQL_BATCH_SIZE = 10           # Users per GraphQL batch query
API_PAGE_SIZE = 100               # Items per page for paginated API calls
```

This makes tuning parameters discoverable and ensures consistency across the codebase.

### Helper functions for DRY

Common patterns are extracted into reusable helpers:

- `paginate_gh_api()` — Generic pagination for GitHub REST API endpoints
- `get_ordered_categories()` — Sort categories by priority for display
- `aggregate_language_stats()` — Combine language data across repos
- `generate_notable_prs_table(prs, langs, limit)` — Build the Notable PRs markdown table, sorted by total churn
- `_resolve_stem()` — Compute base filename stem for output files

### Idiomatic Python patterns

**`@functools.lru_cache` for memoization:**

```python
@functools.lru_cache(maxsize=1024)
def fetch_repo_topics(repo_name):
    """Fetch topics for a repository, with caching via lru_cache."""
```

**Context managers for resource safety:**

```python
with progress.running("Fetching data..."):
    data = fetch_data()  # progress.stop() called even if exception
```

**`contextlib.suppress()` for cleaner exception handling:**

```python
with suppress(subprocess.CalledProcessError, json.JSONDecodeError):
    # Silently ignore expected failures
```

**`pathlib` for file operations:**

```python
Path(output_path).write_text(report, encoding="utf-8")
```

### Line length discipline

All lines are kept under 79 characters (PEP 8 standard) without `# noqa` exemptions. This constraint:

- Forces extraction of complex expressions into named variables
- Encourages shorter, more focused function signatures
- Makes the code more readable in split-pane editors and terminal windows
- Results in natural line breaks at logical boundaries

The 79-character limit is a feature, not a burden — it's a forcing function for cleaner code.

## Testing

The project includes a comprehensive pytest-based test suite covering unit tests, integration tests, snapshot tests, and end-to-end tests.

### Test organization

```
tests/
├── conftest.py              # Shared fixtures, module loading
├── test_helpers.py          # 36 unit tests for pure helper functions
├── test_categorization.py   # 48 tests: pattern matching, repo categorization
├── test_rate_limit.py       # 19 tests: API call estimation, warning thresholds
├── test_aggregation.py      # 28 tests: data aggregation functions
├── test_integration.py      # 106 tests: data flow with mocked API calls
├── test_regression.py       # 61 tests: output structure, section builders, JSON
├── test_snapshots.py        # 2 tests: golden file comparison
├── test_e2e.py              # 28 tests: end-to-end pipeline tests
├── test_cli.py              # 53 tests: argument parsing, format selection, run()
├── test_html.py             # 35 tests: markdown-to-HTML converter
├── api_recorder.py          # Record/replay infrastructure
└── fixtures/
    ├── golden/              # Expected output baselines
    │   ├── user_report.md
    │   └── org_report.md
    └── api_responses/       # Recorded API responses (optional)
```

### Test categories

**Unit tests** (no mocking required):
- `test_helpers.py` — `format_number()`, anchor generators, link generators, `is_bot()`
- `test_categorization.py` — `matches()`, `get_category_from_topics()`, `should_skip_repo()`
- `test_rate_limit.py` — `estimate_org_api_calls()`, `should_warn_rate_limit()`
- `test_aggregation.py` — `aggregate_language_stats()`, `aggregate_org_data()`, `generate_notable_prs_table()`

**Integration tests** (mock `run_gh_command`):
- `test_integration.py` — Tests data gathering and report generation with mocked API responses
- Verifies the orchestration logic without making real network calls

**Regression tests**:
- `test_regression.py` — Verifies report structure, section builders, JSON/HTML output format
- Catches unintended changes to output format

**Snapshot tests**:
- `test_snapshots.py` — Compares full report output against golden baseline files
- `normalize_report()` removes timestamps for stable comparison
- Use `--update-golden` flag to regenerate baselines after intentional changes

**End-to-end tests**:
- `test_e2e.py` — Tests complete data flow from API calls through report generation
- `MockGhCommand` class simulates GitHub API responses based on call patterns
- Verifies data consistency (commit counts match, PRs deduplicated correctly)

**HTML converter tests**:
- `test_html.py` — Tests `markdown_to_html()` and `_inline_markdown()` converters
- Covers headings, tables, lists, inline markup, HTML passthrough, element transitions

**CLI tests**:
- `test_cli.py` — Tests `parse_and_validate_args()` + `run()` entry points
- Covers all argument combinations, format selection, extension inference, validation, output dispatch

### Coverage

The test suite (416 tests) enforces a **98% coverage threshold** configured in `pyproject.toml`. Current coverage is ~99%. Genuinely untestable code (terminal I/O, threading callbacks, rate-limit recovery) is marked `# pragma: no cover`. The remaining ~20 uncovered lines are intentionally left without pragmas — they represent code where mock complexity outweighs testing value, and the coverage report serves as a living inventory of these gaps.

### Running tests

```bash
# Install dependencies
pip install pytest pytest-mock

# Run all tests
pytest tests/ -v

# Run specific category
pytest tests/test_helpers.py -v

# Update golden files after intentional changes
pytest tests/test_snapshots.py --update-golden
```

### Module loading

The main script (`gh-activity-chronicle`) lacks a `.py` extension since it's a CLI tool. The test suite loads it dynamically:

```python
def load_chronicle_module():
    script_path = Path(__file__).parent.parent / "gh-activity-chronicle"
    loader = importlib.machinery.SourceFileLoader("chronicle", str(script_path))
    spec = importlib.util.spec_from_loader("chronicle", loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

### API mocking strategy

For integration and E2E tests, the suite mocks at different levels:

1. **Function-level mocking** — Mock specific functions like `get_contributions_summary()` to return controlled data
2. **Command-level mocking** — `MockGhCommand` class intercepts `run_gh_command()` calls and returns appropriate responses based on argument patterns
3. **Record/replay** — `ApiRecorder` class can capture real API responses for later replay (useful for creating realistic fixtures)

The mocking approach allows testing the full pipeline without GitHub API access while still exercising real code paths.

### Linting and formatting

[Ruff](https://docs.astral.sh/ruff/) handles both linting (`ruff check`) and formatting (`ruff format`), configured in `pyproject.toml` with a 79-character line length. A pre-commit hook (`.git/hooks/pre-commit`) runs both checks on staged files.

### Continuous integration

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs ruff check, ruff format, and the test suite on pushes to main, pull requests, and manual dispatch. Tests run across Python 3.9–3.13 on `ubuntu-latest`. The coverage threshold is enforced via `pyproject.toml` (`fail_under = 98`), so CI fails if coverage drops below 98%.

### Golden file maintenance

Golden files (`tests/fixtures/golden/`) contain expected report output. When report format changes intentionally:

1. Run `pytest tests/test_snapshots.py --update-golden`
2. Review the diff in the golden files
3. Commit the updated golden files with the code changes

The `normalize_report()` function removes variable content (timestamps) before comparison, ensuring tests are deterministic.

## Future improvements

### Performance and efficiency

- **Response caching** — Cache API responses to disk to avoid redundant calls on re-runs (useful when iterating on report formatting)
- **Incremental updates** — Only fetch new data since last run, appending to cached results
- **Conditional requests** — Use `If-Modified-Since` / ETags to skip unchanged data

### Data gathering

- **Smarter fork branch detection** — Current heuristics (branch prefixes like `fix/`, `feat/`) miss some user branches; could analyze commit authorship instead
- **Issue tracking** — Include issues created/commented on, not just PRs
- **Discussion participation** — Track GitHub Discussions activity
- **Commit message analysis** — Extract conventional commit types (feat, fix, docs, etc.) for categorization

### Output and formatting

- **Comparison mode** — Compare two periods side-by-side (e.g., this month vs last month)
- **Contribution graphs** — ASCII or image-based activity heatmaps
- **`--compact` flag** — Single-page summary without detailed tables
- **`--verbose` flag** — Include additional detail (commit messages, PR descriptions)

### Configuration

- **Custom categories** — User-defined category rules via config file (`.gh-activity-chronicle.yml`)
- **Blocklist/allowlist config** — Persist repo filtering rules across runs
- **Output templates** — Customizable markdown templates for report sections

### Organization mode

- **`--full` flag** — Opt-in to full data gathering (fork commits, line stats) for smaller teams where API limits aren't a concern
- **Team comparison** — Compare activity across multiple teams in one report
- **Inactive member detection** — Identify members with no activity in the period

### Integration

- **Scheduled report generation** — GitHub Actions workflow for automatic periodic reports
- **Slack/email delivery** — Send reports directly to communication channels
