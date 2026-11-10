# Learnings Folder

This folder contains documented findings from feasibility studies, proofs of concept, and probing experiments.

## Naming Convention
`XXX-finding-descriptive-name.md` — three-digit sequential numbering shared across `plans/`, `probing/`, `poc/`, `fixtures/`, `learnings/`.

## Template
Each learning document should include:
1. **Date** — when the study concluded
2. **Study Context** — what was being evaluated and why
3. **Summary** — one-line conclusion
4. **Key Findings** — detailed evidence, organized by topic
5. **Recommendation** — go/no-go with rationale
6. **Next Steps** — concrete actions (new probing, PoC, plan updates)
7. **References** — links to sources, PRs, docs, code

## Current Learnings

- [001 — Ground-Truth Dataset Feasibility & Source Survey](001-ground-truth-dataset-feasibility.md) — Schema is 49 fields (not 52); no drop-in Indic PDF+metadata dataset; build from Wikidata/Commons/Wikisource + s1.md seed + manual verification (CC/PD-only). Metrics, split, and phased PoC proposed.
