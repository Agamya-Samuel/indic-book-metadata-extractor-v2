# 009 — Specialized Decision & Classification Models vs Generative LLMs for the 49 Fields

- **Date:** 2026-11-11
- **Context:** Desk study **plus live API probes** (no pipeline runs, no book processed end-to-end). Evaluate whether OpenRouter's **Specialized Decision and Classification Models** (`output_modalities=decisions`, the *Decisions API*) can extract our 49 bibliographic metadata fields from noisy Hindi/Telugu OCR, either as a replacement for the generative LLM stage or as a complementary component. Requested comparison against our current Qwen/Ollama path, plus OpenRouter API mechanics and a hybrid-architecture assessment.
- **Method:** official OpenRouter docs (Models API, Decisions API reference, Extractions guide, Jev hub, structured-output tutorial), vendor docs (Cloudflare, ScaleDown, Sarvam, Levanto), model cards / HF repos, DecisionBench + DecisionBench.lol + AIMultiple + IndicJevBench, one peer-reviewed study (arXiv 2610.11978), our own prior learnings (004, 005, 006), and **live calls to the alpha Decisions/Extractions endpoints** (§9–§10). Everything below is cited; where a claim has no source it is labelled **unverified**.
- **Cost:** **$0.000608 total**, against an OpenRouter key capped at **$0.001** (6 free-model requests used of 1,000/day; **$0.000392 remaining — no further paid calls without raising the cap**). §9 cost **$0.00** (free routes only); §10 cost **$0.000608** (paid extraction routes). Reproduce with `backend/scripts/probe_openrouter_decisions.py` (free) and `backend/scripts/probe_openrouter_extractions.py` (paid, requires `--yes-spend`).

## Summary

**No — not as a replacement.** The Decisions API category returns *typed judgments about options you enumerate* (`choice` / `noul` / `score` / `box`); it does **not** return values, spans or strings, so it structurally cannot produce `title`, `author`, `publisher` or `description_work`. The sibling **Extractions API** (`clairic`, `scaledown/extract`, `sage-2`) *does* return values — measured here to extract Telugu/Hindi values from **text** (clairic 5/5, ScaleDown 4/5) but **unable to read a Telugu scan**, so it cannot bypass our OCR bottleneck (§10). The defensible role for decision models here is **complementary**: a *calibrated validator/classifier* behind a measured gate (e.g. "is this extracted span present verbatim in the source?", "which of these language codes?"), not the extractor of record. Verified live (§9): a value-typed field is rejected by the alpha API with HTTP 400, so the "no values" limit is a schema-level guarantee, not a documentation claim.

## Key Findings

### 1. The category is two different things, and OpenRouter is explicit about it

