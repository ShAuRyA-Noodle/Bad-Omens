# Security Policy

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: shauryapunj404@gmail.com
Subject: `[RELICT SECURITY] <brief description>`

Provide repro steps, impact, and a suggested fix. Acknowledgement within 48 hours; critical issues aim for a patch within 7 days. GitHub's "Security › Report a vulnerability" tab is also accepted.

## Security Controls

- argon2id password hashing (`argon2-cffi`), JWT with `cryptography` backend (`pyjwt>=2.12.0`, fix for the `crit` header auth-bypass advisory), `cryptography>=46.0.6` (fix for the SECT subgroup-attack chain).
- `python-multipart>=0.0.27` to close the upload denial-of-service + arbitrary-file-write advisory chain.
- CodeQL `security-extended` on every push, PR, and weekly schedule (Python + JavaScript/TypeScript).
- Dependabot weekly security + version updates; `npm overrides` pin every transitive dep to advisory-clean versions.
- Branch protection on `main`: required CodeQL status checks, linear history, no force-push, no deletion, conversation resolution required.
