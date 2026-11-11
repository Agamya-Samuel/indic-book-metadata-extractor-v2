# 002 — Enriching Ground-Truth Metadata from Wikisource + Internet Archive

- **Date:** 2026-11-11
- **Context:** [learnings/001](001-ground-truth-dataset-feasibility.md) + [plans/002](../plans/002-ground-truth-poc.md). The 6 seeded GT books had only ~5 prefilled fields (mostly filename-as-title). Goal: more ground data with real bibliographic metadata from open sources. **Note: the `exa` MCP connector was disconnected**, so research used the built-in web tools plus direct Wikimedia/Internet Archive APIs.
- **Artifacts:** [backend/scripts/enrich_ground_truth.py](../backend/scripts/enrich_ground_truth.py) (new), [backend/scripts/fetch_commons_ground_truth.py](../backend/scripts/fetch_commons_ground_truth.py) (`--max-size-mb` added), `backend/tests/fixtures/ground_truth/`.

## Summary

Grew the dataset from **6 → 14 CC/PD books** (9 Telugu, 5 Hindi) and enriched each with authoritative metadata. Field coverage rose to **4–11 of 49 per book**. The remaining ~38 fields are largely *genuinely absent* for these older books (no ISBN, rarely recorded cover artist/distributors/awards/scribes), so coverage is near the realistic ceiling for this source pool — not a tooling gap.

## Key findings

- **Wikisource Index header is a rich, structured source (Telugu).** Each `te.wikisource` proofreading project's `Index:` page begins with `{{:MediaWiki:Proofreadpage_index_template|...}}` carrying named fields — confirmed labels: `శీర్షిక`=title, `రచయిత`=author, `అనువాదకులు`=translator, `ఎడిటర్`=editor, `చిత్రకర్త`=illustrator, `ప్రచురణకర్త`=publisher, `చిరునామా`=place_of_publication, `సంవత్సరం`=publication_date, `రకం`=form_of_creative_work, `సంపుటి`=volume, `ఆధారము`=based_on. This is human-curated → ideal GT prefill. Example: *ఆంధ్ర మహనీయులు* by చిలుకూరి వీరభద్రరావు, ప్రచురణకర్త మాదిరెడ్డి సుబ్బారావు, రాజమహేంద్రవరము, 1952.
- **`hi.wikisource` has no Proofreadpage Index namespace** (`apnamespace 106` → API `badvalue`), and the Hindi books have no Commons `globalusage` on any Wikisource. So **Hindi has no Wikisource metadata path** — it relies on Internet Archive + Commons extmetadata.
- **Internet Archive metadata is rich for DLI books.** `https://archive.org/metadata/<id>` returns `title`, `creator`, `date`, `language`, and a `description` dump with `dc.publisher`, `dc.description.totalpages`, `dc.title`, `dc.contributor.author`. The item id is derivable from the credit/download URL (`/items/<id>` or `/details/<id>`) or the slug (`2015.NNNNN.*` → `in.ernet.dli.2015.NNNNN`). This added publisher + year + pages to every Hindi book and to Telugu books lacking a Wikisource publisher.
- **Wikidata/Open Library were not productive here.** Commons file pages returned **no `pageprops`/`wikibase_item`** for these files, and these DLI/old books generally lack Open Library coverage — so the 22 Wikidata P-ID mappings in the schema couldn't be used. Wikisource + IA carried the load.
- **Coverage is source-limited, not tool-limited.** For pre-ISBN-era books, fields like `isbn`, `cover_artist`, `cover_page_designer`, `distributors`, `awards`, `scribes`, `opinions_messages`, `context` are simply not printed — so `null` is the *correct* GT value, which the harness's presence/absence metric must reward.
- **Environment notes:** the backend `.venv` `httpcore` was repaired (`uv sync`) mid-session. In this shell, `NO_PROXY` containing `[::1]` makes `httpx.Client()` raise `Invalid port ':1]'`; run the scripts with `NO_PROXY` cleared.

## Result — per-book coverage (all `prefilled_needs_verification`)

| Book | Lang | Fields | Main sources |
|---|---|---|---|
| 2015.328360.Andhra-Mahaniyulu | tel | 11 | wikisource + IA |
| 2015.373190.Athma-Charitramu | tel | 10 | wikisource + IA |
| 2015.372978.Andhra-Kavithva | tel | 9 | wikisource + IA |
| A_Collection_of_Telugu_Proverbs | tel | 9 | wikisource |
| tel ×4 others (Abalaa ×2, chitra_leikhanamu, Aanandhanga) | tel | 7–8 | wikisource |
| 1913_Ummed_Singh / Priyapravaas / Sadhu-Aur | hin | 9 | IA |
| 5व_जल_सम्मेलन | hin | 6 | commons |
| Antarrashtriya_Gyankosh | hin | 4 | IA |

## Recommendation

1. **Telugu: use `te.wikisource` Index headers as the primary metadata source** (authoritative + structured). There are **500+ Index pages** — a large pool of books that have *both* GT metadata and page-level OCR GT (the `wikisource_gt.json` mechanism).
2. **DLI/IA books: use the Internet Archive metadata API** for title/creator/date/publisher/language/pages.
3. **Hindi: expect thinner GT** (no Wikisource proofreading); rely on IA + manual annotation for the richer fields.
4. **Do not chase missing fields** — correct `null` is part of GT; score presence/absence accordingly.

## Next steps

- Human-verify the prefilled fields against the scanned title/copyright pages (the `wikisource_gt.json` OCR text is the fastest check).
- Scale Telugu from `te.wikisource` Index pages (metadata + OCR GT together) rather than only Commons category order.
- Wire the harness `discover_ground_truth()` (plan/002 milestone 3) and run the first scored report.
- Consider a `--verify` helper that diffs prefilled values against the title-page OCR.

## References

- Wikisource index (example): https://te.wikisource.org/wiki/సూచిక:2015.328360.Andhra-Mahaniyulu.pdf
- Internet Archive item: https://archive.org/details/in.ernet.dli.2015.328360
- Scripts: [enrich_ground_truth.py](../backend/scripts/enrich_ground_truth.py), [fetch_commons_ground_truth.py](../backend/scripts/fetch_commons_ground_truth.py)
- Plan: [plans/002-ground-truth-poc.md](../plans/002-ground-truth-poc.md)
- Feasibility: [learnings/001](001-ground-truth-dataset-feasibility.md)