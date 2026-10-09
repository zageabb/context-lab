# Development status

## OPS-UDA-001 — Reverse-proxy application prefix
Status: IN PROGRESS

UDA-listed Context Lab application supports a trusted single-hop `X-Forwarded-Prefix` via Werkzeug ProxyFix, prefix-aware Flask navigation/static links, and JavaScript chat fetches.

Evidence: regression test for proxied and LAN root mode; GitHub Actions workflow introduced for tests. The proxy backend must be restricted to trusted ingress to prevent forwarded-header spoofing. Public proxy access remains disabled.

- [ ] CI passes and PR merges to main for UDA pickup
- [ ] Live browser navigation, chat/history, upload, settings and auth via Caddy are verified
- [ ] User acceptance confirmed
