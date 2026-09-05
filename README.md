# AI Finance Controller

## Multi-Source Payment Reconciliation + AI Exception Resolution

AI Finance Controller is an intelligent financial reconciliation system that combines deterministic business rules with Generative AI to investigate and resolve payment exceptions.

The system reconciles financial transactions across:

- Internal Ledger
- Bank Settlement
- Optional Payment Gateway

Instead of sending every transaction to an AI model, the system follows a **Rules First, AI Second** architecture.

---

## Problem

Financial teams often reconcile payment data from multiple sources such as internal ledgers, payment gateways, and bank statements.

Common reconciliation problems include:

- Amount mismatches
- Fee differences
- Settlement timing differences
- Missing transactions
- Duplicate transactions
- Refunds
- Chargebacks
- Unclear or unresolved exceptions

Manual investigation of these exceptions is time-consuming and difficult to audit.

---

## Solution

AI Finance Controller automates the reconciliation workflow by combining deterministic reconciliation rules with AI-powered exception investigation.

```text
Internal Ledger ────┐
                    ├──> Rule Engine ──> RECONCILED
Bank Settlement ────┘
                         │
                         ▼
                      EXCEPTION
                         │
                         ▼
                    Gemini AI Agent
                         │
                         ▼
                    Decision Engine
                    ┌────┼────┐
                    ▼    ▼    ▼
                RESOLVED  NEEDS_REVIEW  UNRESOLVED
```

The Payment Gateway can optionally be added as an enrichment source for additional transaction context.

---

## Key Design Principle

### Rules First. AI Second.

Deterministic business rules handle straightforward reconciliation cases.

Only exceptions are sent to Gemini for investigation.

This approach provides:

- Lower AI usage
- Better consistency
- Explainable decisions
- Reduced hallucination risk
- Clear auditability
- Efficient exception processing

The AI does not blindly modify financial records.

---

## Reconciliation Flow

```text
Raw Data
   ↓
Ingestion
   ↓
Validation
   ↓
Normalization
   ↓
Unified Transactions
   ↓
Rule-Based Reconciliation
   ↓
Exception Detection
   ↓
Gemini AI Exception Analysis
   ↓
Decision Engine
   ↓
PostgreSQL
   ↓
FastAPI
   ↓
React Dashboard
```

---

## Data Sources

### 1. Internal Ledger

Contains the organization's internal transaction records.

Typical information includes:

- Transaction ID
- Order ID
- Invoice ID
- Transaction date
- Amount
- Currency
- Customer ID
- Reference ID

### 2. Bank Settlement

Contains bank-side settlement information.

Typical information includes:

- Bank reference
- Gateway reference
- Settlement date
- Settlement amount
- Bank fee
- Currency
- Transaction type

### 3. Payment Gateway — Optional

Payment Gateway data provides additional context such as:

- Gateway reference
- Order ID
- Gross amount
- Fee
- Net amount
- Currency
- Refund amount
- Chargeback amount

The system is designed to work with the mandatory Internal Ledger + Bank Settlement sources even when Gateway data is unavailable.

---

## Exception Types

The system currently identifies the following exception categories:

| Exception Type | Description |
|---|---|
| `FEE_DIFFERENCE` | Expected and actual fees differ |
| `TIMING_DIFFERENCE` | Settlement occurred outside the expected settlement window |
| `AMOUNT_MISMATCH` | Transaction amounts do not match |
| `MISSING_RECORD` | A required transaction record is missing |
| `DUPLICATE` | Duplicate transaction or order detected |
| `REFUND` | Refund transaction detected |
| `CHARGEBACK` | Chargeback transaction detected |
| `UNKNOWN` | Exception cannot be safely classified |

---

## Final Statuses

The system produces four final statuses.

### RECONCILED

The transaction satisfies the deterministic reconciliation rules.

### RESOLVED

An exception has sufficient evidence for AI-assisted resolution.

### NEEDS_REVIEW

The available evidence is insufficient, contradictory, or uncertain and human review is recommended.

### UNRESOLVED

The exception cannot be safely resolved using the available information.

---

## AI Exception Investigation

Gemini is used as an **exception investigation agent**, rather than an unrestricted financial decision maker.

