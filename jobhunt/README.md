## `README.md`

````markdown
# jobhunt CLI

A developer-first CLI that aggregates fresher full-stack roles from multiple platforms, normalizes them, deduplicates, scores, and presents only actionable results.

```
jobhunt search --skills "react,node,mongodb" --limit 40
```

---

## Features

- **Multi-source aggregation** — Indeed, Hirist, Internshala (+ browser handoff for LinkedIn, Naukri, Wellfound, Cutshort)
- **Smart scoring** — ranks by skill match, recency, role fit, and experience level
- **Fuzzy deduplication** — removes near-duplicate listings across sources
- **Digest mode** — shows only new jobs since your last run
- **Export** — save results to JSON or CSV
- **Config file** — persist your defaults in `~/.jobhunt.toml`
- **Cache** — 30-minute TTL per source, with selective refresh via `jobhunt update`

---

## Installation

```bash
git clone https://github.com/yourname/jobhunt-cli
cd jobhunt-cli

python -m venv .venv && source .venv/bin/activate
pip install -e .

# Install Playwright browser
playwright install chromium
```

---

## Quick Start

```bash
# Set your defaults once
jobhunt config set \
  --role "full stack developer" \
  --skills "react,node,mongodb" \
  --platforms "indeed,hirist,internshala" \
  --limit 30

# Search using saved defaults
jobhunt search

# Search with overrides
jobhunt search --role "backend developer" --skills "python,django" --limit 20

# Export results
jobhunt search --save csv

# Digest — only new jobs since last run
jobhunt search --digest
# or
jobhunt digest
```

---

## Commands

### `jobhunt search`

```
Options:
  -r, --role TEXT         Job role to search for
  -l, --location TEXT     Location (default: india)
  -e, --experience INT    Years of experience (default: 0)
  -s, --skills TEXT       Comma-separated skills, e.g. react,node,mongodb
  -p, --platforms TEXT    Comma-separated platforms (indeed,hirist,internshala)
      --limit INT         Number of results to display
      --digest            Show only new jobs since last run
      --save TEXT         Export to file: json or csv
      --save-defaults     Persist these flags as config defaults
```

### `jobhunt digest`

Shows only jobs not seen in previous runs. Uses saved config defaults.

```bash
jobhunt digest           # show new jobs
jobhunt digest --reset   # clear seen history
```

### `jobhunt update`

Checks and refreshes expired source caches.

```bash
jobhunt update                      # refresh expired sources only
jobhunt update --force              # force refresh all
jobhunt update --platforms indeed   # refresh specific platform
```

### `jobhunt open`

Opens browser-only platforms with pre-filtered search URLs.

```bash
jobhunt open linkedin
jobhunt open naukri --role "backend developer"
jobhunt open wellfound --location bangalore
```

Supported: `linkedin`, `naukri`, `wellfound`, `cutshort`

### `jobhunt config`

```bash
jobhunt config show                          # view current config
jobhunt config set --skills "react,node"     # update specific keys
jobhunt config reset                         # restore factory defaults
```

---

## Platforms

| Platform | Method | Fields |
|---|---|---|
| **Indeed** | Playwright + embedded JSON | Title, company, location, salary, job type, snippet, benefits, date |
| **Hirist** | REST API (httpx) | Title, company, location, skills, date, applicant count, recruiter |
| **Internshala** | HTML parsing (httpx) | Title, company, location, salary, skills, snippet, date |
| **LinkedIn** | Browser handoff | — |
| **Naukri** | Browser handoff | — |
| **Wellfound** | Browser handoff | — |
| **Cutshort** | Browser handoff | — |

---

## Scoring

Jobs are ranked using a weighted formula:

```
score = 0.35 × skill_match
      + 0.25 × recency
      + 0.20 × role_match
      + 0.20 × experience_fit
```

- **skill_match** — fuzzy match between `--skills` and job's skill tags
- **recency** — posted today = 1.0, posted 30+ days ago = 0.1
- **role_match** — title similarity to `--role`
- **experience_fit** — fresher roles score highest (0 yrs = 1.0)

---

## Architecture

