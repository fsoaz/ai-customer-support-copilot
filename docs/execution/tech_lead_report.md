# Tech Lead Briefing & Alignment Report: `ai-customer-support-copilot`

**From:** Tech Lead  
**To:** Engineering Team (Senior Engineer & Mid-level Engineer)  
**Subject:** Current Project Status, Architectural Directives, and Immediate Starting Point  

---

## 1. Product Vision & V1 Scope (The "Wedge")

The **AI Customer Support Copilot** is a multi-tenant SaaS designed to assist Tier-1 customer support agents.

* **V1 Core Product:** A sidebar app natively integrated into **Zendesk** (ZAF v2). When an agent opens a ticket, the copilot streams a draft reply where **every factual claim carries an inline citation** linked directly to the knowledge base (KB) chunk it originated from.
* **Key Business Metrics:** 10–20% reduction in agent handle time on KB-covered tickets, and a draft acceptance rate $\ge 40\%$ (measured via `edit_distance_ratio`).
* **Explicit V1 Non-Goals:** No auto-triage, thread summarization, customer-facing self-service widgets, autonomous agentic actions (refunds, escalations), or complex analytics dashboards. The single focus is delivering grounded, citation-backed draft replies.

---

## 2. Architecture Philosophy & Technical Principles

We adopt a lean infrastructure strategy ("boring infrastructure") paired with strict multi-tenancy and evaluation discipline:

### Target Tech Stack
* **Backend:** FastAPI (Python 3.12 managed via `uv`), single container on Fly.io.
* **Database & Retrieval:** Supabase Postgres 15+ (`pgvector` for HNSW dense search, `tsvector`/GIN for lexical FTS, RLS enforced on all tables, job queue via `FOR UPDATE SKIP LOCKED`).
* **Admin Frontend:** Next.js (App Router) on Vercel.
* **Agent UI:** Zendesk Apps Framework (ZAF v2 sidebar iframe).
* **Observability & Evals:** Langfuse + OpenTelemetry.

### Non-Negotiable Operating Principles
1. **Slice, don't layer:** Progression occurs through functional stages, each ending with an objective, blocking quantitative gate.
2. **Riskiest assumption first:** Retrieval quality determines whether the product is viable. It is answered **offline, without UI, and without application code**.
3. **Native Multi-Tenancy on Commit 1:** `tenant_id` and Row Level Security (RLS) policies on every Supabase table from the very first migration.
4. **Quality Telemetry:** Rather than recording a binary `agent_accepted` boolean, we store the final sent text and compute `edit_distance_ratio` (a continuous, high-signal ROI metric).

---

## 3. Current Repository Status (Where We Stand Today)

We are currently in **Stage 0 — Prove Retrieval**.

> [!IMPORTANT]
> **Product API code, UI, Supabase migrations, and Zendesk integrations do NOT exist in the repository yet** by intentional design. We do not build product plumbing before proving the retrieval hypothesis.

### Current On-Disk Layout
* [`docs/`](file:///mnt/disk1/Documents/Git/ai-customer-support-copilot/docs/): Internal working notebook (architecture, roadmap, decisions, and evidence).
* [`backend/evals/`](file:///mnt/disk1/Documents/Git/ai-customer-support-copilot/backend/evals/): The sole functional package on disk — a local scientific evaluation harness (Python + SQLite + FTS5 + `fastembed` + `flashrank`).
* **Corpus & Dataset:** 1,734 Auth0 documentation pages (MIT) + a golden dataset of 359 answerable and 31 unanswerable community Q&A pairs.

### Stage 0 Gate Status
* **Gate Thresholds (Blocking):** `recall@10 ≥ 0.85` and `MRR ≥ 0.60`.
* **Current Best Result (Task 0.6):** `recall@10 = 0.368` and `MRR = 0.192` (using `bge-base`, 256-token chunks, and RRF with `dense_weight=2`). **Status: FAIL**.

---

## 4. Current Bottleneck & Immediate Next Step (Task 0.7)

First-stage candidate audit (`analyze_first_stage`) revealed:
1. **Candidate Recall is Solvability-Capable:** At `pool@500`, first-stage hybrid search recovers the correct document for **88.3%** of questions (`fused_hit = 0.883`). However, the RRF ranking pushes the correct document outside top-10 (`recall@10 ≈ 0.33–0.36`).
2. **Golden Label Noise (BUG-014):** Hand audits confirmed $\sim 20\%$ noise in the golden dataset (e.g., questions about SMTP linking to an allowlist article as gold). Measured recall was penalizing valid retrieval for missing contaminated labels.

### Active Focus: Task 0.7 (Golden-Label Remediation)
We have halted pure embedding model sweeps. The active task is **remediating golden set labels** (Task 0.7):
* Re-judge and fix noisy question/document pairs in `retrieval_golden.jsonl`.
* Re-run retrieval against the remediated set to establish a trusted baseline.
* Evaluate whether the `0.85` gate is achievable or if reranker upgrades (e.g., GPU Cross-Encoder) are required.

---

## 5. High-Level Roadmap Overview

```
[Stage 0] Prove Retrieval (Offline / Evals) ──► ACTIVE HERE (Task 0.7)
       │ (Gate: recall@10 >= 0.85, MRR >= 0.60)
       ▼
[Stage 1] Grounded Generation Backbone (FastAPI + LLM + Citations + RLS)
       │ (Gate: Groundedness >= 0.95, TTFT < 1.5s, Cost < $0.03)
       ▼
[Stage 2] Zendesk Integration & Pilot (ZAF Sidebar + Pilot Baseline)
       │ (Gate: Draft acceptance >= 40%)
       ▼
[Stage 3] Commercial SaaS Product (Next.js Admin + Stripe Billing)
```

---

## 6. Required Reading & Onboarding Tasks

To prepare for planning, read the internal documentation in this exact order:

1. **Product Vision:** [`docs/context/product.md`](file:///mnt/disk1/Documents/Git/ai-customer-support-copilot/docs/context/product.md)
2. **Sequencing & Gates:** [`docs/context/roadmap.md`](file:///mnt/disk1/Documents/Git/ai-customer-support-copilot/docs/context/roadmap.md)
3. **Technical Design & Schemas:** [`docs/context/architecture.md`](file:///mnt/disk1/Documents/Git/ai-customer-support-copilot/docs/context/architecture.md)
4. **Current Disk Layout:** [`docs/context/structure.md`](file:///mnt/disk1/Documents/Git/ai-customer-support-copilot/docs/context/structure.md)
5. **Active Task:** [`docs/execution/current_task.md`](file:///mnt/disk1/Documents/Git/ai-customer-support-copilot/docs/execution/current_task.md)
6. **Measured Evidence:** [`docs/execution/test_evidence.md`](file:///mnt/disk1/Documents/Git/ai-customer-support-copilot/docs/execution/test_evidence.md)

### Initial Task Breakdown
* **Senior Engineer:** Review the evaluation harness in `backend/evals/`, the Postgres/RLS schema design in [`architecture.md`](file:///mnt/disk1/Documents/Git/ai-customer-support-copilot/docs/context/architecture.md#data-model), and architect the golden label remediation/validation workflow (BUG-014).
* **Mid-Level Engineer:** Run and explore the evaluation scripts in `backend/evals/scripts/`, review metric outputs in [`test_evidence.md`](file:///mnt/disk1/Documents/Git/ai-customer-support-copilot/docs/execution/test_evidence.md), and assist in re-judging target golden pairs for Task 0.7.
