"""
SQLAlchemy async ORM models.
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text,
    func, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ────────────────────────────────────────────────────────────
# Reference / catalog tables
# ────────────────────────────────────────────────────────────

class GradeLevel(Base):
    """Классы: 8, 9, 10, 11."""
    __tablename__ = "grade_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grade: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(32), nullable=False)   # "8 класс"

    exams: Mapped[List["ExamType"]] = relationship(back_populates="grade")


class ExamType(Base):
    """Типы экзаменов (ОГЭ, ЕГЭ, МЦКО, диагностика)."""
    __tablename__ = "exam_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grade_levels.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)    # "oge", "ege", "mcko", "diag"
    name: Mapped[str] = mapped_column(String(128), nullable=False)   # "ОГЭ"
    description: Mapped[Optional[str]] = mapped_column(Text)

    grade: Mapped["GradeLevel"] = relationship(back_populates="exams")
    subjects: Mapped[List["Subject"]] = relationship(back_populates="exam_type",
                                                      cascade="all, delete-orphan")


class Subject(Base):
    """Предметы по экзамену."""
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_type_id: Mapped[int] = mapped_column(ForeignKey("exam_types.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)   # "math", "rus", "phys" …
    name: Mapped[str] = mapped_column(String(128), nullable=False)  # "Математика"

    exam_type: Mapped["ExamType"] = relationship(back_populates="subjects")
    plan_templates: Mapped[List["PlanTemplate"]] = relationship(back_populates="subject",
                                                                 cascade="all, delete-orphan")
    tasks: Mapped[List["Task"]] = relationship(back_populates="subject",
                                               cascade="all, delete-orphan")


# ────────────────────────────────────────────────────────────
# Plan templates
# ────────────────────────────────────────────────────────────

class PlanTemplate(Base):
    """Шаблон плана подготовки (один из нескольких вариантов)."""
    __tablename__ = "plan_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    target_level: Mapped[str] = mapped_column(String(32), nullable=False)
    # low / medium / high / max
    daily_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # 15 / 30 / 45 / 60 / 90
    variant_index: Mapped[int] = mapped_column(Integer, default=1)
    # 1, 2, 3 — несколько вариантов для одного набора параметров
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    total_days: Mapped[int] = mapped_column(Integer, default=60)

    subject: Mapped["Subject"] = relationship(back_populates="plan_templates")
    user_plans: Mapped[List["UserPlan"]] = relationship(back_populates="template")


# ────────────────────────────────────────────────────────────
# Tasks (bank of exercises)
# ────────────────────────────────────────────────────────────

class Task(Base):
    """Одно задание из банка."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    target_level: Mapped[str] = mapped_column(String(32), nullable=False)
    # low / medium / high / max
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text)
    hint: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[Optional[str]] = mapped_column(String(512))  # comma-separated

    subject: Mapped["Subject"] = relationship(back_populates="tasks")
    progress_items: Mapped[List["UserProgress"]] = relationship(back_populates="task")


# ────────────────────────────────────────────────────────────
# Users
# ────────────────────────────────────────────────────────────

class User(Base):
    """Telegram-пользователь."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)   # tg user_id
    username: Mapped[Optional[str]] = mapped_column(String(128))
    full_name: Mapped[Optional[str]] = mapped_column(String(256))
    grade_id: Mapped[Optional[int]] = mapped_column(ForeignKey("grade_levels.id"))
    exam_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("exam_types.id"))
    subject_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subjects.id"))
    target_level: Mapped[Optional[str]] = mapped_column(String(32))
    daily_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    notify_time: Mapped[str] = mapped_column(String(8), default="08:00")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)

    grade: Mapped[Optional["GradeLevel"]] = relationship(foreign_keys=[grade_id])
    exam_type: Mapped[Optional["ExamType"]] = relationship(foreign_keys=[exam_type_id])
    subject: Mapped[Optional["Subject"]] = relationship(foreign_keys=[subject_id])
    plans: Mapped[List["UserPlan"]] = relationship(back_populates="user",
                                                    cascade="all, delete-orphan")
    progress: Mapped[List["UserProgress"]] = relationship(back_populates="user",
                                                          cascade="all, delete-orphan")
    subscription: Mapped[Optional["Subscription"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    payments: Mapped[List["Payment"]] = relationship(back_populates="user",
                                                      cascade="all, delete-orphan")


# ────────────────────────────────────────────────────────────
# User plans
# ────────────────────────────────────────────────────────────

class UserPlan(Base):
    """Выбранный пользователем план."""
    __tablename__ = "user_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    template_id: Mapped[int] = mapped_column(ForeignKey("plan_templates.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    current_day: Mapped[int] = mapped_column(Integer, default=1)
    tasks_sent_today: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="plans")
    template: Mapped["PlanTemplate"] = relationship(back_populates="user_plans")


# ────────────────────────────────────────────────────────────
# Progress
# ────────────────────────────────────────────────────────────

class UserProgress(Base):
    """Запись о выполненном задании."""
    __tablename__ = "user_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean)
    user_answer: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="progress")
    task: Mapped["Task"] = relationship(back_populates="progress_items")


# ────────────────────────────────────────────────────────────
# Subscription & Payment (stub)
# ────────────────────────────────────────────────────────────

class Subscription(Base):
    """Premium-подписка пользователя."""
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_type: Mapped[str] = mapped_column(String(32), default="free")
    # "free" | "premium_month" | "premium_year"
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="subscription")


class Payment(Base):
    """Запись о платёжной транзакции (заглушка)."""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    # "pending" | "success" | "failed" | "refunded"
    plan_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_tx_id: Mapped[Optional[str]] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="payments")
