from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()


def create_db_engine(database_url: str) -> Engine:
    """Crea y configura el motor de base de datos SQLAlchemy (SQLite / PostgreSQL)."""
    connect_args = {}

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # Si es un fichero sqlite local, asegurar que su directorio padre existe
        if "///" in database_url:
            raw_path = database_url.split("///", 1)[1]
            if raw_path and not raw_path.startswith(":memory:"):
                db_file = Path(raw_path).resolve()
                db_file.parent.mkdir(parents=True, exist_ok=True)

    return create_engine(
        database_url,
        connect_args=connect_args,
        echo=False,
        future=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Crea la factoría de sesiones SQLAlchemy."""
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )


def get_db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Generador de contexto para dependencias de inyección de sesión."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