`output_modalities=decisions` selects models that "return typed judgments instead of text" ([Models guide](https://openrouter.ai/docs/guides/overview/models)). OpenRouter's own tutorial states the boundary plainly:

> "Jev doesn't pull out IDs or items, so use it next to the schema call, or instead of it when labels are all you need." — [structured-output tutorial, 2026-11-10](https://openrouter.ai/blog/tutorials/structured-output-llm/)

The four primitives are fixed and closed ([Decisions API reference](https://github.com/OpenRouterTeam/skills/blob/main/skills/openrouter-decisions/references/decisions-api.md)):

| Primitive | Answers | Returns |
|---|---|---|
| `choice` | which of these options? | option + probability per option + confidence |
| `noul` | does this hold? | probability of yes |
| `score` | where on this ordered scale? | expected level + per-level probabilities |
| `box` (Jev 1.14 only) | where in this image? | 4 edge fractions + confidence |

There is a **separate surface** for values — `POST /api/alpha/extractions` — which "asks an extraction model for typed fields" and returns one typed answer per field with `p_null` (probability nothing is present), `confidence`, `span` offsets and `spell_confidence` ([Extractions API guide](https://openrouter.ai/docs/guides/community/extractions)). That route is served by `cloudflare/clairic`, `scaledown/extract`, `levanto/sage-2` and `inception/mercury-decide` (text-only, `text`+`list`). `output_modalities` cannot select it — you filter by `endpoints=/api/alpha/extractions`.

**Consequence for us:** "structured output support" is not evidence of value extraction. A decision model that returns `{"language": {"choice":"telugu","confidence":1.0}}` is *classifying into a list we supply*, not reading a language statement off the title page.

### 2. Question A — can these models extract metadata? Split by field kind

| Sub-task | Decisions category | Extractions category | Notes |
|---|---|---|---|
| Classify into predefined categories (language, form_of_creative_work) | **Yes** | Yes | `choice` over ≤255 enumerated options |
| Identify which of the 49 fields are present | **Yes**, but capped at ~8 questions/request on many models → batch | Yes (`p_null`) | `noul` per field |
| Extract the **actual value** (title/author/publisher strings) | **No** — impossible by contract | **Yes** (`text` field = a span of the input) | The decisive limitation |
| Confidence on extracted values | n/a | Yes (`confidence`, `p_null`) | Genuine advantage over LLM self-report |
| Missing / ambiguous / conflicting info | Good fit — `p_null`, calibrated abstain | `p_null`, `truncated` flag | Best-supported strengths |
| Multi-field recall over 49 fields at once | Poor (question caps, no values) | Plausible (Clairic has no field cap; splits into parallel passes) | Unverified on Indic |

A book title is an open-vocabulary string from noisy OCR; only a model that **generates or spans** text can emit it. Decision models cannot. So the honest mapping for our 49 fields:

- **Closed-set / categorical fields** (language, original_language, form_of_creative_work, rights/licence, some genre flags) → decision-model friendly.
- **Presence/boolean questions** ("is there a title on this page?") → decision-model friendly.
- **Name/text fields** (title, author, label, editor, publisher, place_of_publication, description_work) → need a generative LLM or a span extractor. These are also exactly where our pipeline is weakest today (see §8).

### 3. Question C — OpenRouter Decisions API: mechanics and hard limits

- **Endpoint:** `POST https://openrouter.ai/api/alpha/decisions` (alpha; shape "can change"). Also `POST /api/v1/systemone` for TypeSafe SDK clients.
- **Request:** `model`, `state` (string | object | array, incl. inline images / `assets`), `questions` map keyed by *your* IDs; each question is `type` + `instructions` + `criteria`; optional `session_id`, `user`, `trace`, `provider`.
- **Response:** `answers` keyed by your IDs, each `{type, choice|noul|score|box, probabilities, confidence, legend?}` + `usage.{input_tokens,output_tokens,cost}`. Output tokens are 0 — **you pay input only**.
- **Output format:** only the four primitives. **No arbitrary schema.** You cannot define 49 typed output fields; you can only define 49 *questions* with enumerated criteria for `choice`/`score` and yes/no for `noul`.
- **State/limits (per model page; these are the blockers for book OCR):**

| Model | Context | Platform text cap | Max questions | Choice options |
|---|---|---|---|---|
| `typesafe/jev-1.14` | 262,144 | >~32,000 **bytes** → slower, less accurate long-context mode | not published | ≤255 |
| `sarvam-prism` | 32,768 **per question** | — | no cap | 2–255 |
| `openai/gpt-6-luna-decisions` | 1,050,000 | 32 KiB | 8 | — |
| `microsoft/microsoft-decision-1` | 32,768 | — | 8 | — |
| `nace-ai/drex-*` | 131,072–262,144 | — | 8 | — |
| `upstage/solar-decide-flash` | 524,288 | 32 KiB | 8 | 2–26 |
| `scaledown/classify-1` | 1,000,000 | 32 KiB | 8 | — |
| `cloudflare/clef` / `clef-flash` | — | **2,000 UTF-8 bytes of text state** | 8 | — |
| `togethercomputer/tev1-4b-experimental` | 32,768 | — | — | 2–20 |
| `convaiinnovations/laya` | 8,192 | — | — | 2–100 |
| `jaredpalmer/kev-4b` | 8,192 | — | — | — |

  A 32 KiB platform cap is fatal for whole-book OCR as a single state; you would chunk per page. And decision models are documented to **degrade on long, detail-heavy states** ("tends to lose accuracy when the state it examines carries irrelevant detail", "reads criteria literally", "weak at arithmetic/counting/date comparison") — [Jev vs LLM](https://openrouter.ai/blog/tutorials/jev-vs-llm-when-to-use-each/). Noisy OCR is exactly "irrelevant detail".
- **Multilingual:** no Decisions model publishes a language list except Sarvam Prism (English + 10 Indian languages + Hinglish) and Qwen3.5-derived ones (Mammoth/Elephant/Joey/Microsoft-Decision-1) where Indic support is **unverified**.
- **Self-hosting:** the API is hosted-only, but the *category* now has open weights — see §6.

### 4. The actual models (verified inventory, 2026-11)

Prices are input-only, USD per 1M tokens (output = $0). "Indic evidence" = published, model-specific Hindi/Telugu evidence, not vendor marketing.

| Model | Vendor | Base / size | Context | Price | Notes | Indic evidence |
|---|---|---|---|---|---|---|
| `typesafe/jev-1.14` (+`-1.13`) | TypeSafe | proprietary | 262,144 | $0.042 | The reference model; `box`; images | MMLU-ProX (29 langs) 83.2, MMMLU (14) 85.0 — **aggregate, no per-language Indic split** (arXiv 2610.11978) |
| `sarvam-prism` | Sarvam AI | Sarvam 105B MoE (LoRA) | 32,768/question | ₹4 | Open weights (Apache-2.0); **needs ~120 GB FP8 GPU** | 82.5 on Sarvam's *internal* Indian-language index; 38.4% of Indic answers clear 0.9 confidence (vs 68.5% EN) |
| `cloudflare/clef`, `-flash`, `-omni` | Cloudflare | 27B / small / Qwen3-Omni-30B-A3B | — | $0.038–0.24 | Clef = 2 KB text only; Omni adds audio/video | None |
| `perplexity/pplx-decider-v1.2`, `-flash` | Perplexity | 27B / 4B | 262,144 | $0.01–0.02 | High token volume (488B/wk for 27B) | None (Sarvam benchmark only) |
| `microsoft/microsoft-decision-1` | Microsoft | Qwen3.5-9B | 32,768 | $0.042 | 8 questions max | None |
| `nace-ai/drex-v1.5/v2.0/max` | Nace.AI | <10B / 35B-A3B / max | ≤262,144 | $0.04–0.06 | — | None |
| `liquid/d1.1`, `d1-ultra` | Liquid AI | — | 32,768–65,536 | $0.02–0.042 | Also on Vercel Gateway | None |
| `baseten/mammoth-1`, `elephant-1`, `joey-1` | Base Labs | Qwen3.5-27B / -9B / -2B | 16,384 | $0.01–0.1 | Top of DecisionBench.lol | None |
| `openai/gpt-6-luna-decisions` | OpenAI | proprietary | 1,050,000 | $0.1 | 32 KiB text cap | None |
| `togethercomputer/tev1-4b-experimental` | Together | 4B | 32,768 | $0.042 | Jev contract, ≤20 options | None |
| `scaledown/classify-1` | ScaleDown | — | 1,000,000 | $0.04 | 32 KiB text cap; sits behind Decisions | None |
| `respan/span-01/-02` | Respan | — | ≤131,072 | $0.01–0.02 | Span-01 = `noul` only | None |
| `morph/reflex`, `levanto/sage-2`, `convaiinnovations/laya` | Morph / Levanto / Convai | — | 8,192–65,536 | — | Laya = 421M open weights | **Laya's own BENCHMARKS.md: Hindi 0.430 vs English 0.680; Telugu 0.220; Kannada 0.150** (20-way MASSIVE) |
| **Extractions:** `cloudflare/clairic` | Cloudflare | System One extraction | 65,536 | $0.10 | All field types incl. `estimate`/`forecast`; **open weights promised ("soon")**; images, no PDF | None published |
| **Extractions:** `scaledown/extract` | ScaleDown | constrained-decoding | 1,000,000 | $0.04 | **Built-in OCR — takes a scanned PDF directly**; `text`+`list` only; no `p_null` | None published |

### 5. Question B — comparison with generative LLMs (what the evidence actually shows)

Public benchmarks in this category measure **classification/routing/judging**, never bibliographic value extraction. Read them that way.

- **Decision models ≈ LLMs on labels, worse on reasoning.** OpenRouter's own Jev-vs-LLM runs: accuracy "a wash" on intent triage (59–60/60) at ~¼ the cost of GPT-Luna; but on MathQA Jev is **17.7 points below the frontier median and below all 19 LLMs** (arXiv 2610.11978). DecisionBench.lol (24 models, 5 tests, 10 Nov 2026) puts Mammoth 1 at 90 and ScaleDown Classify-1 last at 7.
- **Calibration is the real differentiator.** In the QuanticData study, *every* Jev mistake carried a hesitant score, while the small LLMs' mistakes carried none; at a 0.8/0.3 accept/reject policy Jev decided 289/317 cases with zero errors. DecisionBench reports ECE/NLL/coverage beside accuracy for exactly this reason. **This is the one capability our pipeline genuinely lacks** (an LLM's self-reported confidence is not calibrated; see §8).
- **Indic is where the category is weakest and least evidenced.**
  - **IndicJevBench** ([cmul8.com](https://www.cmul8.com/research/indicjevbench/)) — 69,402 items, Hindi/Bengali/Tamil/**Telugu**/Kannada/Malayalam/Hinglish intent classification. Baselines on 1,000 items/dataset: `OpenJev` (Qwen3.5-4B, local) acc **0.620** fintech / 0.606 synthetic; `Laya-multilingual` acc 0.256–0.493; GPT-4o-mini highest raw accuracy (0.775 fintech) but loses the composite on latency/cost; **Hinglish collapses for everyone** (GPT-4o-mini 0.175). Note these are intent-classification numbers, not extraction.
  - **Sarvam Prism** is the only decision model openly pitched at Indic (82.5 vs Perplexity 75.0 / Jev 70.8 on *Sarvam's own* index) — but it needs a 120 GB GPU to self-host, and even Sarvam reports **only 38.4% of Indic answers clear 0.9 confidence**.
  - **Jev's only multilingual evidence is aggregate MCQ** (MMLU-ProX 29 langs = 83.2; MMMLU 14 langs = 85.0). **No per-language Hindi/Telugu figure is published** (unverified for our scripts).
- **Hallucination:** a structural win for the Decisions category — it cannot invent a title, because it can only pick your options. That is also why it cannot do the job.

### 6. Self-hosting on our node (4 vCPU / 16 GB, CPU-only)

Since Jev shipped (15 Sep 2026), the ecosystem went open-weight; we can run *typed-decision* models locally via GGUF/llama.cpp (`/v1/systemone`) — [Hugging Face, 2026-11-10](https://huggingface.co/blog/decision):

| Open decision model | Base | Size | Licence | CPU fit on 16 GB |
|---|---|---|---|---|
| **decima-small** | multilingual-e5-small + distillation | 122M | Apache-2.0 (ONNX) | Excellent (~20 ms/decision, 1 core) |
| **Bosun 3.1 1.7B / Bosun-4B** | Qwen3-1.7B / Qwen3-Reranker-4B LoRA | 1.7B / 4B | Apache-2.0 (GGUF) | Good (Bosun 1.7B reported 84.9% DecisionBench) |
| **Laya** | — | 421M | Apache-2.0 | Good |
| **OpenJev / Jev-Style-Qwen3.5-2B** | Qwen3.5-2B/4B | 2–4B | varies | OK |
| **Decido 26B-A4B** | Gemma-4-26B-A4B LoRA | 26B (Q4/Q8) | — | **No** — ~30 GB RAM |
| Sarvam Prism | Sarvam 105B | 105B | Apache-2.0 | **No** — ~120 GB GPU |

So a *local* decision model is feasible; a local **Sarvam-Prism-class Indic** decision model is not, on this box.

Adjacent open-weight options that actually **extract** (all CPU-capable, no cloud):
- **GLiNER2 / GLiNER2.5** (Apache-2.0, `fastino/gliner2.5-multi-v1`, mDeBERTa-v3, ~205–287M): zero-shot span extraction with offsets and scores; "CPU first". **Indic numbers exist**: after the combining-mark splitter fix (v2.1.0), zero-shot F1 on **Telugu NER = 74.4** (from 10.2) and Hindi 75.6 — [HF blog](https://huggingface.co/blog/nishikantmandal007/gliner-indic-scripts). Still below IndicNER (78.6) and it returns *whole words only* (cannot strip Tamil/Hindi suffixes).
- **NuExtract 1.5** (MIT, Phi-3.5-mini base): template-driven JSON extraction, long documents, multilingual — but its supported list is European + 4 others; **Indic not listed** (unverified).
- **GROBID** (Apache-2.0): the classic purpose-built bibliographic/header extractor — 68 labels, CPU, CRF by default. But it is English/scholarly-reference oriented; the PLOS-One comparison shows GROBID's field accuracy on non-English references ~50 points below an in-domain BERT, and no Indic script support. **Not a solution for जन्म-सन्/ప్రచురణ సంవత్సరం headers.**

### 7. Question D — is a hybrid worth it?

OpenRouter publishes the exact pattern we would use, and it matches our gap:

> "Cut LLM Cost with a Jev-Verified Cascade: drafts with a cheap model, **verifies the draft against retrieved context with Jev**, and escalates to a stronger model only when the check fails."

Two hybrids are plausible for us, and they are **not** equal:

1. **LLM extracts values → decision model validates each value.** A `noul` per field: "does the source text contain this exact author string?" Returns a calibrated probability; threshold at ~0.9 → auto-accept, else queue for human review. This is a *precision/hallucination* control and a review-triage tool. Cheap (input-only), short states (the span + a page), fits the 32 KiB caps. **Worth piloting.**
2. **Decision model does the whole extraction.** Not possible for name/text fields; for the ~8 categorical fields it is a small win with a new cloud dependency. **Not worth it as an architecture.**

Expected gain is **precision/hallucination reduction and reviewer triage — not recall.** Our measured failure mode is recall (006): author/title/label P = 1.0, R ≈ 0.13. A validator cannot recover a value the extractor never emitted. So the hybrid addresses the *second* biggest problem, not the first.

### 8. Where this lands against our current pipeline

Current state (from 004/005/006): Telugu OCR CER ≈ 0.45 dominates; micro-F1 0.308 on 8 books with `qwen2.5:3b`; **name/text fields P = 1.0 / R ≈ 0.13** (recall problem); `description_work` F1 0.00; tier-1 regex carries the structured fields; model front-runner `qwen3:4b-instruct-2507` (~½ RAM, ~1.6× the 7B) on the same node.

- The **binding constraint is OCR**, not the extractor. No decision/extraction model changes that; the only one that *bypasses* it is `scaledown/extract`/`clairic` reading the **PDF directly** (Cloudflare's receipt demo; ScaleDown's built-in OCR) — interesting, but with **zero Indic evidence** and cloud-only.
- Decision models **cannot** help recall on `title`/`author`; they *can* certify the values tier-1 and the LLM do emit.
- Our LLM path already emits valid JSON reliably with `qwen3:4b-instruct-2507` (005), so we do not have the "app needs labels, not text" problem that motivates the category.

### 9. Measured probe (2026-11-11, **$0 spent**) — direct verification

Key stored in gitignored `.env` as `OPENROUTER_API_KEY` (documented in `.env.example`, confirmed via `git check-ignore`). `GET /api/v1/key` → `limit 0.001`, `spend 0`, `free_model_daily_requests: 1000`. **Every call below returned `usage.cost = 0`.**

**A — the API itself refuses value extraction.** Sending one question of `{"type": "text", "instructions": "the publisher name, verbatim"}` to `POST /api/alpha/decisions` returns **HTTP 400**: `Invalid discriminator value. Expected 'noul' | 'choice' | 'score' | 'box'` at path `questions.publisher_name.type`. So §1–2 is not just documented but **enforced at the schema layer** — there is no request shape that asks a Decisions model for a value.

**B — closed-set + presence classification works on real Indic title-page text** (`parallel/decisions-fast:free`; the values are verbatim from our GT fixtures, laid out as a title page with light noise):

| Question (primitive) | Telugu | Hindi |
|---|---|---|
| language (choice) | telugu p=0.993, conf 0.992 ✅ | hindi p=0.957, conf 0.946 ✅ |
| has_title (noul) | 0.981 ✅ | 0.911 ✅ |
| form = book (choice) | book p=0.973, conf 0.966 ✅ | book p=0.931, conf 0.914 ✅ |
| has_publisher (noul) | 0.978 ✅ | 0.994 ✅ |
| has_author (noul) | 0.992 ✅ | 0.987 ✅ |
| readability (score) | 2.27 "usable", conf 0.274 | 1.90, conf **0** (degenerate) |
| usage | 6,535 in / 0 out / **$0** | 4,657 in / 0 out / **$0** |

All six probes correct on both scripts. Note the **`criteria` dominate the prompt** (~6.5 K input tokens for 6 questions), matching Clairic's note that "field definitions took 472 of 655 input tokens" — a verbose schema costs more than the text it reads.

**C — behaviour under OCR corruption** (same questions, Telugu state, random glyph substitution at p = 0 / 0.20 / 0.45, i.e. up to ≈ our measured OCR CER):

| p (≈CER) | language (conf) | has_title | has_publisher | readability (conf) |
|---|---|---|---|---|
| 0.00 | telugu 0.994 | 0.943 | 0.972 | 2.51 (0.51) |
| 0.20 | telugu 0.987 | **0.630** | 0.980 | 1.48 (0) |
| 0.45 | telugu 0.980 | **0.359** | **0.312** | 1.34 (0) |

Two actionable readings:
- **Script/language ID is robust to heavy corruption** (0.98 at p=0.45) — script identity survives token damage. Directly relevant: `language` / `original_language` are among our lowest-recall fields today (006: R ≈ 0.25 / 0.13).
- **Presence questions degrade to abstention, not to confident error**: at p=0.45 `has_publisher` = 0.312, i.e. below a 0.5 threshold it answers "not present" rather than asserting a false positive. That is the calibrated-triage behaviour we want — but it also confirms the decision model **cannot rescue recall** on corrupted text; it agrees the evidence is gone.
- Caveat: `score` confidence collapsed to `0` in two of three runs (degenerate distributions) — score answers need checking before trusting.

**D — there is no free-tier extraction route.** `?endpoints=/api/alpha/extractions` returns only `cloudflare/clairic` ($0.10/M in) and `scaledown/extract` ($0.04/M in) — no `:free` variant. The one experiment that would test value extraction (and ScaleDown's OCR bypass) **cannot be run at $0**; the smallest useful request is ≈700–1,000 input tokens ≈ **$0.00004–0.0001**, inside the key's `$0.001` cap but not free. Held pending an explicit go-ahead.

**E — shape warts.** `respan/span-01-lite:free` rejects `choice`/`score` outright (noul only) and its 400 text claims criteria should be "plain strings" while the schema actually demands an **object**; a noul-only request with `criteria: {"true":…,"false":…}` succeeds (0.9999, 171 in tokens, $0). Two free routes exist today: `parallel/decisions-fast:free` (32 K ctx, all primitives) and `respan/span-01-lite:free` (noul only, 171-token prompt).

**F — the catalogue churns fast, confirmed live.** Today's live `output_modalities=decisions` list is **36 entries** (vs the 19/22 in the October write-ups), and `inception/mercury-decide` and `levanto/sage-2` — documented in the OpenRouter Extractions guide — **are absent from today's extractions list**. Treat any model list here as a dated snapshot.

### 10. Measured probe — the Extractions category (paid, **$0.00061 total**, authorised)

Input: a **real** Telugu title page — PDF page 3 of `2015.373190.Athma-Charitramu` (691-page Commons scan) rendered to PNG at 150 dpi — plus the fixture's proofread te.wikisource text of that page, and a synthetic Hindi title page. Five fields: title, author, publisher, place_of_publication, publication_year. (Key spend is now **$0.00061 of the $0.001 cap — no further paid calls without raising it**.)

| Probe | title | author | publisher | place | year | cost |
|---|---|---|---|---|---|---|
| **clairic, page image** | `None` | `Rann Siv` (conf 0.38) | `None` | `GUNTUR` ❌ | `1933` ✅ | $0.00039 (620 img tok, **5 passes**) |
| **clairic, clean text** | ఆత్మచరిత్రము ✅ 0.96 | రాయసము వెంకటశివుఁడు ✅ 0.87 | ఆంధ్ర పత్రికా ముద్రాలయము ✅ 0.98 | మద్రాసు ✅ 0.98 | 1933 ✅ 1.00 | $0.00013 |
| **extract, clean text** | `ఆంధ్రగ్రంథమాల : 22` ❌ 0.74 | రాయసము వెంకటశివుఁడు ✅ 0.57 | ఆంధ్ర పత్రికా ముద్రాలయము ✅ 0.87 | మద్రాసు ✅ 0.85 | 1933 ✅ 1.00 | $0.000016 |
| **extract, page image (own OCR)** | `AUTOBIOGRAPHY:` ❌ | `R. Venkata Sivudu` ~ | `రాజనమం వెంకటేశ్వర…` ❌ conf **0** | `గుంటూరు` ❌ | `None` ❌ | $0.000035 |
| **extract, Telugu text @ p=0.45** | `AUTOBIOGRAPHY` ❌ | `R. Venkata Sivudu` ~ | `రటయహమణ ఆెఝకపశఉవేఊఅు` ❌ **conf 0.81** | `మదకవాోబ` ❌ **conf 0.94** | `1933` ✅ | $0.000016 |
| **extract, Hindi text** | उम्मेदसिंह चरित्र। ✅ 0.52 | लज्जाराम शर्म। ~ 0.44 | श्रीवेंकटेश्वर स्टीम् प्रैस, बम्बई। ✅ 0.23 | बम्बई ✅ 0.98 | 1913 ✅ 0.92 | $0.000013 |

**1 — The category *can* extract Indic values, from text.** clairic scored **5/5** on clean Telugu text (every value with a span, conf 0.87–1.00); ScaleDown Extract got 4/5 Telugu and ~5/5 Hindi, at **$0.00002–0.00013 per page**. This is the study's first measured Indic evidence and it kills the hypothesis that the models don't know our scripts.

**2 — But neither model reads the scan.** clairic's vision returned `None` for the title and publisher and read only the Latin line (`GUNTUR`, `1933`) — it **cannot see Telugu script**. ScaleDown's built-in OCR turned రాయసము వెంకటశివుఁడు into `రాజనమం వెంకటేశ్వర…` and chose Guntur over Madras. So the specialised path **does not bypass our OCR bottleneck** — it consumes the same bad text we already have.

**3 — Cause isolated: vision, not language.** The same clairic model scores 5/5 on the *text* of the same page. Our problem is upstream of the extractor, exactly as 004/006 concluded. Note also `title` was already wrong for ScaleDown on **clean** text (it grabbed the series header line), so span selection is a second, independent error source.

**4 — Worse failure mode than decision models under corruption.** At p=0.45 ScaleDown returned **confident garbage** (conf 0.81 for the publisher, 0.94 for the place) because **Extract reports no `p_null`** — documented, now confirmed — so it *cannot abstain*. The decision models collapsed to ~0.31 on the same corruption (§9-C). For triage, the `noul` layer is the safer gate.

**5 — Cost scales with field count, not just text.** clairic ran **5 passes for 5 fields** (schema 845 tok, image 620 tok; each pass re-reads the state). A 49-field schema on one page is ≈50 passes ≈ 34 K tokens ≈ **$0.003/page** — ~20× the 5-field probe, still far below local LLM wall-clock.

**Verdict:** the Extractions category is a credible **value extractor on clean Indic text** and a cheap second opinion, but it is **not** an OCR bypass and **not** a replacement for the LLM stage while OCR CER ≈ 0.45. Residual caveat: n=1 real Telugu page + 1 synthetic Hindi page, 2 vendors, 5 of 49 fields.

### 11. Limitations of this study (state honestly)

- **Published** evidence for decision/extraction models on Indic *book metadata* does not exist; every external number above is classification/routing or non-Indic. Our own probes are narrow: §9 is n=2 short title pages on one free 32 K-ctx model with *simulated* OCR noise; §10 is **n=1 real Telugu page + 1 synthetic Hindi page, 2 vendors, 5 of 49 fields**. Both are directional, not benchmarks. No external result is invented or extrapolated.
- Several benchmark pages are **vendor-reported** (Sarvam's 82.5 Indic index; ScaleDown's 77.2 DecisionBench vs "Jev's 72") and every comparison in the launch stories is self-published; DecisionBench.lol and DecisionEval are the independent ones and both warn the category is ~2 months old ("nothing that recent has been checked by anyone outside the people who trained it").
- Model capabilities churn fast (aliases like `~typesafe/jev-latest` retarget; Perplexity V1.1 retired mid-study). Any figure should be re-checked at implementation time.
- Sending book OCR to OpenRouter is a **data-egress + new-vendor** decision for a project that self-hosts an open-weight model; production currently carries no traffic (see project memory). That trade needs a product call, not just a benchmark.

## Recommendation

**Do not replace the generative LLM stage. Do not re-architect around the Decisions category.** Concretely:

1. **Keep Qwen (Ollama) as the value extractor** for the 49 fields; it is the only component that can emit open-vocabulary Indic strings, and 005 already established the local model choice.
2. **Keep attacking OCR and recall first** (004/006) — the actual bottleneck; a validator or classifier does not move recall.
3. **Pilot decision models only as a calibrated reviewer/validator** (hybrid #1), behind a measured gate, on *closed-set* fields and value verification — not as a system component until it beats the status quo on our GT.
4. **The OCR-bypass idea is closed (§10).** `clairic` and `scaledown/extract` both *do* return Indic values from text, but neither reads a Telugu scan: clairic's vision returned `None` for everything in Telugu script and read only the Latin line; ScaleDown's built-in OCR mangled the page. Revisit only if a vendor publishes Indic vision/OCR support.
5. **Local open-weight decision models are technically available** (Bosun/decima-small/Laya on CPU) if we ever want a self-hosted classifier; **no local Indic-quality decision model fits 16 GB**, so Sarvam Prism is API-only for us.
6. **Probes done, at $0.00061 of the $0.001 key cap.** §9 de-risks Phase 1 for free (choice/noul work on Telugu+Hindi; language survived p=0.45 corruption); §10 closed Phase 3 with a negative OCR-bypass result. **No further paid calls without raising the cap.**

> Blocked on GT verification: any accuracy comparison must wait for the name/text fields to be human-verified (already a standing next step in 006). Until then treat decision-vs-LLM accuracy as **not comparable**.

## Evaluation & Benchmarking Plan

Reuse the existing harness rather than building new infra: `backend/scripts/evaluate_extraction.py --ground-truth --model … --limit …` and the shared validator `app/services/extraction_validator.py::evaluate_book` (metrics already available: TP/FP/FN, `mean_token_f1`, `exact_match_rate`, `normalized_match_rate`, **hallucinations/absent**). `backend/scripts/score_acc.py` merges single-book JSONL predictions for quick per-field reads. Add a thin decision-model client next to it; do not touch the pipeline.

**Phase 0 — re-establish the baseline (no new dependency).**
Re-run `--ground-truth --include-unverified --limit 8 --model qwen3:4b-instruct-2507` on the node and record per-field P/R/F1 to compare against the `qwen2.5:3b` report (`backend/reports/gt-eval-qwen2.5-3b.json`, micro-F1 0.308). This is the number every later arm must beat.

**Phase 1 — closed-set field classification (cheap, low risk).**
For `language`, `original_language`, `form_of_creative_work`, `rights/licence` (enumerate the allowed code list as `choice` criteria), run one `choice` question per field against the front-matter OCR on the safest Indic-capable model available: **Sarvam Prism** (Sarvam API, Indic-tuned) and, as the open/self-hosted control, **Bosun 1.7B GGUF** or **decima-small ONNX** on the local node.
- Metrics: per-field accuracy vs the LLM's, **plus ECE / Brier** (calibration) and the **auto-accept rate at a 0.9 threshold**.
- Success criterion to proceed: decision-model accuracy ≥ LLM accuracy on these fields **and** ECE ≤ 0.05 (Bosun-class numbers), with ≥1 s median latency headroom. Otherwise stop.

**Phase 2 — value verification / hallucination arm (the real hypothesis).**
After the LLM produces its 49-field dict for a book, send each *emitted* name/text value as a `noul`: "does the source text below contain the author string `…` exactly (modulo whitespace)?" State = the value + the candidate source pages.
- Metrics: **hallucination rate** (validator's `hallucinations/absent`) before vs after gating at 0.9; reviewer workload = share of fields above threshold.
- Success criterion: ≥50% reduction in undetected hallucinations **and** ≥60% of fields auto-clear — otherwise the gate costs more review than it saves.

**Phase 3 — DONE (§10), negative result recorded.**
Ran on one real Telugu title page: `cloudflare/clairic` (image + text) and `scaledown/extract` (text + page image + corrupted text). Outcome: both extract Indic values from **text** (clairic 5/5, ScaleDown 4/5) but **neither reads the scan** — clairic's vision returned `None` for all Telugu-script fields, and ScaleDown's built-in OCR mangled the page. **The OCR-bypass line is closed** (per the pre-declared gate: Indic fields were far below the local LLM on the image path). Re-open only if a vendor ships Indic vision/OCR.

**Cross-cutting rules for every phase.**
- Report **per language (tel/hin) and per field**, never pooled only — pooled averages hide the weak cell (the Indic literature is explicit about this).
- Separate **OCR error from extraction error** by scoring at least one arm on the verified **Wikisource text** (bypass OCR) — already listed as a next step in 006.
- Freeze inputs: same GT books, same page set, same `--limit`; keep the GT scaffold marked *unverified* until Phase 0's spot-check lands, and label results *provisional* accordingly.
- Budget/privacy: Decisions/Extractions calls are third-party egress; get the product call before sending any book text, and cap the probe (a handful of books, input-only pricing is <$0.01/book).

Promote the winning arm (if any) to `plans/007-decision-validation-poc.md` with a Go/No-Go only after Phase 1–2 clear their gates.

## References

- OpenRouter — [Models guide (modalities, `endpoints`)](https://openrouter.ai/docs/guides/overview/models) · [Decisions API reference (skills repo)](https://github.com/OpenRouterTeam/skills/blob/main/skills/openrouter-decisions/references/decisions-api.md) · [Jev hub](https://openrouter.ai/docs/guides/community/jev) · [Extractions API guide](https://openrouter.ai/docs/guides/community/extractions) · [Structured output tutorial, 2026-11-10](https://openrouter.ai/blog/tutorials/structured-output-llm/) · [Jev vs LLM](https://openrouter.ai/blog/tutorials/jev-vs-llm-when-to-use-each/) · [Provider integration](https://openrouter.ai/docs/guides/providers/integration)
- Model catalogues — [OpenRouter decision list](https://openrouter.ai/models?output_modalities=decisions) · [Accelerated Logic snapshot (19 entries, 2026-10-09)](https://acceleratedlogicai.com/blog/openrouter-decision-models-list-pricing-and-api-guide/) · [decisions-api.dev/models](https://decisions-api.dev/models) · [OpenRouter ScaleDown page](https://openrouter.ai/scaledown)
- Extraction models — [Cloudflare Clairic launch](https://blog.cloudflare.com/clairic-extraction-model/) · [Clairic specs](https://systemonemodels.org/models/clairic/) · [ScaleDown extract/classify docs](https://docs.scaledown.ai/api-reference/openai-compatibility) · [Clairic vs GLiNER](https://systemonemodels.org/compare/clairic-vs-gliner/)
- Indic decision models — [IndicJevBench](https://www.cmul8.com/research/indicjevbench/) · [Sarvam Prism blog](https://www.sarvam.ai/blogs/sarvam-prism) · [Sarvam Prism docs (limits, cal.)](https://docs.sarvam.ai/api/token-factory/models/sarvam-prism) · [sarvamai/prism HF](https://huggingface.co/sarvamai/prism) · [Indic typed-decision benchmark proposal (laya's Indic numbers)](https://velofy.co/research/papers/indic-typed-decision-benchmark/) · [DecisionEval multilingual](https://decisioneval.dev/models/language/multilingual/)
- Benchmarks — [DecisionBench](https://hannolabs.ai/field-notes/decisionbench) · [DecisionBench.lol](https://www.decisionbench.lol/) · [AIMultiple decision models](https://aimultiple.com/decision-models) · [arXiv 2610.11978 — Jev vs 19 LLMs](https://arxiv.org/abs/2610.11978) · [QuanticData Jev vs LLMs](https://quanticdata.io/blog/jev-vs-llm-benchmark/)
- Open weights / self-host — [HF: Decision Models in Hugging Face (llama.cpp `/v1/systemone`)](https://huggingface.co/blog/decision) · [Hanno-Labs/bosun-v3.1-1.7b](https://huggingface.co/Hanno-Labs/bosun-v3.1-1.7b) · [Hanno-Labs/bosun-4b-GGUF](https://huggingface.co/Hanno-Labs/bosun-4b-GGUF) · [decido-26b-a4b](https://huggingface.co/decido-ai/decido-26b-a4b) · [amyrmahdy/decima-small](https://huggingface.co/amyrmahdy/decima-small) · [DecisionEval GGUF guide](https://decisioneval.dev/self-host/gguf/)
- Open-weight extractors — [GLiNER2 (Apache-2.0)](https://github.com/fastino-ai/GLiNER2) · [GLiNER Indic scripts fix (Telugu 74.4 F1)](https://huggingface.co/blog/nishikantmandal007/gliner-indic-scripts) · [NuExtract 1.5](https://numind.ai/blog/nuextract-1-5-multilingual-infinite-context) · [GROBID](https://github.com/grobidOrg/grobid) · [non-English metadata extraction vs GROBID (PLOS One)](https://doi.org/10.1371/journal.pone.0280637)
- Internal — [004 OCR CER](004-ocr-stage-cer.md) · [005 LLM model evaluation](005-llm-model-evaluation.md) · [006 first real accuracy](006-first-real-accuracy.md) · Harness: `backend/scripts/evaluate_extraction.py` · Validator: `backend/app/services/extraction_validator.py` · Report: `backend/reports/gt-eval-qwen2.5-3b.json` · Probes: `backend/scripts/probe_openrouter_decisions.py` (free), `backend/scripts/probe_openrouter_extractions.py` (paid, `--yes-spend`)
