# Security Policy

FootballQ AI is a free, open-source portfolio project. It is built with
security-conscious controls appropriate for a public demo, but **it is not
claimed to be unhackable** and should not be used to process sensitive
personal data.

For the full threat model, implemented controls, and known limitations, see
[`docs/SECURITY.md`](docs/SECURITY.md).

## Reporting a Vulnerability

This is a demo/portfolio project with no dedicated security team. If you
find an issue, please open a GitHub issue describing the problem. Do not
include real credentials, tokens, or personal data in any report.

## Secret Management

- No real secrets are committed to this repository.
- `.env.example` contains placeholders only.
- Azure SQL connection strings and any optional API keys must be configured
  via Azure Functions Application Settings and Vercel Environment Variables,
  never in source code.
