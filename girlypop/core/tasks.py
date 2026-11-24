"""Service des tâches : ajouter, planifier, cocher, trouver celles à rappeler."""

from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from girlypop.db.models import Goal, Task


def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "goal_id": task.goal_id,
        "day": task.day.isoformat() if task.day else None,
        "start_time": task.start_time.strftime("%H:%M") if task.start_time else None,
        "duration_minutes": task.duration_minutes,
        "done": task.done,
        "learning_session_id": task.learning_session_id,
    }


class TaskService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._sessions = session_factory

    def add_task(
        self,
        title: str,
        goal_id: Optional[int] = None,
        day: Optional[date] = None,
        start_time: Optional[time] = None,
        duration_minutes: int = 30,
    ) -> dict:
        with self._sessions() as session:
            if goal_id is not None and session.get(Goal, goal_id) is None:
                raise ValueError(f"Aucun objectif n°{goal_id}")
            task = Task(
                title=title, goal_id=goal_id, day=day, start_time=start_time, duration_minutes=duration_minutes
            )
            session.add(task)
            session.commit()
            return task_to_dict(task)

    def list_tasks(self, day: Optional[date] = None, include_done: bool = False) -> list[dict]:
        """Les tâches d'un jour donné, ou toutes les tâches si `day` est None."""
        with self._sessions() as session:
            query = select(Task)
            if day is not None:
                query = query.where(Task.day == day)
            if not include_done:
                query = query.where(Task.done.is_(False))
            query = query.order_by(Task.day, Task.start_time)
            return [task_to_dict(t) for t in session.scalars(query)]

    def list_unscheduled(self) -> list[dict]:
        """Les tâches pas encore placées dans un jour (à caser dans le planning)."""
        with self._sessions() as session:
            query = select(Task).where(Task.day.is_(None), Task.done.is_(False))
            return [task_to_dict(t) for t in session.scalars(query)]

    def schedule_task(
        self, task_id: int, day: date, start_time: Optional[time], duration_minutes: Optional[int] = None
    ) -> dict:
        with self._sessions() as session:
            task = self._get(session, task_id)
            task.day = day
            task.start_time = start_time
            if duration_minutes is not None:
                task.duration_minutes = duration_minutes
            task.reminded = False  # nouvel horaire => nouveau rappel
            session.commit()
            return task_to_dict(task)

    def complete_task(self, task_id: int) -> dict:
        with self._sessions() as session:
            task = self._get(session, task_id)
            task.done = True
            # Règle métier : finir la tâche d'une session d'apprentissage valide la session.
            if task.learning_session is not None:
                task.learning_session.done = True
            session.commit()
            return task_to_dict(task)

    def due_for_reminder(self, now: datetime, minutes_before: int) -> list[dict]:
        """Tâches non faites, pas encore rappelées, qui commencent entre maintenant et now + minutes_before."""
        limit = now + timedelta(minutes=minutes_before)
        with self._sessions() as session:
            query = select(Task).where(
                Task.done.is_(False),
                Task.reminded.is_(False),
                Task.day == now.date(),
                Task.start_time.is_not(None),
            )
            due = []
            for task in session.scalars(query):
                start = datetime.combine(task.day, task.start_time, tzinfo=now.tzinfo)
                if now <= start <= limit:
                    due.append(task_to_dict(task))
            return due

    def ending_between(self, after: datetime, until: datetime) -> list[dict]:
        """Tâches du jour non faites dont l'heure de FIN tombe dans ]after, until].

        Sert au message « c'est l'heure de passer à la suite » de la motivatrice.
        """
        ending = []
        for task in self._timed_tasks(until.date()):
            start = datetime.combine(task.day, task.start_time, tzinfo=until.tzinfo)
            end = start + timedelta(minutes=task.duration_minutes)
            if after < end <= until:
                ending.append(task_to_dict(task))
        return ending

    def next_task(self, now: datetime) -> Optional[dict]:
        """La prochaine tâche du jour qui n'a pas encore commencé (ou None)."""
        upcoming = [
            t for t in self._timed_tasks(now.date())
            if datetime.combine(t.day, t.start_time, tzinfo=now.tzinfo) >= now
        ]
        return task_to_dict(min(upcoming, key=lambda t: t.start_time)) if upcoming else None

    def _timed_tasks(self, day: date) -> list[Task]:
        with self._sessions() as session:
            query = select(Task).where(Task.done.is_(False), Task.day == day, Task.start_time.is_not(None))
            return list(session.scalars(query))

    def mark_reminded(self, task_id: int) -> None:
        with self._sessions() as session:
            self._get(session, task_id).reminded = True
            session.commit()

    @staticmethod
    def _get(session: Session, task_id: int) -> Task:
        task = session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Aucune tâche n°{task_id}")
        return task
