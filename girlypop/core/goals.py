"""Service des objectifs.

Le cœur métier ne sait pas que Discord ou Claude existent : il reçoit des valeurs
Python simples et renvoie des dictionnaires simples. On peut donc le tester seul.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from girlypop.db.models import CATEGORIES, Goal


def goal_to_dict(goal: Goal) -> dict:
    return {
        "id": goal.id,
        "title": goal.title,
        "category": goal.category,
        "description": goal.description,
        "weekly_minutes": goal.weekly_minutes,
    }


class GoalService:
    def __init__(self, session_factory: sessionmaker[Session]):
        # On garde l'usine à sessions : chaque méthode ouvre sa propre session courte.
        self._sessions = session_factory

    def add_goal(
        self, title: str, category: str, description: str = "", weekly_minutes: Optional[int] = None
    ) -> dict:
        # Règle métier : la catégorie doit être connue.
        if category not in CATEGORIES:
            raise ValueError(f"Catégorie inconnue '{category}'. Choix possibles : {', '.join(CATEGORIES)}")

        # `with` ferme la session automatiquement à la fin du bloc (même en cas d'erreur).
        with self._sessions() as session:
            goal = Goal(title=title, category=category, description=description, weekly_minutes=weekly_minutes)
            session.add(goal)
            session.commit()  # c'est ici que l'INSERT est vraiment écrit dans le fichier
            return goal_to_dict(goal)

    def list_goals(self) -> list[dict]:
        with self._sessions() as session:
            goals = session.scalars(select(Goal).where(Goal.active).order_by(Goal.category, Goal.id))
            return [goal_to_dict(g) for g in goals]
