"""Le réveil : ce qui permet à Girlypop de t'écrire d'elle-même.

APScheduler appelle nos fonctions à heure fixe. Le scheduler ne sait pas QUOI dire :
il demande à l'agent (brief, plan) ou au cœur (rappels), puis envoie via le bot.
"""

import logging
from datetime import datetime
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from girlypop.agent import Agent
from girlypop.agent.prompts import MORNING_BRIEF_INSTRUCTION, WEEKLY_PLAN_INSTRUCTION
from girlypop.config import Config
from girlypop.core import Core

log = logging.getLogger(__name__)

# Le type de `send` : une fonction async qui prend un texte (ici, bot.send_to_owner).
SendFn = Callable[[str], Awaitable[None]]


def build_scheduler(config: Config, agent: Agent, core: Core, send: SendFn) -> AsyncIOScheduler:
    tz = config.timezone

    async def morning_brief() -> None:
        log.info("⏰ Brief du matin")
        await send(await agent.ask(MORNING_BRIEF_INSTRUCTION))

    async def weekly_plan() -> None:
        log.info("⏰ Plan de la semaine")
        await send(await agent.ask(WEEKLY_PLAN_INSTRUCTION))

    async def reminders() -> None:
        # Pas d'IA ici : une simple requête au cœur, c'est rapide et gratuit.
        now = datetime.now(tz)
        for task in core.tasks.due_for_reminder(now, config.reminder_minutes_before):
            await send(f"⏰ À {task['start_time']} : **{task['title']}** ({task['duration_minutes']} min). Tu gères 💪")
            core.tasks.mark_reminded(task["id"])

    scheduler = AsyncIOScheduler(timezone=tz)
    brief = config.morning_brief_time
    weekly = config.weekly_plan_time
    scheduler.add_job(morning_brief, CronTrigger(hour=brief.hour, minute=brief.minute, timezone=tz))
    scheduler.add_job(
        weekly_plan,
        CronTrigger(day_of_week=config.weekly_plan_day, hour=weekly.hour, minute=weekly.minute, timezone=tz),
    )
    scheduler.add_job(reminders, IntervalTrigger(minutes=5, timezone=tz))
    return scheduler