The AI is instructed to:

- Use only the supplied transaction evidence
- Never invent missing financial information
- Never fabricate amounts, dates, fees, or references
- Separate facts from possible explanations
- Avoid proposing unsupported corrected values
- Identify insufficient or contradictory evidence
- Recommend human review when appropriate
- Provide an explanation for its conclusion
- Recommend a safe next action

The AI does not directly modify financial records.

The deterministic Decision Engine evaluates the AI response before assigning the final status.

---

## Decision Architecture

```text
Rule Engine
     │
     ├── MATCHED
     │      │
     │      └──> RECONCILED
     │
     └── EXCEPTION
            │
            ▼
       Gemini AI Agent
            │
            ▼
       AI Analysis
            │
            ▼
       Decision Engine
            │
       ┌────┼─────────────┐
       ▼    ▼             ▼
   RESOLVED  NEEDS_REVIEW  UNRESOLVED
```

`MATCHED` is an intermediate rule-engine classification.

The final system statuses are:

```text
RECONCILED
RESOLVED
NEEDS_REVIEW
UNRESOLVED
```

---

## Dataset

The project includes a synthetic reconciliation benchmark containing multiple realistic financial scenarios.

### Current Demo Dataset

- **121 transactions**
- 50+ records required by the buildathon
- Internal Ledger records
- Bank Settlement records
- Payment Gateway records
- Ground-truth scenario labels

The dataset contains scenarios such as:

- Clean matches
- Fee differences
- Timing differences
- Amount mismatches
- Missing records
- Duplicates
- Refunds
- Chargebacks
- Unresolved cases

---

## Demo Results

The current demo pipeline processed **121 transactions**.

| Final Status | Count |
|---|---:|
| RECONCILED | 56 |
| RESOLVED | 30 |
| NEEDS_REVIEW | 35 |
| UNRESOLVED | 0 |
| **Total** | **121** |

This demonstrates the complete flow from deterministic reconciliation to AI-powered exception investigation and decision making.

---

## External Benchmark

The reconciliation engine was additionally evaluated on a separate external benchmark containing **150 economic orders**.

### Results

| Metric | Result |
|---|---:|
| Rule Outcome Accuracy | **88.67%** |
| Exception Classification Accuracy | **85.07%** |
| End-to-End Final Status Accuracy | **55.33%** |

The **88.67%** figure refers specifically to **rule-outcome accuracy**, not overall AI accuracy.

The lower end-to-end final-status accuracy is largely influenced by the benchmark containing many cases labelled as `UNRESOLVED`, while the AI layer attempts to resolve or escalate exceptions when sufficient evidence is available.

---

## Technology Stack

### Backend

- Python 3.11+
- FastAPI
- Pydantic
- Pandas
- SQLAlchemy
- PostgreSQL

### AI

- Google Gemini API
- `google-genai`
- Gemini 3.1 Flash Lite

### Frontend

- React
- Vite
- Tailwind CSS

### Development

- Git
- GitHub
- Python Virtual Environment

---

## Project Architecture

```text
                    ┌─────────────────────┐
                    │    Internal Ledger  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Bank Settlement   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     Ingestion &     │
                    │    Normalization    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Unified Transaction │
                    │       Model         │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     Rule Engine     │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
                RECONCILED            EXCEPTION
                                          │
                                          ▼
                                ┌─────────────────┐
                                │   Gemini AI     │
                                │ Exception Agent │
                                └────────┬────────┘
                                         │
                                         ▼
                                ┌─────────────────┐
                                │ Decision Engine │
                                └────────┬────────┘
                                         │
                         ┌───────────────┼───────────────┐
                         ▼               ▼               ▼
                     RESOLVED      NEEDS_REVIEW     UNRESOLVED
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │  PostgreSQL  │
                                  └──────┬───────┘
                                         │
                                         ▼
                                   ┌───────────┐
                                   │  FastAPI  │
                                   └─────┬─────┘
                                         │
                                         ▼
                                   ┌───────────┐
                                   │   React   │
                                   │ Dashboard │
                                   └───────────┘
```

The Payment Gateway is an optional enrichment source that can provide additional context to the reconciliation engine.

---

## Project Structure

