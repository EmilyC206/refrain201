from __future__ import annotations

import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

_DB_PATH = os.getenv("DB_PATH", "./db/enrichment.db")
_db_dir = os.path.dirname(_DB_PATH)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)

engine = create_engine(f"sqlite:///{_DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class LeadRecord(Base):
    """One row per HubSpot contact. Heart of the pipeline."""

    __tablename__ = "lead_records"

    hs_contact_id      = Column(String, primary_key=True)
    email              = Column(String)
    domain             = Column(String)
    job_title          = Column(String)
    seniority          = Column(String)
    job_function       = Column(String)
    company_name       = Column(String)
    industry           = Column(String)
    employee_range     = Column(String)
    hq_country         = Column(String)
    tech_stack_json    = Column(JSON)
    score_icp_fit      = Column(Integer, default=0)
    score_seniority    = Column(Integer, default=0)
    score_function     = Column(Integer, default=0)
    score_company_size = Column(Integer, default=0)
    total_score        = Column(Integer, default=0)
    score_tier         = Column(String)
    personalization_hook  = Column(Text)
    hook_variables_json   = Column(JSON)
    enrichment_status  = Column(String, default="Pending")
    enrichment_source  = Column(String)
    enrichment_error   = Column(Text)
    enriched_at        = Column(DateTime)
    hs_synced_at       = Column(DateTime)


class ScoringHistory(Base):
    """Immutable audit log of every score change. Never delete rows."""

    __tablename__ = "scoring_history"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    hs_contact_id  = Column(String)
    old_score      = Column(Integer)
    new_score      = Column(Integer)
    delta          = Column(Integer)
    old_tier       = Column(String)
    new_tier       = Column(String)
    trigger_fields = Column(JSON)
    changed_at     = Column(DateTime, default=datetime.utcnow)


class ApiUsageLog(Base):
    """One row per provider per day — read by _check_cap() before every API call."""

    __tablename__ = "api_usage_log"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    date       = Column(String)
    provider   = Column(String)
    call_count = Column(Integer, default=0)
    cap        = Column(Integer)


def init_db() -> None:
    Base.metadata.create_all(engine)
    print("DB initialized.")
