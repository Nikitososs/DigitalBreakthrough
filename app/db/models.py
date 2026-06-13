"""ORM-модели архива обработанных задач."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class StoredJob(Base):
    __tablename__ = "stored_jobs"

    task_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    filename: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(Text, default="")
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    problem_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    municipality_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_json: Mapped[str] = mapped_column(Text, default="{}")
    stored_at: Mapped[str] = mapped_column(Text, default="")
    incident_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_task_id: Mapped[str | None] = mapped_column(String(16), nullable=True)


class StoredIncident(Base):
    __tablename__ = "stored_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("stored_jobs.task_id", ondelete="CASCADE"),
        index=True,
    )
    row_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_name: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str] = mapped_column(Text, default="")
    municipality: Mapped[str] = mapped_column(Text, default="")
    settlement: Mapped[str | None] = mapped_column(Text, nullable=True)
    street: Mapped[str | None] = mapped_column(Text, nullable=True)
    house: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[int] = mapped_column(Integer, default=0)
    is_problem: Mapped[bool] = mapped_column(Boolean, default=False)
    agency: Mapped[str] = mapped_column(Text, default="")
    agency_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    municipality_admin: Mapped[str | None] = mapped_column(Text, nullable=True)
    municipality_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    municipality_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_line: Mapped[str] = mapped_column(Text, default="")
    has_address: Mapped[bool] = mapped_column(Boolean, default=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    incident_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    closed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    manually_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=False)
    resolved_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("task_id", "row_id", name="uq_incident_task_row"),
        Index("ix_incidents_task_severity", "task_id", "severity"),
        Index("ix_incidents_task_municipality", "task_id", "municipality"),
        Index("ix_incidents_task_resolved", "task_id", "manually_resolved"),
        Index("ix_incidents_task_is_resolved", "task_id", "is_resolved", "severity"),
    )


class IncidentRegistry(Base):
    """Глобальный реестр ID обращений (колонка B) для дедупа и «решено» между загрузками."""

    __tablename__ = "incident_registry"

    external_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    manually_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_task_id: Mapped[str] = mapped_column(String(16), default="")
    last_task_id: Mapped[str] = mapped_column(String(16), default="")
    updated_at: Mapped[str] = mapped_column(Text, default="")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32), default="operator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(Text, default="")


class GeocodeCacheEntry(Base):
    """Глобальный кэш Nominatim: нормализованный адрес → координаты."""

    __tablename__ = "geocode_cache"

    address_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    address_line: Mapped[str] = mapped_column(Text, default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[str] = mapped_column(Text, default="")