```text
AI Reconciliation/
│
├── data/
│   ├── external/
│   ├── processed/
│   └── raw/
│
├── docs/
│
├── frontend/
│   ├── public/
│   ├── src/
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
│
├── scripts/
│   └── generate_dataset.py
│
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
│
├── .gitignore
└── README.md
```

---

## Database

PostgreSQL stores reconciliation results and AI investigation information.

Stored information includes:

- Transaction ID
- Final status
- Exception type
- Difference
- Resolution
- Confidence score
- AI explanation
- Recommended action
- Human review requirement
- Timestamp

This provides an auditable record of reconciliation decisions.

---

## API

The backend is exposed through FastAPI.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/reconcile` | Run reconciliation pipeline |
| `GET` | `/results` | Retrieve reconciliation results |
| `GET` | `/results/{transaction_id}` | Retrieve a specific transaction result |
| `GET` | `/summary` | Retrieve reconciliation summary |

Interactive API documentation is available through FastAPI Swagger UI.

---

## Running the Backend

### 1. Create Virtual Environment

```bash
python -m venv .venv
```

### 2. Activate Environment

Windows:

```bash
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install fastapi uvicorn pydantic pandas python-dotenv sqlalchemy psycopg2-binary google-genai
```

### 4. Configure Environment Variables

Create:

```text
src/.env
```

Add:

```env
GEMINI_API_KEY=your_gemini_api_key
DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:1234/ai_reconciliation
```

> Never commit `.env` or API keys to GitHub.

### 5. Start FastAPI

From the project root:

```bash
uvicorn src.api:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

---

## Running the Frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on:

```text
http://localhost:5173
```

---

## Dashboard

The React dashboard provides:

- Reconciliation overview
- Transaction results
- Exception monitoring
- Analytics
- Audit information
- AI Finance Agent insights
- Reconciliation execution

---

## AI Usage Strategy

The system is designed to minimize unnecessary AI calls.

```text
                 All Transactions
                       │
                       ▼
                  Rule Engine
                   /                         /                          ▼           ▼
        Straightforward   Exception
              │               │
              ▼               ▼
         RECONCILED        Gemini AI
                               │
                               ▼
                         Decision Engine
```

This allows deterministic cases to be processed without consuming AI quota.

Only exceptions require AI investigation.

---

## Why This Architecture?

The system deliberately avoids using AI for every transaction.

For a straightforward transaction:

```text
Transaction
    ↓
Rule Engine
    ↓
RECONCILED
```

For an exception:

```text
Transaction
    ↓
Rule Engine
    ↓
EXCEPTION
    ↓
Gemini Investigation
    ↓
Evidence-Based Analysis
    ↓
Decision Engine
    ↓
Final Status
```

This creates a balance between:

**Automation + Accuracy + Explainability + Cost Efficiency**

---

## Future Scope

### Machine Learning

The current MVP uses deterministic rules and Generative AI.

A future ML layer can learn from:

- Historical reconciliation outcomes
- Confirmed exception resolutions
- Human-reviewed cases
- Merchant/payment behavior
- Recurring exception patterns

Potential future capabilities include:

- Exception prediction
- Anomaly detection
- Resolution recommendation ranking
- Merchant-specific reconciliation patterns
- Adaptive confidence scoring

---

## Security & Reliability Considerations

The system follows several principles for financial data processing:

- API keys are stored in environment variables
- `.env` files are excluded from Git
- Financial calculations are primarily deterministic
- AI operates only on supplied evidence
- AI cannot directly modify source records
- Uncertain cases can be escalated for human review
- Reconciliation results are persisted for auditability

---

## Buildathon Track

**Track:** Multi-Source Reconciliation

The project demonstrates an AI-powered reconciliation workflow that combines:

**Multi-source financial data + deterministic reconciliation + Gemini AI exception investigation + explainable decisions + auditability**

---

## Conclusion

AI Finance Controller transforms payment reconciliation from a largely manual investigation process into an automated, explainable workflow.

The core philosophy is simple:

> **Rules first. AI second. Human review when necessary.**

This allows the system to automate routine reconciliation while using Generative AI where it provides the most value — investigating complex financial exceptions.

---
