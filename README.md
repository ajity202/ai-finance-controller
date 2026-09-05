# AI Finance Controller

### Multi-Source Payment Reconciliation + AI Exception Resolution

AI Finance Controller reconciles payment data across an Internal Ledger, Bank Settlement statements, and an optional Payment Gateway feed. It follows a **Rules First, AI Second** architecture: deterministic rules close every transaction they can, and only genuine exceptions are handed to an LLM for investigation.

---

## Problem

Financial teams reconcile payment data from multiple, independent sources — ledgers, gateways, bank statements — that rarely agree perfectly. Common issues include amount mismatches, fee differences, settlement timing gaps, missing or duplicate transactions, refunds, and chargebacks. Investigating these by hand is slow and hard to audit.

## Architecture 

![AI Finance Controller Architecture](docs/architecture.png)

```text
Internal Ledger ──┐
Bank Settlement ──┼──> Ingestion & Normalization ──> Unified Transaction Model
Payment Gateway* ─┘                                          │
                                                              ▼
                                                        Rule Engine
                                                              │
                                        ┌─────────────────────┴─────────────────────┐
                                        ▼                                           ▼
                                   RECONCILED                                  EXCEPTION
                                                                                    │
                                                                                    ▼
                                                                          Gemini AI Agent
                                                                                    │
                                                                                    ▼
                                                                          Decision Engine
                                                                                    │
                                                      ┌─────────────────────────────┼──────────────────────┐
                                                      ▼                             ▼                      ▼
                                                 RESOLVED                    NEEDS_REVIEW             UNRESOLVED
                                                              │
                                                              ▼
                                                PostgreSQL ──> FastAPI ──> React Dashboard
```
*Payment Gateway is optional — the system works with Ledger + Bank alone.*

**Why rules first?** Deterministic logic handles every case it can prove — cheaper, faster, consistent, and fully explainable. The AI is only invoked for what's left, which keeps AI usage low, auditability high, and hallucination risk contained. The AI never modifies financial records directly; the Decision Engine evaluates its output before any status is finalized.

---

## Data Sources

| Source | Required | Key Fields |
|---|---|---|
| **Internal Ledger** | Yes | Transaction ID, Order ID, Invoice ID, Transaction date, Amount, Currency, Customer ID, Reference ID |
| **Bank Settlement** | Yes | Bank reference, Gateway reference, Settlement date, Settlement amount, Bank fee, Currency, Transaction type |
| **Payment Gateway** | Optional | Gateway reference, Order ID, Gross amount, Fee, Net amount, Currency, Refund amount, Chargeback amount |

## Exception Types

| Type | Meaning |
|---|---|
| `FEE_DIFFERENCE` | Expected and actual fees differ |
| `TIMING_DIFFERENCE` | Settlement fell outside the expected window |
| `AMOUNT_MISMATCH` | Transaction amounts don't match |
| `MISSING_RECORD` | A required record is missing on one side |
| `DUPLICATE` | Duplicate transaction or order detected |
| `REFUND` | Refund transaction detected |
| `CHARGEBACK` | Chargeback transaction detected |
| `UNKNOWN` | Cannot be safely classified |

## Final Statuses

| Status | Meaning |
|---|---|
| `RECONCILED` | Closed by deterministic rules alone |
| `RESOLVED` | AI found sufficient evidence to explain the exception |
| `NEEDS_REVIEW` | Evidence is uncertain or contradictory — human review recommended |
| `UNRESOLVED` | Cannot be safely resolved with available information |

`MATCHED` is an intermediate Rule Engine classification that leads to `RECONCILED`; it is never a final status.

## AI Exception Investigation

Gemini acts as an **investigation agent**, not an unrestricted decision-maker. It is instructed to:

- Use only the supplied evidence — never invent amounts, dates, fees, or references
- Separate facts from possible explanations
- Flag insufficient or contradictory evidence rather than guessing
- Recommend human review when appropriate, with an explanation and a safe next action

The Decision Engine evaluates every AI response before assigning a final status; the AI cannot write directly to financial records.

