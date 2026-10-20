# Security policy

## Reporting a vulnerability
Please use GitHub's private vulnerability reporting (Security tab → "Report a vulnerability") for this repository.
If that is unavailable, open an issue asking for a private contact channel **without** including exploit details.
This is a volunteer-maintained project; there is no guaranteed response time.

## Threat model in brief
- Runs locally; no server component. Task files and prediction files are treated as untrusted *data*.
- `command:` adapter executes a program **you** choose (no shell). Never take adapter commands from untrusted input.
- `openai` adapter sends task prompts to the endpoint you configure. It refuses non-http(s) URLs and refuses to send an
  API key over plain `http` to a non-local host. Keys are read from an environment variable *name*, never a CLI value.
- Do not put private data, real phone numbers or personal information in task files (`nepali-eval lint` flags
  Nepali-mobile-like numbers).

## Automated checks in CI
`ruff`, `pytest -W error`, `bandit -r src`, `pip-audit` (dev dependencies; there are no runtime dependencies),
GitHub secret scanning with push protection and Dependabot security updates. Dependabot also proposes weekly updates for
GitHub Actions and dev tools. These checks reduce risk; they do not prove absence of vulnerabilities.
