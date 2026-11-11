# 010 — Agent Browser Testing Handoff (pointer)

The canonical testing handoff lives at
[`docs/agent-browser-testing-handoff.md`](../docs/agent-browser-testing-handoff.md).

It covers: where to test (deployed `oki` host), access/credentials, Playwright
MCP tips, the full browser test matrix (§6), verified-vs-pending status (§5),
known gotchas (§7), and the reporting format (§8).

Status at handoff: implementation committed and pushed (`531cf39`); the deployed
host was returning **404** for `/`, `/login`, and `/health` — see the ⚠️ Deploy
status box in the doc before starting.
