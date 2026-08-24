# Security Policy

## Reporting a Vulnerability

Please report security issues privately rather than opening a public issue. Use GitHub's [private vulnerability reporting](https://github.com/petebojovic/homepage-exposure-status/security/advisories/new) (repo's Security tab, then Report a vulnerability).

Please include:
- A description of the issue and its potential impact
- Steps to reproduce
- Affected version(s)

## Supported Versions

Only the latest released version is supported with security fixes.

## Response

This is a small, personal project maintained in spare time. There's no guaranteed response time, but reports will be reviewed and addressed as soon as reasonably possible.

## Known Limitations (Not Vulnerabilities, But Worth Knowing)

- The `/check` endpoint has no built-in authentication or rate limiting. **Do not expose this service to the public internet.** It's designed to run on your own LAN, alongside Homepage itself. Exposing it publicly would let anyone use your instance as a free, anonymous relay to check-host.net.
- Every check made through this tool is relayed through [check-host.net](https://check-host.net), a free third-party service. Based on their API's `permanent_link` response field, they appear to retain a permanent record of each check performed. Don't use this tool against hostnames you don't want a third party to have a lasting record of monitoring.
