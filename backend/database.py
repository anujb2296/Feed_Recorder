"""
database.py — SQLAlchemy models and session management for CCTV NVR.
"""
import os
from datetime import datetime
from pathlib import Path
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Float, Index, text
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "/data/cctv.db")

# Ensure parent directory exists
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Recording(Base):
    """One row per MP4 segment file on disk."""
    __tablename__ = "recordings"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    camera_id        = Column(String, nullable=False)
    camera_name      = Column(String, nullable=False)
    file_path        = Column(String, unique=True, nullable=False)
    start_time       = Column(DateTime, nullable=False)
    end_time         = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    file_size_bytes  = Column(Integer, nullable=True)
    # status values: 'recording' | 'completed' | 'gap'
    status           = Column(String, nullable=False, default="recording")

    __table_args__ = (
        Index("idx_cam_start", "camera_id", "start_time"),
        Index("idx_status", "status"),
    )


def init_db() -> None:
    """Create tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
    # Enable WAL mode for better concurrent read performance
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))


@contextmanager
def get_db():
    """Provide a transactional database session."""
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_dep():
    """FastAPI dependency that yields a DB session."""
    with get_db() as db:
        yield db
