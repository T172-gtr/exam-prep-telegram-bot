"""
Seed script — заполняет справочные таблицы, шаблоны планов и примеры заданий.
Безопасен для повторного запуска (upsert-логика).
"""
import asyncio
from sqlalchemy import select
from .database import async_session, init_db
from .models import (
    GradeLevel, ExamType, Subject, PlanTemplate, Task,
)


# ──────────────────────────────────────────────
# Справочники
# ──────────────────────────────────────────────

GRADES = [
    (8, "8 класс"),
    (9, "9 класс"),
    (10, "10 класс"),
    (11, "11 класс"),
]

# grade -> [(code, name, description)]
EXAMS = {
    8:  [
        ("mcko",  "МЦКО",        "Московский центр качества образования"),
        ("diag",  "Диагностика", "Диагностическая контрольная работа"),
    ],
    9:  [("oge",  "ОГЭ",  "Основной государственный экзамен")],
    10: [
        ("mcko",  "МЦКО",        "МЦКО для 10 класса"),
        ("diag",  "Диагностика", "Диагностическая работа"),
    ],
    11: [("ege",  "ЕГЭ",  "Единый государственный экзамен")],
}

# exam_code -> [(subject_code, subject_name)]
SUBJECTS = {
    "mcko": [
        ("math",    "Математика"),
        ("rus",     "Русский язык"),
        ("eng",     "Английский язык"),
    ],
    "diag": [
        ("math",    "Математика"),
        ("rus",     "Русский язык"),
        ("bio",     "Биология"),
        ("hist",    "История"),
    ],
    "oge": [
        ("math",    "Математика"),
        ("rus",     "Русский язык"),
        ("phys",    "Физика"),
        ("chem",    "Химия"),
        ("bio",     "Биология"),
        ("geo",     "География"),
        ("hist",    "История"),
        ("soc",     "Обществознание"),
        ("inf",     "Информатика"),
        ("eng",     "Английский язык"),
        ("lit",     "Литература"),
    ],
    "ege": [
        ("math_b",  "Математика (база)"),
        ("math_p",  "Математика (профиль)"),
        ("rus",     "Русский язык"),
        ("phys",    "Физика"),
        ("chem",    "Химия"),
        ("bio",     "Биология"),
        ("geo",     "География"),
        ("hist",    "История"),
        ("soc",     "Обществознание"),
        ("inf",     "Информатика"),
        ("eng",     "Английский язык"),
        ("lit",     "Литература"),
    ],
}

# (level, days)
LEVEL_DAYS = {
    "low":    30,
    "medium": 60,
    "high":   90,
    "max":   120,
}

# ──────────────────────────────────────────────
# Описания уровней
# ──────────────────────────────────────────────

LEVEL_META = {
    "low":    ("Низкий",       "Базовые задания: задачи части 1, минимальный балл"),
    "medium": ("Средний",      "Умеренный прогресс: части 1–2, уверенная сдача"),
    "high":   ("Высокий",      "Систематическая подготовка: сложные задания, хороший балл"),
    "max":    ("Максимальный", "Глубокое погружение: все части, максимальный балл"),
}

# Шаблоны названий планов (variant 1, 2, 3)
PLAN_VARIANTS = [
    ("Классический план",     "Равномерное распределение тем по дням с повторением"),
    ("Интенсивный план",      "Приоритет слабых тем, быстрое продвижение"),
    ("Тематический блоками",  "Работа по тематическим блокам с мини-тестами"),
]

# ──────────────────────────────────────────────
# Пример заданий (по 3 на каждый ключевой предмет/уровень)
# ──────────────────────────────────────────────

