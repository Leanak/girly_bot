"""Service des parcours d'apprentissage.

Répartition des rôles :
- Claude INVENTE les thèmes des sessions (il est bon pour ça).
- Ce service les MÉMORISE dans l'ordre et sait toujours quelle est « la prochaine »
  (une base de données est fiable pour ça, une IA beaucoup moins).
"""

from datetime import date, time
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from girlypop.db.models import Goal, LearningSession, Task


def session_to_dict(s: LearningSession) -> dict:
    return {
        "id": s.id,
        "goal_id": s.goal_id,
        "position": s.position,
        "topic": s.topic,
        "description": s.description,
        "duration_minutes": s.duration_minutes,
        "done": s.done,
    }


class LearningService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._sessions = session_factory

    def add_sessions(self, goal_id: int, sessions: list[dict]) -> list[dict]:
        """Ajoute des sessions à la fin du parcours d'un objectif.

        `sessions` est une liste de {"topic": ..., "description": ..., "duration_minutes": ...}.
        """
        with self._sessions() as db:
            if db.get(Goal, goal_id) is None:
                raise ValueError(f"Aucun objectif n°{goal_id}")
            # On continue la numérotation après la dernière session existante.
            last = db.scalar(select(func.max(LearningSession.position)).where(LearningSession.goal_id == goal_id))
            position = (last or 0) + 1

            created = []
            for item in sessions:
                s = LearningSession(
                    goal_id=goal_id,
                    position=position,
                    topic=item["topic"],
                    description=item.get("description", ""),
                    duration_minutes=item.get("duration_minutes", 45),
                )
                db.add(s)
                created.append(s)
                position += 1
            db.commit()
            return [session_to_dict(s) for s in created]

    def list_sessions(self, goal_id: int) -> list[dict]:
        with self._sessions() as db:
            query = select(LearningSession).where(LearningSession.goal_id == goal_id).order_by(LearningSession.position)
            return [session_to_dict(s) for s in db.scalars(query)]

    def next_sessions(self) -> list[dict]:
        """Pour chaque objectif, la première session pas encore faite ni déjà planifiée."""
        with self._sessions() as db:
            # Sessions déjà transformées en tâche non terminée = déjà planifiées.
            planned_ids = select(Task.learning_session_id).where(
                Task.learning_session_id.is_not(None), Task.done.is_(False)
            )
            query = (
                select(LearningSession)
                .where(LearningSession.done.is_(False), LearningSession.id.not_in(planned_ids))
                .order_by(LearningSession.goal_id, LearningSession.position)
            )
            result, seen_goals = [], set()
            for s in db.scalars(query):
                if s.goal_id not in seen_goals:
                    seen_goals.add(s.goal_id)
                    result.append({**session_to_dict(s), "goal_title": s.goal.title})
            return result

    def plan_session(self, session_id: int, day: date, start_time: Optional[time]) -> dict:
        """Place une session dans le planning en créant la tâche correspondante."""
        with self._sessions() as db:
            s = db.get(LearningSession, session_id)
            if s is None:
                raise ValueError(f"Aucune session n°{session_id}")
            task = Task(
                title=f"{s.goal.title} — Session {s.position} : {s.topic}",
                goal_id=s.goal_id,
                day=day,
                start_time=start_time,
                duration_minutes=s.duration_minutes,
                learning_session_id=s.id,
            )
            db.add(task)
            db.commit()
            return {"task_id": task.id, "title": task.title}