---

## Dataset & Results

**Demo dataset:** 121 synthetic transactions (Ledger + Bank + Gateway) with ground-truth labels covering clean matches, fee/timing/amount discrepancies, missing records, duplicates, refunds, chargebacks, and unresolved cases.

| Final Status | Count |
|---|---:|
| RECONCILED | 56 |
| RESOLVED | 30 |
| NEEDS_REVIEW | 35 |
| UNRESOLVED | 0 |
| **Total** | **121** |

**External benchmark:** a separate 150-order dataset used to stress-test the pipeline.

| Metric | Result |
|---|---:|
| Rule Outcome Accuracy | **88.67%** |
| Exception Classification Accuracy | **85.07%** |
| End-to-End Final Status Accuracy | **55.33%** |

The 88.67% figure is rule-outcome accuracy specifically, not overall AI accuracy. The lower end-to-end figure largely reflects the benchmark's many `UNRESOLVED`-labeled cases, which the AI layer sometimes attempts to resolve or escalate when it finds partial evidence.

---

## Technology Stack

| Layer | Stack |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic, Pandas, SQLAlchemy, PostgreSQL |
| AI | Google Gemini API (`google-genai`, Gemini 3.1 Flash Lite) |
| Frontend | React, Vite, Tailwind CSS |
| Tooling | Git, GitHub, Python venv |

## Project Structure

```text
AI Reconciliation/
├── data/
│   ├── external/
│   ├── processed/
│   └── raw/
├── docs/
├── frontend/
│   ├── public/
│   ├── src/
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
├── scripts/
│   └── generate_dataset.py
├── src/
│   ├── api.py
│   ├── database.py
│   ├── decision_engine.py
│   ├── evaluate_ai_pipeline.py
│   ├── evaluate_results.py
│   ├── ingestion.py
│   ├── llm_agent.py
│   ├── model.py
│   ├── pipeline.py
│   ├── rule_engine.py
│   └── .env.example
├── .gitignore
└── README.md
```

## Database

PostgreSQL stores every reconciliation decision for auditability: transaction ID, final status, exception type, computed difference, resolution, confidence score, AI explanation, recommended action, human-review flag, and timestamp.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/reconcile` | Run the reconciliation pipeline |
| `GET` | `/results` | Retrieve all reconciliation results |
| `GET` | `/results/{transaction_id}` | Retrieve a specific transaction's result |
| `GET` | `/summary` | Retrieve the reconciliation summary |

Interactive docs are available via FastAPI's Swagger UI.

---

## Getting Started

### Backend

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install fastapi uvicorn pydantic pandas python-dotenv sqlalchemy psycopg2-binary google-genai
```

Create `src/.env`:

```env
GEMINI_API_KEY=your_gemini_api_key
DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:1234/ai_reconciliation
```

> Never commit `.env` or API keys to GitHub.

```bash
uvicorn src.api:app --reload
```

Backend: `http://127.0.0.1:8000` · Swagger docs: `http://127.0.0.1:8000/docs`

> PostgreSQL must be running with the `ai_reconciliation` database configured before starting the backend.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

The dashboard provides a reconciliation overview, transaction-level results, exception monitoring, analytics, audit trails, and AI-agent insights.

---

## Security & Reliability

- API keys live in environment variables; `.env` is git-ignored
- Financial calculations are deterministic wherever possible
- AI operates only on supplied evidence and cannot write to source records
- Uncertain cases escalate to human review instead of being guessed at
- Every reconciliation decision is persisted for audit

## Future Scope

A future ML layer could learn from historical outcomes, confirmed resolutions, and human-reviewed cases to support exception prediction, anomaly detection, resolution ranking, and adaptive confidence scoring.

---

## Buildathon Track

Built for the **Razorpay Buildathon — Multi-Source Reconciliation track**, demonstrating multi-source financial data ingestion, deterministic reconciliation, Gemini-powered exception investigation, and explainable, auditable decisions.

> **Rules first. AI second. Human review when necessary.**

**Team:** AI Finance Controller