SAMPLE_TASKS = [
    # ОГЭ Математика
    dict(subject_lookup=("oge","math"), level="low",
         title="Арифметика: дроби",
         body="Вычислите: 3/4 + 1/6",
         correct_answer="11/12",
         acceptable_answers="11÷12",
         hint="Приведите дроби к общему знаменателю 12",
         explanation="3/4 = 9/12, 1/6 = 2/12 → 9/12 + 2/12 = 11/12"),
    dict(subject_lookup=("oge","math"), level="low",
         title="Степени",
         body="Вычислите: 2³ × 2²",
         correct_answer="32",
         hint="Сложите показатели степени: 2^(3+2) = 2^5",
         explanation="2³ · 2² = 2^(3+2) = 2^5 = 32"),
    dict(subject_lookup=("oge","math"), level="medium",
         title="Уравнение",
         body="Решите уравнение: 2x + 5 = 13",
         correct_answer="4",
         acceptable_answers="x=4|x = 4",
         hint="Перенесите 5 в правую часть",
         explanation="2x = 13 − 5 = 8 → x = 4"),
    dict(subject_lookup=("oge","math"), level="medium",
         title="Геометрия: площадь",
         body="Найдите площадь прямоугольника со сторонами 7 и 4 см. Ответ в см².",
         correct_answer="28",
         acceptable_answers="28 см²|28см2",
         hint="S = a × b",
         explanation="S = 7·4 = 28 см²"),
    dict(subject_lookup=("oge","math"), level="medium",
         title="Геометрия по чертежу",
         body="На рисунке изображён прямоугольный треугольник. Чему равна гипотенуза, если катеты равны 3 и 4?",
         correct_answer="5",
         hint="Теорема Пифагора",
         explanation="c = √(3² + 4²) = √25 = 5",
         image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d2/Pythagorean.svg/240px-Pythagorean.svg.png",
         source_url="https://oge.fipi.ru/"),
    dict(subject_lookup=("oge","math"), level="high",
         title="Квадратное уравнение",
         body="Решите уравнение: x² − 5x + 6 = 0. Перечислите корни через запятую.",
         correct_answer="2,3",
         acceptable_answers="3,2|x=2,x=3",
         hint="Разложите на множители или используйте дискриминант",
         explanation="D = 25 − 24 = 1, x = (5 ± 1)/2 → 2 и 3"),
    dict(subject_lookup=("oge","math"), level="max",
         title="Задача на движение",
         body="Два велосипедиста выехали навстречу друг другу из двух городов, расстояние между которыми 120 км. Скорость первого — 20 км/ч, второго — 25 км/ч. Через сколько часов они встретятся? Ответ в часах в виде десятичной дроби.",
         correct_answer="2.67",
         acceptable_answers="2,67|8/3",
         hint="Сумма скоростей = 45 км/ч; t = 120/45",
         explanation="t = 120/45 = 8/3 ≈ 2.67 ч"),

    # ЕГЭ Математика (профиль)
    dict(subject_lookup=("ege","math_p"), level="low",
         title="Производная: степень",
         body="Найдите производную функции f(x) = x³. Ответ — выражение через x.",
         correct_answer="3x^2",
         acceptable_answers="3x²|3*x^2|3·x²",
         hint="Формула (xⁿ)' = n·xⁿ⁻¹",
         explanation="(x³)' = 3·x^(3−1) = 3x²"),
    dict(subject_lookup=("ege","math_p"), level="medium",
         title="Логарифм",
         body="Вычислите: log₂(32)",
         correct_answer="5",
         hint="2^5 = 32",
         explanation="log₂(2^5) = 5"),
    dict(subject_lookup=("ege","math_p"), level="high",
         title="Производная сложной функции",
         body="Найдите производную f(x) = sin(2x).",
         correct_answer="2cos(2x)",
         acceptable_answers="2·cos(2x)|2 cos 2x",
         hint="Правило производной сложной функции: f'(x) = cos(2x)·(2x)'",
         explanation="(sin u)' = cos u · u', где u = 2x → 2·cos(2x)"),
    dict(subject_lookup=("ege","math_p"), level="max",
         title="Интеграл",
         body="Вычислите интеграл ∫(3x² + 2x) dx (без константы).",
         correct_answer="x^3+x^2",
         acceptable_answers="x³+x²|x^3 + x^2",
         hint="Интегрируйте почленно",
         explanation="∫3x² dx = x³, ∫2x dx = x² → x³ + x² (+ C)"),
    dict(subject_lookup=("ege","math_p"), level="medium",
         title="График функции",
         body="На рисунке изображён график линейной функции. Чему равен её угловой коэффициент, если функция проходит через точки (0, 1) и (2, 5)?",
         correct_answer="2",
         hint="k = Δy / Δx",
         explanation="k = (5 − 1)/(2 − 0) = 4/2 = 2",
         image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/Linear_function_graph.svg/240px-Linear_function_graph.svg.png",
         source_url="https://fipi.ru/ege"),

    # ОГЭ Русский язык
    dict(subject_lookup=("oge","rus"), level="low",
         title="Правописание: корни с чередованием",
         body="Выберите правильный вариант: р..сток / р..сток (росток/расток). Вставьте букву.",
         answer="росток",
         hint="Исключение: росток, Ростов, Ростислав"),
    dict(subject_lookup=("oge","rus"), level="medium",
         title="Синтаксический разбор",
         body="Укажите грамматическую основу предложения: «Ветер гонит по небу серые облака.»",
         answer="ветер гонит",
         hint="Найдите подлежащее (кто? что?) и сказуемое (что делает?)"),
    dict(subject_lookup=("oge","rus"), level="high",
         title="Сочинение: аргумент",
         body="Приведите один аргумент из литературы в поддержку тезиса: «Дружба помогает преодолевать трудности».",
         answer="(Открытый вопрос — примеры: «Три мушкетёра», «Тимур и его команда»)",
         hint="Назовите произведение, автора и конкретный эпизод"),

    # ЕГЭ Русский язык
    dict(subject_lookup=("ege","rus"), level="low",
         title="Орфография: Н и НН",
         body="Вставьте Н или НН: стекля..ый.",
         answer="стеклянный",
         hint="Исключения из правила: стеклянный, оловянный, деревянный"),
    dict(subject_lookup=("ege","rus"), level="medium",
         title="Пунктуация: запятая при однородных членах",
         body="Расставьте знаки препинания: «Книги учат нас думать размышлять анализировать.»",
         answer="Книги учат нас думать, размышлять, анализировать.",
         hint="Однородные члены разделяются запятой"),

    # ЕГЭ Обществознание
    dict(subject_lookup=("ege","soc"), level="low",
         title="Государство и право",
         body="Что такое правовое государство? Дайте краткое определение.",
         answer="Государство, в котором верховенство закона, разделение властей и соблюдение прав человека",
         hint="Три ключевых признака: верховенство права, разделение властей, гарантии прав"),
    dict(subject_lookup=("ege","soc"), level="medium",
         title="Экономика: ВВП",
         body="Что измеряет ВВП?",
         answer="Суммарную стоимость всех конечных товаров и услуг, произведённых в стране за год",
         hint="ВВП = Валовой Внутренний Продукт"),

    # ЕГЭ История
    dict(subject_lookup=("ege","hist"), level="low",
         title="Дата: Куликовская битва",
         body="В каком году произошла Куликовская битва?",
         answer="1380",
         hint="Дмитрий Донской, Мамай"),
    dict(subject_lookup=("ege","hist"), level="medium",
         title="Термин: опричнина",
         body="Объясните, что такое опричнина и кем она была введена.",
         answer="Государственная политика террора и система управления, введённая Иваном Грозным в 1565–1572 гг.",
         hint="Иван IV, 1565 год"),

    # МЦКО Математика
    dict(subject_lookup=("mcko","math"), level="low",
         title="Проценты",
         body="Найдите 15% от числа 200.",
         answer="30",
         hint="200 × 0.15"),
    dict(subject_lookup=("mcko","math"), level="medium",
         title="Пропорция",
         body="Решите пропорцию: 3/x = 9/15",
         answer="x = 5",
         hint="Перекрёстное произведение: 3×15 = 9×x"),
]