```
jobhunt/
├── cli.py                  # Typer CLI entrypoint
├── core/
│   ├── aggregator.py       # Collect + dedup + score across sources
│   ├── scorer.py           # Scoring formula
│   └── formatter.py        # Rich table output
├── sources/
│   ├── base.py             # BaseSource ABC
│   ├── indeed.py           # Playwright + embedded JSON
│   ├── hirist.py           # REST API
│   └── internshala.py      # HTML parsing
├── models/
│   └── job.py              # Job dataclass
└── utils/
    ├── cache.py            # File-based cache (30min TTL)
    ├── config.py           # ~/.jobhunt.toml read/write
    ├── dedupe.py           # Fuzzy deduplication (rapidfuzz)
    ├── digest.py           # Seen-jobs tracking
    ├── exporter.py         # JSON/CSV export
    ├── http.py             # Playwright browser fetcher
    └── skill_extractor.py  # Skill extraction from free text
```

---

## Configuration

Config is stored at `~/.jobhunt.toml`:

```toml
[search]
role = "full stack developer"
location = "india"
experience = 0
skills = ["react", "node", "mongodb"]
platforms = ["indeed", "hirist", "internshala"]
limit = 30
```

CLI flags always override config. Use `--save-defaults` to persist any search flags.

---

## Cache

- Location: `~/.jobhunt/cache/`
- TTL: 30 minutes per source per query
- Exported files: `~/jobhunt_exports/jobs_YYYYMMDD_HHMMSS.{json,csv}`
- Seen jobs digest store: `~/.jobhunt/seen_jobs.json`

---

## Requirements

- Python 3.11+
- Chromium (via Playwright) — for Indeed only
- Internet connection

```
playwright install chromium
```

---

## Guardrails

- No session/auth token replay
- No LinkedIn/Naukri/Wellfound scraping (bot-protected — browser handoff only)
- Polite delays between requests
- Aggressive caching to minimize load on sources
````

---

Save this as `README.md` in the root `jobhunt-cli/` directory.

That completes the full project. Here's the final feature checklist:

| Feature | Status |
|---|---|
| Indeed (embedded JSON, salary, dates, skills) | ✅ |
| Hirist (REST API, skills, timestamps) | ✅ |
| Internshala (HTML parsing, salary, skills) | ✅ |
| LinkedIn / Naukri / Wellfound / Cutshort (browser handoff) | ✅ |
| Fuzzy deduplication | ✅ |
| Scoring (skill + recency + role + exp) | ✅ |
| Config file (`~/.jobhunt.toml`) | ✅ |
| Digest mode | ✅ |
| Export JSON/CSV | ✅ |
| `jobhunt update` (selective cache refresh) | ✅ |
| Installed CLI (`jobhunt` from anywhere) | ✅ |
| README | ✅ |




| Platform | Approach | Status |
|---|---|---|
| Indeed | Playwright + embedded JSON | ✅ Working |
| Hirist | REST API (httpx) | ✅ Working |
| Internshala | HTML parsing (httpx) | ✅ Working |
| Wellfound | Browser-handoff | 🔗 Slider CAPTCHA |
| Naukri | Browser-handoff | 🔗 reCAPTCHA |
| LinkedIn | Browser-handoff | 🔗 By design |
| Cutshort | Browser-handoff | 🔗 By design |


## Usage

```bash
# Search with flags (no config needed)
python3 cli.py search --skills "react,node,mongodb" --platforms indeed,hirist

# Save current flags as defaults
python3 cli.py search --role "backend developer" --skills "python,django" --save-defaults

# View config
python3 cli.py config show

# Update specific keys
python3 cli.py config set --skills "react,node,mongodb" --platforms "indeed,hirist,internshala"

# Reset to defaults
python3 cli.py config reset

# Now just run without any flags — uses your saved defaults
python3 cli.py search

# Normal search + export to CSV
python3 cli.py search --skills "react,node" --save csv

# First run — marks all jobs as seen
python3 cli.py search --digest

# Second run — only new jobs since last run
python3 cli.py search --digest

# Digest command directly (uses saved config)
python3 cli.py digest-cmd

# Reset seen history
python3 cli.py digest-cmd --reset

# Config
python3 cli.py config show
python3 cli.py config set --skills "react,node,mongodb" --limit 30
```

Once confirmed working, we add **digest** and **--save json/csv** next.