# GCP Test Nodes — Inventory & Live Task Tracker

**This is a living document.** Last updated: 2026-11-10.

Single source of truth for the temporary GCP Compute Engine nodes used for parallel testing.
The nodes are **generic**: any task can be assigned to them (LLM/OCR benchmarking, pipeline
load tests, dependency experiments, or anything else) — they are not tied to one workload.

---

## 1. How to use this file

1. **Read this file before creating or using any GCP resource.**
2. **Claim a node before installing anything.** Edit its row in §4 (status → `claimed`,
   `Current task` → short slug, `Owner` → you) and add a matching instance label:
   `gcloud compute instances add-labels test-node-N --labels=task=<slug> --zone=asia-south1-c`
3. **One CPU/RAM-heavy task per node.** Do not run two parallel workloads on the same node —
   results must be attributable and not resource-contended.
4. **Update the row when you start (`running`), block (`blocked`), or finish.** Record where
   results live (path/URL) in the Notes column, then free the node (`idle`, `unassigned`).
5. **Never modify pre-existing resources** (§6).
6. **Respect the spend guardrails** (§2). Prefer `stop` over leaving a node idle.

---

## 2. Guardrails (do not exceed)

| Item | Value |
|---|---|
| Project | `algogini-gcp` (`505492538410`) |
| Billing account | `017CBF-BA60CB-3D175B` (INR, open) |
| Budget alert | `llm-benchmark hard cap (algogini-gcp)` — **Rs 3000**, alerts at 50 / 80 / 100 % |
| Node cost (estimate) | `e2-standard-4` ≈ US$0.134–0.162/hr ≈ **Rs 14/hr per node** (asia-south1, on-demand) |
| All three nodes | ≈ **Rs 42/hr** combined |
| Boot disk | 50 GB pd-balanced ≈ Rs 0.7/hr per node while running |
| Hard cap translation | Rs 3000 ≈ ~210 node-hours ≈ 70 h with all three running |
| Operational rule | Delete nodes at task end. If idle for more than a few hours, **stop** them instead of leaving them running. |

Cost figures are estimates (regional avg on-demand price); the budget alert reports actual spend.
Cloud Billing's public API exposes **no** credit-balance endpoint, so trial credit remaining is
not machine-readable — the budget + this cap are the enforcement mechanism.

---

## 3. Node inventory

All three nodes are identical so results are comparable across them.

| Node | GCE ID | Zone | Machine type | vCPU / RAM | Boot disk | Internal IP | External IP |
|---|---|---|---|---|---|---|---|
| test-node-1 | 8694400015119873311 | asia-south1-c | e2-standard-4 | 4 / 16 GB | 50 GB pd-balanced | 10.160.0.10 | 35.200.150.62 |
| test-node-2 | 2043148591779738880 | asia-south1-c | e2-standard-4 | 4 / 16 GB | 50 GB pd-balanced | 10.160.0.8 | 35.200.231.164 |
| test-node-3 | 1380574741623928064 | asia-south1-c | e2-standard-4 | 4 / 16 GB | 50 GB pd-balanced | 10.160.0.9 | 34.93.24.253 |

- Created: 2026-11-10. Base image: **Ubuntu 22.04.5 LTS**, clean (no task-specific deps preinstalled).
- Verified on all three: `nproc` = 4, RAM ≈ 15.99 GB, `/` = 49 GB usable.
- External IPs are **ephemeral** — they change if a node is stopped and started. Re-read the
  table (or re-run the inventory command in §7) after any stop/start.

---

## 4. Live task tracker

| Node | Status | Current task | Owner | Since | Notes / results |
|---|---|---|---|---|---|
| test-node-1 | claimed | resource-profile | Qoder agent | 2026-11-10 | Peak CPU/RAM sampling of OCR+LLM pipeline; serial single-book config. Results → `learnings/`. |
| test-node-2 | idle | unassigned | — | 2026-11-11 | `llm-model-eval` done: resource/speed/JSON sweep (7 models) + accuracy on verified Telugu Athma — `gemma4:e4b` 0.636 › `qwen3.5:4b` 0.545 › `qwen3:4b-2507` 0.182 › `qwen2.5:7b` 0.091 → [learnings/005](../learnings/005-llm-model-evaluation.md). Node **stopped** (spend guardrail); Ollama container + models persist on disk for restart. |
| test-node-3 | idle | unassigned | — | 2026-11-11 | GT accuracy eval done — 8 books, `qwen2.5:3b`, micro-F1 **0.308** → [learnings/006](../learnings/006-first-real-accuracy.md); report `backend/reports/gt-eval-qwen2.5-3b.json`. **Node stopped** (disk retains code+GT+models for fast restart). |

Status values: `idle` · `claimed` (setup) · `running` · `blocked`.
Keep this table and the instance `task` label in sync.

---

## 5. Quotas & headroom (observed 2026-11-10)

| Quota | Scope | In use / Limit | Headroom |
|---|---|---|---|
| `CPUS_ALL_REGIONS` | global | 14 / 16 | **2 vCPU — the binding constraint** |
| `CPUS` | asia-south1 | 14 / 100 | 86 |
| `INSTANCES` | asia-south1 | 4 / 24 | 20 |
| `DISKS_TOTAL_GB` | asia-south1 | 50 / 2458 | large |
| `IN_USE_ADDRESSES` | asia-south1 | 4 / 8 | 4 |

The **global 16 vCPU cap** is what limits how many 4-vCPU nodes can exist at once. With
`algogini-prod` holding 2 vCPU, three 4-vCPU nodes consume 14 of 16. The three nodes cannot
run alongside a fourth 4-vCPU node without a quota increase.

---

## 6. Pre-existing resources — DO NOT MODIFY OR DELETE

| Resource | Type | Note |
|---|---|---|
| `algogini-prod` | instance (e2-standard-2, asia-south1-c) | Production server |
| `algogini-prod-ip` | reserved static IP (34.93.242.151) | Production address |
| `algogini-prod-*` daily snapshots (14) + `algogini-prod-preresize-20261110` | snapshots | Production backups — unrelated to this task |

Anything not listed in §3 was not created for this task and must be left alone.

---

## 7. Lifecycle commands

```bash
# Inventory (re-run after any create/stop/start — IPs are ephemeral)
gcloud compute instances list \
  --format="table(name,id,zone.basename(),machineType.basename(),networkInterfaces[0].networkIP,networkInterfaces[0].accessConfigs[0].natIP,status,labels.task)"

# SSH
gcloud compute ssh test-node-1 --zone=asia-south1-c

# Stop when idle (keeps disk, frees vCPU, costs far less)
gcloud compute instances stop test-node-1 --zone=asia-south1-c

# Start again
gcloud compute instances start test-node-1 --zone=asia-south1-c

# Delete a finished node (boot disk auto-deletes)
gcloud compute instances delete test-node-1 --zone=asia-south1-c --quiet

# Verify nothing billable from this task remains (expect only pre-existing resources)
gcloud compute instances list
gcloud compute disks list
gcloud compute addresses list
```

---

## 8. Change log

| Date | Change |
|---|---|
| 2026-11-10 | Three `test-node-{1,2,3}` created (4 vCPU / 16 GB / 50 GB, asia-south1-c). Budget cap Rs 3000 created. Nodes idle, unassigned. |
