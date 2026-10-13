# CustomOSINT

CustomOSINT is an evidence-first, auditable OSINT correlation CLI. It turns explicit seeds into normalized entities, preserves raw provider output, scores evidence conservatively, controls automatic pivoting, and produces portable graphs and a self-contained HTML report. It does **not** assert that equal usernames identify the same person.

## Architecture

```text
seeds -> normalization -> provider adapters -> raw archive
             |                  |
             v                  v
        SQLite entities <- normalized results
             |                  |
             +-> evidence scoring -> controlled BFS pivots
                                      |
                                      v
                GEXF / GraphML / Neo4j / Maltego / HTML report
```

Providers only execute and normalize tools. Correlation, deduplication, scoring, persistence, and pivot policy live in the core. Every investigation gets its own `case.db`, raw directory, normalized JSONL, graph files, and report.

## Install

Python 3.10+ is required. For development:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp config.example.yaml config.yaml
```

On a fresh Kali system, review `install.sh` and then run `sudo ./install.sh`. The script uses a virtual environment and never runs `sudo pip`. External tools are optional and can be installed in isolation:

```bash
pipx install maigret
pipx install sherlock-project
pipx install holehe
```

Run `customosint doctor` after installation. A missing provider is recorded as `SKIPPED`, not treated as a fatal investigation error.

## Usage

```bash
customosint investigate --email example@example.com --nickname example93 --depth 2
customosint investigate --nickname example93 --providers maigret,sherlock
customosint investigate --email example@example.com --fixture tests/fixtures/example_case
customosint providers
customosint doctor
customosint cases
customosint show cases/CASE_DIRECTORY
customosint report cases/CASE_DIRECTORY
customosint graph cases/CASE_DIRECTORY
```

Provider interfaces verified for this implementation: Maigret uses its documented `--json ndjson`; Sherlock uses CSV because Sherlock's `--json` selects a site-data input; Holehe has no stable structured export, so its adapter is deliberately conservative. Public/API adapters cover GitHub, Gravatar, Keybase and HIBP. GHunt is experimental because its structured CLI output differs between releases. SpiderFoot integrates with a locally operated server through `SPIDERFOOT_URL`; scan results remain untrusted until normalized and scored.

API configuration:

```bash
export HIBP_API_KEY="..."
export GITHUB_TOKEN="..."          # optional, raises GitHub rate limits
export GRAVATAR_API_KEY="..."
export SPIDERFOOT_URL="http://127.0.0.1:5001"
```

No secret belongs in source control. Use environment variables or a local `.env` loader. A missing key or executable produces `SKIPPED`, not a failed case.

## Confidence and graphs

Evidence is combined with diminishing returns and is grouped by provider, preventing repeated weak facts from one source from creating certainty. Labels are LOW (0–0.29), POSSIBLE (0.30–0.59), PROBABLE (0.60–0.79), and STRONG (0.80–1.00). Conflicting evidence lowers a score. Human review remains mandatory.

Each case exports GEXF for Gephi, GraphML, a Neo4j Cypher script, Maltego CSV, and a local interactive HTML graph. The report separates provider errors and uncertain findings from higher-confidence relationships.

## Configuration and troubleshooting

Copy `config.example.yaml` to `config.yaml`. Conservative defaults cap depth, entity count, provider runs, concurrency, and timeouts. If a provider does not run, check `customosint doctor`, its installation, and `case.db`/the report's provider errors. Raw output remains under `raw/<provider>/` for parser debugging.

Useful safety controls include `--max-entities`, `--max-provider-runs`, `--timeout`, `--provider-timeout`, and `--no-cache`. Provider failures use bounded exponential retry; calls have a per-provider delay and global concurrency limit.

Run quality checks with:

```bash
pytest
ruff check .
mypy src
```

## Legal use

Use this software only for lawful, authorized investigations. Respect terms of service, rate limits, privacy, and local law. Do not use it for stalking, harassment, credential access, contact discovery, or bypassing service controls. HIBP integration stores breach metadata only—never plaintext passwords or breach dumps. A possible correlation is a lead, not proof of identity.
