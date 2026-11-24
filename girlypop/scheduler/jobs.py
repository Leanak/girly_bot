"""Le réveil : ce qui permet à Girlypop de t'écrire d'elle-même.

APScheduler appelle nos fonctions à heure fixe. Le scheduler ne sait pas QUOI dire :
il demande à l'agent (brief, plan, motivation, bilan) ou au cœur (rappels), puis
envoie via le bot.

Les réveils de la journée (rôle Motivatrice) :
  07:30            brief du matin (IA)
  toutes les 5 min rappels des tâches ET des événements du calendrier (sans IA)
  toutes les 5 min « c'est l'heure de passer à la suite » à la fin d'une tâche (sans IA)
  10:30 14:30 17:00 petit message de motivation (IA)
  21:00            bilan du soir (IA)
  dimanche 19:00   plan de la semaine (IA)
Toutes ces heures se règlent dans .env.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from girlypop.agent import Agent
from girlypop.agent.prompts import (
    EVENING_CHECKIN_INSTRUCTION,
    MORNING_BRIEF_INSTRUCTION,
    MOTIVATION_INSTRUCTION,
    WEEKLY_PLAN_INSTRUCTION,
)
from girlypop.config import Config
from girlypop.core import Core
from girlypop.integrations import Calendars

log = logging.getLogger(__name__)

# Le type de `send` : une fonction async qui prend un texte (ici, bot.send_to_owner).
SendFn = Callable[[str], Awaitable[None]]

CHECK_EVERY_MINUTES = 5  # fréquence des vérifications « sans IA » (rappels, transitions)


def transition_message(ended: dict, next_task: Optional[dict]) -> str:
    """Le message de fin de tâche. Fonction pure, facile à tester et à personnaliser."""
    text = f"⏱️ C'est l'heure de boucler **{ended['title']}** ! C'est fait ? Réponds « fait » et je coche ✅"
    if next_task:
        text += f"\n👉 Ensuite : **{next_task['title']}** à {next_task['start_time']}. Petite pause d'abord ? 🫖"
    else:
        text += "\nPlus rien de prévu après : tu peux souffler 🌸"
    return text


class Reminders:
    """Les vérifications régulières, sans IA (rapides et gratuites).

    Les ensembles `_seen_*` retiennent ce qui a déjà été envoyé pour ne jamais
    t'écrire deux fois la même chose (ils s'effacent au redémarrage, ce n'est pas grave).
    """

    def __init__(self, config: Config, agent: Agent, core: Core, send: SendFn,
                 calendar: Optional[Calendars] = None):
        self._config = config
        self._agent = agent
        self._core = core
        self._send = send
        self._calendar = calendar
        self._seen_events: set[tuple[str, str]] = set()
        self._seen_endings: set[int] = set()

    async def _say(self, text: str) -> None:
        await self._send(text)
        self._agent.note(text)  # pour qu'elle comprenne ta réponse (« fait ! »)

    async def check(self) -> None:
        now = datetime.now(self._config.timezone)
        await self.task_reminders(now)
        if self._config.transition_nudges:
            await self.transitions(now)
        if self._calendar:
            await self.calendar_reminders(now)

    async def task_reminders(self, now: datetime) -> None:
        for task in self._core.tasks.due_for_reminder(now, self._config.reminder_minutes_before):
            await self._say(
                f"⏰ À {task['start_time']} : **{task['title']}** ({task['duration_minutes']} min, "
                f"tâche n°{task['id']}). Tu gères 💪"
            )
            self._core.tasks.mark_reminded(task["id"])

    async def transitions(self, now: datetime) -> None:
        window_start = now - timedelta(minutes=CHECK_EVERY_MINUTES)
        for task in self._core.tasks.ending_between(window_start, now):
            if task["id"] in self._seen_endings:
                continue
            self._seen_endings.add(task["id"])
            text = transition_message(task, self._core.tasks.next_task(now))
            await self._say(text + f" _(tâche n°{task['id']})_")

    async def calendar_reminders(self, now: datetime) -> None:
        until = now + timedelta(minutes=self._config.reminder_minutes_before)
        try:
            # Requête réseau bloquante -> dans un thread, pour ne pas figer Discord.
            events = await asyncio.to_thread(self._calendar.list_events, now, until)
        except Exception as e:  # iCloud injoignable : on réessaiera dans 5 minutes
            log.warning("Calendrier injoignable : %s", e)
            return
        for event in events:
            key = (event["title"], event["start"])
            if event["all_day"] or key in self._seen_events or event["start"] < now.strftime("%Y-%m-%d %H:%M"):
                continue
            self._seen_events.add(key)
            where = f" ({event['location']})" if event.get("location") else ""
            await self._say(f"📅 À {event['start'][-5:]} : **{event['title']}**{where}. Prépare-toi ✨")


def build_scheduler(config: Config, agent: Agent, core: Core, send: SendFn,
                    calendar: Optional[Calendars] = None) -> AsyncIOScheduler:
    tz = config.timezone

    def ai_job(instruction: str, label: str) -> Callable[[], Awaitable[None]]:
        """Fabrique une tâche planifiée qui demande un message à l'agent puis te l'envoie."""
        async def job() -> None:
            log.info("⏰ %s", label)
            await send(await agent.ask(instruction, label=f"[{label} automatique]"))
        return job

    def at(t, **extra) -> CronTrigger:
        return CronTrigger(hour=t.hour, minute=t.minute, timezone=tz, **extra)

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(ai_job(MORNING_BRIEF_INSTRUCTION, "Brief du matin"), at(config.morning_brief_time))
    scheduler.add_job(
        ai_job(WEEKLY_PLAN_INSTRUCTION, "Plan de la semaine"),
        at(config.weekly_plan_time, day_of_week=config.weekly_plan_day),
    )
    for t in config.motivation_times:
        scheduler.add_job(ai_job(MOTIVATION_INSTRUCTION, "Message de motivation"), at(t))
    if config.evening_checkin_time:
        scheduler.add_job(ai_job(EVENING_CHECKIN_INSTRUCTION, "Bilan du soir"), at(config.evening_checkin_time))

    reminders = Reminders(config, agent, core, send, calendar)
    scheduler.add_job(reminders.check, IntervalTrigger(minutes=CHECK_EVERY_MINUTES, timezone=tz))
    return scheduler