async def seed() -> None:
    await init_db()

    async with async_session() as session:
        async with session.begin():

            # ── grades ──────────────────────────────
            grade_map: dict[int, GradeLevel] = {}
            for g_num, g_label in GRADES:
                res = await session.execute(select(GradeLevel).where(GradeLevel.grade == g_num))
                obj = res.scalar_one_or_none()
                if obj is None:
                    obj = GradeLevel(grade=g_num, label=g_label)
                    session.add(obj)
                    await session.flush()
                grade_map[g_num] = obj

            # ── exam types ──────────────────────────
            exam_map: dict[tuple, ExamType] = {}  # (grade_num, code) -> ExamType
            for g_num, exams in EXAMS.items():
                for code, name, desc in exams:
                    res = await session.execute(
                        select(ExamType).where(
                            ExamType.grade_id == grade_map[g_num].id,
                            ExamType.code == code,
                        )
                    )
                    obj = res.scalar_one_or_none()
                    if obj is None:
                        obj = ExamType(
                            grade_id=grade_map[g_num].id,
                            code=code,
                            name=name,
                            description=desc,
                        )
                        session.add(obj)
                        await session.flush()
                    exam_map[(g_num, code)] = obj

            # ── subjects ────────────────────────────
            subject_map: dict[tuple, Subject] = {}  # (exam_code, subj_code) -> Subject
            for exam_code, subj_list in SUBJECTS.items():
                for (grade_num, et_code), et_obj in exam_map.items():
                    if et_code == exam_code:
                        for s_code, s_name in subj_list:
                            res = await session.execute(
                                select(Subject).where(
                                    Subject.exam_type_id == et_obj.id,
                                    Subject.code == s_code,
                                )
                            )
                            obj = res.scalar_one_or_none()
                            if obj is None:
                                obj = Subject(
                                    exam_type_id=et_obj.id,
                                    code=s_code,
                                    name=s_name,
                                )
                                session.add(obj)
                                await session.flush()
                            subject_map[(exam_code, s_code)] = obj

            # ── plan templates ───────────────────────
            for (exam_code, s_code), subj_obj in subject_map.items():
                for level, days in LEVEL_DAYS.items():
                    for minutes in [15, 30, 45, 60, 90]:
                        for vidx, (vtitle, vdesc) in enumerate(PLAN_VARIANTS, start=1):
                            res = await session.execute(
                                select(PlanTemplate).where(
                                    PlanTemplate.subject_id == subj_obj.id,
                                    PlanTemplate.target_level == level,
                                    PlanTemplate.daily_minutes == minutes,
                                    PlanTemplate.variant_index == vidx,
                                )
                            )
                            if res.scalar_one_or_none() is None:
                                level_label, _ = LEVEL_META[level]
                                session.add(PlanTemplate(
                                    subject_id=subj_obj.id,
                                    target_level=level,
                                    daily_minutes=minutes,
                                    variant_index=vidx,
                                    title=f"{vtitle} · {subj_obj.name} · {level_label} · {minutes} мин/день",
                                    description=(
                                        f"{vdesc}. "
                                        f"Цель: {level_label.lower()} уровень. "
                                        f"Ежедневно {minutes} минут. "
                                        f"Длительность: {days} дней."
                                    ),
                                    total_days=days,
                                ))
                await session.flush()

            # ── sample tasks ────────────────────────
            for t in SAMPLE_TASKS:
                exam_code, s_code = t["subject_lookup"]
                subj_obj = subject_map.get((exam_code, s_code))
                if subj_obj is None:
                    continue
                res = await session.execute(
                    select(Task).where(
                        Task.subject_id == subj_obj.id,
                        Task.title == t["title"],
                    )
                )
                if res.scalar_one_or_none() is None:
                    primary = t.get("correct_answer") or t.get("answer")
                    session.add(Task(
                        subject_id=subj_obj.id,
                        target_level=t["level"],
                        title=t["title"],
                        body=t["body"],
                        answer=primary,
                        correct_answer=primary,
                        acceptable_answers=t.get("acceptable_answers"),
                        hint=t.get("hint"),
                        explanation=t.get("explanation"),
                        image_url=t.get("image_url"),
                        image_file_id=t.get("image_file_id"),
                        source_url=t.get("source_url"),
                        tags=f"{exam_code},{s_code},{t['level']}",
                    ))

        print("✅ Seed завершён.")


if __name__ == "__main__":
    asyncio.run(seed())
