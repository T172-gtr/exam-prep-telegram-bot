from aiogram import Router

from .start      import router as start_router
from .onboarding import router as onboarding_router
from .plan       import router as plan_router
from .schedule   import router as schedule_router
from .commands   import router as commands_router
from .subscribe  import router as subscribe_router
from .admin      import router as admin_router
from .tasks      import router as tasks_router


def get_main_router() -> Router:
    main = Router()
    # Порядок важен: tasks_router содержит общий обработчик текста
    # (автопроверка ответа) — он должен идти ПОСЛЕ всех более
    # специфичных обработчиков.
    main.include_router(start_router)
    main.include_router(onboarding_router)
    main.include_router(plan_router)
    main.include_router(schedule_router)
    main.include_router(commands_router)
    main.include_router(subscribe_router)
    main.include_router(admin_router)
    main.include_router(tasks_router)
    return main
