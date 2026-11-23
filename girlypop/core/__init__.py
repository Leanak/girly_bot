"""Couche métier : les règles de ton organisation, indépendantes de Discord et de l'IA."""

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from girlypop.core.goals import GoalService
from girlypop.core.learning import LearningService
from girlypop.core.planner import PlannerService
from girlypop.core.tasks import TaskService


@dataclass
class Core:
    """Regroupe tous les services du cœur, pour les passer d'un coup aux autres couches."""

    goals: GoalService
    tasks: TaskService
    learning: LearningService
    planner: PlannerService


def build_core(session_factory: sessionmaker[Session]) -> Core:
    goals = GoalService(session_factory)
    tasks = TaskService(session_factory)
    learning = LearningService(session_factory)
    planner = PlannerService(goals, tasks, learning)
    return Core(goals=goals, tasks=tasks, learning=learning, planner=planner)
