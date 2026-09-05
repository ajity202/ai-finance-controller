import os

from dotenv import load_dotenv
from sqlalchemy import Boolean, Column, DateTime, Numeric, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.sql import func


# -------------------------------------------------
# Load environment variables
# -------------------------------------------------

load_dotenv(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".env",
    )
)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not configured in .env"
    )


# -------------------------------------------------
# Database connection
# -------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


# -------------------------------------------------
# Reconciliation Results Table
# -------------------------------------------------

class ReconciliationResultDB(Base):

    __tablename__ = "reconciliation_results"

    id = Column(
        String,
        primary_key=True,
    )

    unified_transaction_id = Column(
        String,
        nullable=False,
        index=True,
    )

    final_status = Column(
        String,
        nullable=False,
        index=True,
    )

    exception_type = Column(
        String,
        nullable=True,
    )

    difference = Column(
        Numeric(18, 2),
        nullable=True,
    )

    resolution = Column(
        Text,
        nullable=True,
    )

    confidence_score = Column(
        Numeric(5, 4),
        nullable=True,
    )

    ai_explanation = Column(
        Text,
        nullable=True,
    )

    recommended_action = Column(
        Text,
        nullable=True,
    )

    requires_human_review = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )


# -------------------------------------------------
# Create Tables
# -------------------------------------------------

Base.metadata.create_all(
    bind=engine
)

print("Database initialized successfully.")