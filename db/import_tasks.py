"""
Импорт заданий из внешнего источника (JSON/CSV).

Архитектура: точка расширения для будущего парсера. Сейчас поддерживаются
JSON-файлы в формате:

[
  {
    "exam_code": "oge",
    "subject_code": "math",
    "target_level": "low",
    "title": "Заголовок",
    "body": "Условие",
    "correct_answer": "42",
    "acceptable_answers": "42 шт|42 штуки",
    "hint": "Подсказка",
    "explanation": "Подробное объяснение",
    "image_url": "https://example.com/task.png",
    "source_url": "https://example.com/source",
    "tags": "арифметика,натуральные"
  }
]

Реальный веб-скрапер сюда подключается через одну функцию
`import_tasks(session, items)`.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Subject, ExamType, Task

logger = logging.getLogger(__name__)

DEFAULT_IMPORT_PATH = Path("data/tasks_import.json")


async def _find_subject(session: AsyncSession, exam_code: str,
                         subject_code: str) -> Subject | None:
    res = await session.execute(
        select(Subject)
        .join(ExamType, Subject.exam_type_id == ExamType.id)
        .where(ExamType.code == exam_code, Subject.code == subject_code)
        .limit(1)
    )
    return res.scalars().first()


async def import_tasks(session: AsyncSession,
                        items: Iterable[dict]) -> tuple[int, int]:
    """Импортирует список заданий. Возвращает (added, skipped)."""
    added = 0
    skipped = 0
    for item in items:
        try:
            exam_code    = item["exam_code"]
            subject_code = item["subject_code"]
            title        = item["title"]
            body         = item["body"]
            level        = item.get("target_level", "medium")
        except KeyError as exc:
            logger.warning("Skip task — missing required field %s: %s", exc, item)
            skipped += 1
            continue

        subj = await _find_subject(session, exam_code, subject_code)
        if subj is None:
            logger.warning("Skip task — unknown subject %s/%s", exam_code, subject_code)
            skipped += 1
            continue

        # дубликаты по (subject_id, title) пропускаем
        dup = await session.execute(
            select(Task).where(
                Task.subject_id == subj.id,
                Task.title == title,
            )
        )
        if dup.scalar_one_or_none() is not None:
            skipped += 1
            continue

        correct = item.get("correct_answer") or item.get("answer")
        session.add(Task(
            subject_id         = subj.id,
            target_level       = level,
            title              = title,
            body               = body,
            answer             = correct,
            correct_answer     = correct,
            acceptable_answers = item.get("acceptable_answers"),
            hint               = item.get("hint"),
            explanation        = item.get("explanation"),
            image_url          = item.get("image_url"),
            image_file_id      = item.get("image_file_id"),
            source_url         = item.get("source_url"),
            tags               = item.get("tags") or f"{exam_code},{subject_code},{level}",
        ))
        added += 1
    return added, skipped


async def import_tasks_from_default_file(session: AsyncSession) -> tuple[int, int]:
    path = Path(os.getenv("TASKS_IMPORT_PATH", DEFAULT_IMPORT_PATH))
    if not path.exists():
        raise FileNotFoundError(str(path))
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("JSON-файл должен содержать список заданий.")
    return await import_tasks(session, data)
