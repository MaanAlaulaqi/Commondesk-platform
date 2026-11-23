"""Authoritative case store and additive schema for PostgreSQL and local SQLite."""

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    select,
    text,
)
from sqlalchemy.dialects import postgresql, sqlite

DATA = Path(os.getenv("DATA_DIR", "data"))
url = os.getenv("DATABASE_URL")
if not url:
    DATA.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{DATA.resolve()}/commondesk.sqlite"
for prefix in ("postgres://", "postgresql://"):
    if url.startswith(prefix):
        url = "postgresql+psycopg://" + url[len(prefix) :]
engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def sqlite_setup(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("PRAGMA journal_mode=WAL")


meta = MetaData()
media = Table(
    "cd_media",
    meta,
    Column("id", String, primary_key=True),
    Column("mime", String, nullable=False),
    Column("data", LargeBinary, nullable=False),
    Column("alt", Text, nullable=False),
    Column("source", String, nullable=False),
)
cases = Table(
    "cd_cases",
    meta,
    Column("id", String, primary_key=True),
    Column("incident_id", String, nullable=False),
    Column("source", String, nullable=False, index=True),
    Column("text", Text, nullable=False),
    Column("language", String, nullable=False),
    Column("intent", String, nullable=False),
    Column("category", String, nullable=False),
    Column("status", String, nullable=False),
    Column("final_urgency", String),
    Column("suggested_urgency", String, nullable=False),
    Column("district", String),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("accuracy", Float),
    Column("location_source", String),
    Column("created_at", String, nullable=False),
    Column("week_start", String, nullable=False),
    Column("day", String, nullable=False),
    Column("photo", ForeignKey("cd_media.id")),
    Column("provenance", String, nullable=False),
    Column("evidence_origin", JSON, nullable=False),
    Column("proposal", JSON, nullable=False),
    Column("service", String),
    Column("index_status", String, nullable=False),
    Column("requested_key", String, unique=True),
    Column("request_hash", String),
    Column("revision", Integer, nullable=False),
    CheckConstraint(
        "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)"
    ),
)
views = Table(
    "cd_wordings",
    meta,
    Column("case_id", ForeignKey("cd_cases.id"), primary_key=True),
    Column("language", String, primary_key=True),
    Column("text", Text, nullable=False),
    Column("view_id", String, nullable=False, unique=True),
)
report_translations = Table(
    "cd_report_translations",
    meta,
    Column("cache_key", String(64), primary_key=True),
    Column("case_id", String, nullable=False),
    Column("source", String, nullable=False),
    Column("source_digest", String(64), nullable=False),
    Column("source_language", String, nullable=False),
    Column("target_language", String, nullable=False),
    Column("model_revision", String, nullable=False),
    Column("text", Text),
    Column("lease", String),
    Column("expires_at", Float),
)
events = Table(
    "cd_events",
    meta,
    Column("case_id", ForeignKey("cd_cases.id"), primary_key=True),
    Column("event_id", String, primary_key=True),
    Column("at", String, nullable=False),
    Column("type", String, nullable=False),
    Column("status", String),
    Column("details", JSON, nullable=False),
)
queue = Table(
    "cd_index_queue",
    meta,
    Column("case_id", ForeignKey("cd_cases.id"), primary_key=True),
    Column("revision", Integer, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("available", Float, nullable=False),
    Column("lease", String),
    Column("last_error", String),
)
migrations = Table("cd_migrations", meta, Column("version", Integer, primary_key=True))
Index("cd_cases_recent", cases.c.source, cases.c.created_at)
Index("cd_queue_due", queue.c.available)
Index("cd_wording_language", views.c.language)


def now():
    return datetime.now(timezone.utc).isoformat()


def insert_for(table):
    return (
        postgresql.insert if engine.dialect.name == "postgresql" else sqlite.insert
    )(table)


def migrate():
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(517491028)"))
        meta.create_all(conn)
        if conn.scalar(select(migrations.c.version).where(migrations.c.version == 1)):
            return
        if engine.dialect.name == "postgresql":
            conn.exec_driver_sql("""CREATE OR REPLACE FUNCTION cd_history_guard() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Case events are append-only'; END; $$""")
            conn.exec_driver_sql("""CREATE TRIGGER cd_no_event_mutation BEFORE UPDATE OR DELETE OR TRUNCATE ON cd_events
                                 FOR EACH STATEMENT EXECUTE FUNCTION cd_history_guard()""")
        else:
            for action in ("UPDATE", "DELETE"):
                conn.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS cd_no_event_{action} BEFORE {action} ON cd_events
                                         BEGIN SELECT RAISE(ABORT, 'Case events are append-only'); END""")
        conn.execute(migrations.insert().values(version=1))
