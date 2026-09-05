import os
import sys
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --------------------------------------------------
# PATH SETUP
# --------------------------------------------------

SRC_DIR = os.path.dirname(os.path.abspath(__file__))

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

load_dotenv(os.path.join(SRC_DIR, ".env"))

# --------------------------------------------------
# IMPORT PROJECT MODULES
# --------------------------------------------------

from pipeline import run_reconciliation_pipeline
from database import SessionLocal, ReconciliationResultDB


# --------------------------------------------------
# FASTAPI APP
# --------------------------------------------------

app = FastAPI(
    title="AI Finance Controller API",
    description="AI-powered multi-source payment reconciliation system",
    version="1.0.0",
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# REQUEST MODEL
# --------------------------------------------------

class ReconciliationRequest(BaseModel):
    ledger_path: Optional[str] = "data/raw/internal_ledger.csv"
    bank_path: Optional[str] = "data/raw/bank_settlement.csv"
    gateway_path: Optional[str] = "data/raw/payment_gateway.csv"


# --------------------------------------------------
# TEMPORARY IN-MEMORY STORE
# --------------------------------------------------
# Kept for compatibility with the existing pipeline flow.
# Persistent results are now stored in PostgreSQL.

results_store = []


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI Finance Controller",
    }


# --------------------------------------------------
# RUN RECONCILIATION
# --------------------------------------------------

@app.post("/reconcile")
def reconcile(request: ReconciliationRequest):

    try:
        results = run_reconciliation_pipeline(
            ledger_path=request.ledger_path,
            bank_path=request.bank_path,
            gateway_path=request.gateway_path,
        )

        # Update in-memory store
        results_store.clear()
        results_store.extend(results)

        # Save results to PostgreSQL
        db = SessionLocal()

        try:
            for result in results:

                final_status = (
                    result.final_status.value
                    if hasattr(result.final_status, "value")
                    else str(result.final_status)
                )

                db_result = ReconciliationResultDB(
                    id=result.unified_transaction_id,
                    unified_transaction_id=result.unified_transaction_id,
                    final_status=final_status,
                    exception_type=result.exception_type,
                    difference=result.difference,
                    resolution=result.resolution,
                    confidence_score=result.confidence_score,
                    ai_explanation=result.ai_explanation,
                    recommended_action=result.recommended_action,
                    requires_human_review=result.requires_human_review,
                )

                db.merge(db_result)

            db.commit()

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

        return {
            "message": "Reconciliation completed successfully",
            "total_transactions": len(results),
            "results": results,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# --------------------------------------------------
# GET ALL RESULTS
# --------------------------------------------------

@app.get("/results")
def get_results():

    db = SessionLocal()

    try:
        rows = (
            db.query(ReconciliationResultDB)
            .order_by(ReconciliationResultDB.created_at.desc())
            .all()
        )

        return [
            {
                "unified_transaction_id": row.unified_transaction_id,
                "final_status": row.final_status,
                "exception_type": row.exception_type,
                "difference": (
                    float(row.difference)
                    if row.difference is not None
                    else None
                ),
                "resolution": row.resolution,
                "confidence_score": (
                    float(row.confidence_score)
                    if row.confidence_score is not None
                    else None
                ),
                "ai_explanation": row.ai_explanation,
                "recommended_action": row.recommended_action,
                "requires_human_review": row.requires_human_review,
            }
            for row in rows
        ]

    finally:
        db.close()


# --------------------------------------------------
# GET SINGLE RESULT
# --------------------------------------------------

@app.get("/results/{transaction_id}")
def get_result(transaction_id: str):

    db = SessionLocal()

    try:
        row = (
            db.query(ReconciliationResultDB)
            .filter(
                ReconciliationResultDB.unified_transaction_id
                == transaction_id
            )
            .first()
        )

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found",
            )

        return {
            "unified_transaction_id": row.unified_transaction_id,
            "final_status": row.final_status,
            "exception_type": row.exception_type,
            "difference": (
                float(row.difference)
                if row.difference is not None
                else None
            ),
            "resolution": row.resolution,
            "confidence_score": (
                float(row.confidence_score)
                if row.confidence_score is not None
                else None
            ),
            "ai_explanation": row.ai_explanation,
            "recommended_action": row.recommended_action,
            "requires_human_review": row.requires_human_review,
        }

    finally:
        db.close()


# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

@app.get("/summary")
def get_summary():

    db = SessionLocal()

    try:
        rows = db.query(ReconciliationResultDB).all()

        return {
            "total": len(rows),

            "reconciled": sum(
                1
                for row in rows
                if row.final_status == "RECONCILED"
            ),

            "resolved": sum(
                1
                for row in rows
                if row.final_status == "RESOLVED"
            ),

            "needs_review": sum(
                1
                for row in rows
                if row.final_status == "NEEDS_REVIEW"
            ),

            "unresolved": sum(
                1
                for row in rows
                if row.final_status == "UNRESOLVED"
            ),
        }

    finally:
        db.close()