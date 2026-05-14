"""
Database service layer — async helper functions used by handlers.
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    GradeLevel, ExamType, Subject, PlanTemplate, Task,
    User, UserPlan, UserProgress, Subscription, Payment,
)


# ──────────────────────────────────────────────
# User helpers
# ──────────────────────────────────────────────

async def get_or_create_user(session: AsyncSession, tg_id: int,
                              username: str | None, full_name: str | None) -> User:
    res = await session.execute(select(User).where(User.id == tg_id))
    user = res.scalar_one_or_none()
    if user is None:
        user = User(id=tg_id, username=username, full_name=full_name)
        session.add(user)
        await session.flush()
    else:
        user.username  = username
        user.full_name = full_name
    return user


async def get_user(session: AsyncSession, tg_id: int) -> Optional[User]:
    res = await session.execute(select(User).where(User.id == tg_id))
    return res.scalar_one_or_none()


async def update_user_profile(session: AsyncSession, tg_id: int, **kwargs) -> None:
    res = await session.execute(select(User).where(User.id == tg_id))
    user = res.scalar_one_or_none()
    if user:
        for k, v in kwargs.items():
            setattr(user, k, v)


# ──────────────────────────────────────────────
# Catalog lookups
# ──────────────────────────────────────────────

async def get_all_grades(session: AsyncSession) -> List[GradeLevel]:
    res = await session.execute(select(GradeLevel).order_by(GradeLevel.grade))
    return list(res.scalars().all())


async def get_exams_for_grade(session: AsyncSession, grade_id: int) -> List[ExamType]:
    res = await session.execute(
        select(ExamType).where(ExamType.grade_id == grade_id)
    )
    return list(res.scalars().all())


async def get_subjects_for_exam(session: AsyncSession, exam_type_id: int) -> List[Subject]:
    res = await session.execute(
        select(Subject).where(Subject.exam_type_id == exam_type_id)
    )
    return list(res.scalars().all())


async def get_exam_type(session: AsyncSession, exam_type_id: int) -> Optional[ExamType]:
    res = await session.execute(select(ExamType).where(ExamType.id == exam_type_id))
    return res.scalar_one_or_none()


async def get_subject(session: AsyncSession, subject_id: int) -> Optional[Subject]:
    res = await session.execute(select(Subject).where(Subject.id == subject_id))
    return res.scalar_one_or_none()


async def get_grade(session: AsyncSession, grade_id: int) -> Optional[GradeLevel]:
    res = await session.execute(select(GradeLevel).where(GradeLevel.id == grade_id))
    return res.scalar_one_or_none()


# ──────────────────────────────────────────────
# Plan templates
# ──────────────────────────────────────────────

async def get_plan_variants(
    session: AsyncSession,
    subject_id: int,
    target_level: str,
    daily_minutes: int,
) -> List[PlanTemplate]:
    res = await session.execute(
        select(PlanTemplate).where(
            PlanTemplate.subject_id    == subject_id,
            PlanTemplate.target_level  == target_level,
            PlanTemplate.daily_minutes == daily_minutes,
        ).order_by(PlanTemplate.variant_index)
    )
    return list(res.scalars().all())


async def get_plan_template(session: AsyncSession, template_id: int) -> Optional[PlanTemplate]:
    res = await session.execute(
        select(PlanTemplate).where(PlanTemplate.id == template_id)
    )
    return res.scalar_one_or_none()


# ──────────────────────────────────────────────
# User plans
# ──────────────────────────────────────────────

async def create_user_plan(session: AsyncSession, user_id: int,
                            template_id: int) -> UserPlan:
    # deactivate existing plans
    res = await session.execute(
        select(UserPlan).where(UserPlan.user_id == user_id, UserPlan.is_active == True)
    )
    for old in res.scalars().all():
        old.is_active = False

    plan = UserPlan(user_id=user_id, template_id=template_id)
    session.add(plan)
    await session.flush()
    return plan


async def get_active_plan(session: AsyncSession, user_id: int) -> Optional[UserPlan]:
    res = await session.execute(
        select(UserPlan)
        .options(selectinload(UserPlan.template).selectinload(PlanTemplate.subject))
        .where(UserPlan.user_id == user_id, UserPlan.is_active == True)
    )
    return res.scalar_one_or_none()


# ──────────────────────────────────────────────
# Tasks
# ──────────────────────────────────────────────

async def get_next_task(
    session: AsyncSession,
    user_id: int,
    subject_id: int,
    target_level: str,
) -> Optional[Task]:
    """Return a task the user has not yet completed."""
    done_subq = (
        select(UserProgress.task_id).where(UserProgress.user_id == user_id)
    )
    res = await session.execute(
        select(Task)
        .where(
            Task.subject_id   == subject_id,
            Task.target_level == target_level,
            Task.id.not_in(done_subq),
        )
        .limit(1)
    )
    task = res.scalar_one_or_none()

    # If all tasks done, cycle from beginning
    if task is None:
        res = await session.execute(
            select(Task)
            .where(
                Task.subject_id   == subject_id,
                Task.target_level == target_level,
            )
            .limit(1)
        )
        task = res.scalar_one_or_none()

    return task


async def get_task(session: AsyncSession, task_id: int) -> Optional[Task]:
    res = await session.execute(select(Task).where(Task.id == task_id))
    return res.scalar_one_or_none()


async def record_progress(
    session: AsyncSession,
    user_id: int,
    task_id: int,
    is_correct: Optional[bool] = None,
    user_answer: Optional[str] = None,
) -> UserProgress:
    entry = UserProgress(
        user_id=user_id,
        task_id=task_id,
        is_correct=is_correct,
        user_answer=user_answer,
    )
    session.add(entry)
    await session.flush()
    return entry


async def count_progress(session: AsyncSession, user_id: int) -> dict:
    total_res = await session.execute(
        select(func.count()).select_from(UserProgress).where(UserProgress.user_id == user_id)
    )
    correct_res = await session.execute(
        select(func.count()).select_from(UserProgress).where(
            UserProgress.user_id == user_id,
            UserProgress.is_correct == True,
        )
    )
    total   = total_res.scalar() or 0
    correct = correct_res.scalar() or 0
    return {"total": total, "correct": correct}


# ──────────────────────────────────────────────
# Subscription & Payment stubs
# ──────────────────────────────────────────────

async def get_or_create_subscription(session: AsyncSession, user_id: int) -> Subscription:
    res = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = res.scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user_id, is_active=False, plan_type="free")
        session.add(sub)
        await session.flush()
    return sub


async def activate_subscription(
    session: AsyncSession,
    user_id: int,
    plan_type: str,
    days: int,
) -> Subscription:
    sub = await get_or_create_subscription(session, user_id)
    sub.is_active = True
    sub.plan_type = plan_type
    sub.started_at = datetime.now(timezone.utc)
    from datetime import timedelta
    sub.expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    return sub


async def create_payment(
    session: AsyncSession,
    user_id: int,
    plan_type: str,
    amount_rub: int,
) -> Payment:
    payment = Payment(
        user_id=user_id,
        plan_type=plan_type,
        amount_rub=amount_rub,
        status="pending",
    )
    session.add(payment)
    await session.flush()
    return payment


async def get_all_subscribed_users(session: AsyncSession) -> List[User]:
    """Return users who have an active plan and notifications enabled."""
    res = await session.execute(
        select(User)
        .join(UserPlan, UserPlan.user_id == User.id)
        .where(UserPlan.is_active == True, User.is_active == True)
        .distinct()
    )
    return list(res.scalars().all())
