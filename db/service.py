"""
Database service layer — async helper functions used by handlers.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Iterable

from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    GradeLevel, ExamType, Subject, PlanTemplate, Task,
    User, UserPlan, UserProgress, UserSubject,
    Subscription, Payment,
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
# User subjects (multi-selection)
# ──────────────────────────────────────────────

async def get_user_subjects(session: AsyncSession, user_id: int) -> List[UserSubject]:
    res = await session.execute(
        select(UserSubject)
        .options(
            selectinload(UserSubject.subject)
            .selectinload(Subject.exam_type)
            .selectinload(ExamType.grade)
        )
        .where(UserSubject.user_id == user_id)
        .order_by(UserSubject.id)
    )
    return list(res.scalars().all())


async def add_user_subject(session: AsyncSession, user_id: int, subject_id: int) -> bool:
    """Добавить предмет пользователю. Возвращает True если добавлено, False если уже был."""
    res = await session.execute(
        select(UserSubject).where(
            UserSubject.user_id == user_id,
            UserSubject.subject_id == subject_id,
        )
    )
    if res.scalar_one_or_none() is not None:
        return False
    session.add(UserSubject(user_id=user_id, subject_id=subject_id))
    await session.flush()
    return True


async def remove_user_subject(session: AsyncSession, user_id: int, subject_id: int) -> None:
    await session.execute(
        delete(UserSubject).where(
            UserSubject.user_id == user_id,
            UserSubject.subject_id == subject_id,
        )
    )


async def clear_user_subjects(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(UserSubject).where(UserSubject.user_id == user_id))


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
    """Создаёт активный план для пользователя по конкретному предмету.

    Деактивирует только предыдущий план по тому же предмету,
    не трогая планы по другим предметам.
    """
    template = await get_plan_template(session, template_id)
    if template is None:
        raise ValueError(f"Template {template_id} not found")

    # деактивируем предыдущие активные планы по этому же предмету
    res = await session.execute(
        select(UserPlan)
        .options(selectinload(UserPlan.template))
        .where(UserPlan.user_id == user_id, UserPlan.is_active == True)
    )
    for old in res.scalars().all():
        if old.template.subject_id == template.subject_id:
            old.is_active = False

    plan = UserPlan(user_id=user_id, template_id=template_id)
    session.add(plan)
    await session.flush()
    return plan


async def deactivate_all_user_plans(session: AsyncSession, user_id: int) -> None:
    """Деактивирует все планы пользователя (используется при сбросе подготовки)."""
    res = await session.execute(
        select(UserPlan).where(UserPlan.user_id == user_id, UserPlan.is_active == True)
    )
    for plan in res.scalars().all():
        plan.is_active = False


async def get_active_plan(session: AsyncSession, user_id: int) -> Optional[UserPlan]:
    """Возвращает «основной» активный план (первый по id) — для обратной совместимости."""
    res = await session.execute(
        select(UserPlan)
        .options(selectinload(UserPlan.template).selectinload(PlanTemplate.subject))
        .where(UserPlan.user_id == user_id, UserPlan.is_active == True)
        .order_by(UserPlan.id)
    )
    return res.scalars().first()


async def get_active_plans(session: AsyncSession, user_id: int) -> List[UserPlan]:
    """Все активные планы пользователя (по каждому выбранному предмету)."""
    res = await session.execute(
        select(UserPlan)
        .options(selectinload(UserPlan.template).selectinload(PlanTemplate.subject))
        .where(UserPlan.user_id == user_id, UserPlan.is_active == True)
        .order_by(UserPlan.id)
    )
    return list(res.scalars().all())


# ──────────────────────────────────────────────
# Tasks
# ──────────────────────────────────────────────

async def get_next_task(
    session: AsyncSession,
    user_id: int,
    subject_id: int,
    target_level: str,
) -> Optional[Task]:
    """Возвращает задание, которое пользователь ещё не получал.

    После выполнения всех заданий по subject+level — возвращает None
    (НЕ зацикливаем — пользователь должен сам сменить план/предмет).
    """
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
        .order_by(Task.id)
        .limit(1)
    )
    return res.scalar_one_or_none()


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
    """Пользователи с активным планом и включёнными уведомлениями."""
    res = await session.execute(
        select(User)
        .join(UserPlan, UserPlan.user_id == User.id)
        .where(UserPlan.is_active == True, User.is_active == True)
        .distinct()
    )
    return list(res.scalars().all())


# ──────────────────────────────────────────────
# Admin / stats helpers
# ──────────────────────────────────────────────

async def get_subscription_stats(session: AsyncSession) -> dict:
    """Сводка по подпискам и платежам для /admin."""
    total_users = (await session.execute(
        select(func.count()).select_from(User)
    )).scalar() or 0

    active_premium = (await session.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.is_active == True,
            Subscription.plan_type != "free",
        )
    )).scalar() or 0

    by_plan_rows = (await session.execute(
        select(Subscription.plan_type, func.count())
        .where(Subscription.is_active == True, Subscription.plan_type != "free")
        .group_by(Subscription.plan_type)
    )).all()

    pay_total = (await session.execute(
        select(func.count()).select_from(Payment)
    )).scalar() or 0
    pay_success = (await session.execute(
        select(func.count()).select_from(Payment).where(Payment.status == "success")
    )).scalar() or 0
    pay_amount = (await session.execute(
        select(func.coalesce(func.sum(Payment.amount_rub), 0))
        .where(Payment.status == "success")
    )).scalar() or 0

    return {
        "total_users":     total_users,
        "active_premium":  active_premium,
        "by_plan":         dict(by_plan_rows),
        "payments_total":  pay_total,
        "payments_ok":     pay_success,
        "payments_amount": pay_amount,
    }


async def get_subject_distribution(session: AsyncSession) -> list[tuple]:
    """Сколько пользователей выбрали каждый предмет (с классом и экзаменом)."""
    rows = (await session.execute(
        select(
            GradeLevel.label,
            ExamType.name,
            Subject.name,
            func.count(UserSubject.id),
        )
        .join(Subject, UserSubject.subject_id == Subject.id)
        .join(ExamType, Subject.exam_type_id == ExamType.id)
        .join(GradeLevel, ExamType.grade_id == GradeLevel.id)
        .group_by(GradeLevel.label, ExamType.name, Subject.name)
        .order_by(func.count(UserSubject.id).desc())
        .limit(30)
    )).all()
    return list(rows)
