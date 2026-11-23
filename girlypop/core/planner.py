"""Service de planning : rassemble tout ce qu'il faut savoir pour organiser un jour ou une semaine.

Ce service ne « décide » pas du planning : il prépare une vue d'ensemble claire.
C'est Claude qui propose l'emploi du temps à partir de cette vue, puis le fixe
avec les outils schedule_task / plan_learning_session.
"""

from datetime import date, timedelta

from girlypop.core.goals import GoalService
from girlypop.core.learning import LearningService
from girlypop.core.tasks import TaskService


class PlannerService:
    def __init__(self, goals: GoalService, tasks: TaskService, learning: LearningService):
        # Le planner s'appuie sur les autres services du cœur (il ne touche pas la base directement).
        self._goals = goals
        self._tasks = tasks
        self._learning = learning

    def day_overview(self, day: date) -> dict:
        return {
            "day": day.isoformat(),
            "weekday": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][day.weekday()],
            "goals": self._goals.list_goals(),
            "tasks_today": self._tasks.list_tasks(day=day),
            "unscheduled_tasks": self._tasks.list_unscheduled(),
            "next_learning_sessions": self._learning.next_sessions(),
        }

    def week_overview(self, start: date) -> dict:
        days = [start + timedelta(days=i) for i in range(7)]
        return {
            "week_start": start.isoformat(),
            "goals": self._goals.list_goals(),
            "tasks_by_day": {d.isoformat(): self._tasks.list_tasks(day=d) for d in days},
            "unscheduled_tasks": self._tasks.list_unscheduled(),
            "next_learning_sessions": self._learning.next_sessions(),
        }
