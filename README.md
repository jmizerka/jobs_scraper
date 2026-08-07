# Job Listings Scraper

Scrapes job offers from listing services, filters them with a local AI model (Ollama) based on your preferences, and emails you the matching jobs.

## How it works

1. **Search** — queries job listing providers (currently [Just Join IT](https://justjoin.it) and [No Fluff Jobs](https://nofluffjobs.com)) using CLI filter flags.
2. **Filter** — jobs are first filtered deterministically (client-side) for fields the provider API cannot handle, then sent to an Ollama model for AI matching against your preferences.
3. **Email** — matching jobs are sent to a configured Gmail address via the Gmail API.

## Requirements

- Python 3.14+ (uses `.venv`)
- [Ollama](https://ollama.com) running locally on `localhost:11434` with a chat model (e.g. `gemma4:latest`)
- A Google Cloud project with the Gmail API enabled and an OAuth client secret file for sending email

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Gmail OAuth setup:

1. Create a project in the [Google Cloud Console](https://console.cloud.google.com), enable the **Gmail API**, and create an OAuth 2.0 **Desktop app** client.
2. Download the client secret JSON and place it in the project root as `client_secret_*.apps.googleusercontent.com.json`.
3. On first run, the app will open a browser flow to authorize Gmail access and store credentials in `token.json`.

## Usage

```bash
python main.py [options]
```

Without any options it searches Just Join IT for all offers and sends matches to the default recipient.

### Options

| Option | Description |
| --- | --- |
| `--provider` | Listing service(s) to search: `jjit`, `nfjobs` (default: `jjit`) |
| `--category` | Job category, e.g. `python`, `javascript`, `data` |
| `--work-mode` | Remote work: `remote`, `hybrid`, `office` |
| `--work-type` | Working times: `full_time`, `part_time`, `practice_internship`, `freelance`, `b2b_contract` |
| `--experience` | Seniority: `intern`, `junior`, `mid`, `senior`, `team-leader-manager`, `c-level` |
| `--contract-type` | Contract: `b2b`, `permanent`, `internship`, `mandate-contract`, `specific-task-contract` |
| `--lang` | Offer language: `pl`, `en`, `de`, `es`, `ua`, `fr`, `it`, `ru` |
| `--city` | City to search in |
| `--city-radius` | Search radius in km |
| `--pub-date` | Only offers published within N days |
| `--with-salary` | Only offers with salary |
| `--min-salary` | Minimum salary in PLN |
| `--email-to` | Recipient email address (default is hard-coded in `main.py`) |
| `--preferences` | Path to a preferences JSON used by the AI matcher (default: `preferences.json`) |

### Examples

```bash
# Remote Python jobs in the last 7 days, min 20k PLN
python main.py --provider jjit --category python --work-mode remote --min-salary 20000 --pub-date 7

# Search both providers for senior data roles
python main.py --provider jjit nfjobs --category data --experience senior

# Send matches to a specific address
python main.py --email-to me@example.com
```

## Preferences

`preferences.json` drives the AI matcher:

```json
{
  "skills": ["Python"],
  "min_salary_pln": 1,
  "seniority": ["mid", "senior"],
  "work_mode": ["remote"],
  "excluded_skills": ["PHP", "Java", "fullstack", "frontend"],
  "extra_notes": ""
}
```

- `skills` — skills you are looking for.
- `min_salary_pln` — minimum accepted salary in PLN.
- `seniority` — accepted experience levels.
- `work_mode` — accepted work modes (e.g. `remote`).
- `excluded_skills` — skills that disqualify an offer when required in the description. Structured skill fields are filtered out beforehand; only the description body is checked.
- `extra_notes` — free-form additional instructions for the model.

Pass a different file with `--preferences path/to/file.json`.

## Roadmap / TODOs

- [ ] **Anthropic AI service** — add a matcher backed by the [Anthropic API](https://www.anthropic.com) as an alternative to the local Ollama model, selectable alongside the existing providers.
- [ ] **pracuj.pl** — add a listing provider adapter for [Pracuj.pl](https://www.pracuj.pl) (`--provider pracuj`).
- [ ] **LinkedIn** — add a listing provider adapter for [LinkedIn Jobs](https://www.linkedin.com/jobs) (`--provider linkedin`).

## Tests

```bash
pytest
```

## Project layout

```
main.py                          Entry point: search -> filter -> email
preferences.json                 AI matcher preferences
src/
  cli.py                         argparse CLI and query building
  logger.py                      Logging (console + rotating file in logs/)
  schemas/                       Pydantic models (job, justjoin.it, nofluffjobs)
  services/
    listing/                     Provider adapters (jjit, nfjobs)
    query_filter.py              Deterministic client-side filters
    deterministic_filter.py      Excluded-skill pre-filter
    ai/                          Ollama-based AI matcher
    email/                       Gmail sender
tests/                           pytest test suite
```
