"""Les tables de la base, décrites comme des classes Python (SQLAlchemy 2).

Chaque classe = une table. Chaque attribut `Mapped[...]` = une colonne.
Parallèle C : une ligne de table ressemble à une `struct`, SQLAlchemy fait la
conversion struct <-> SQL pour nous.

Cette couche ne contient AUCUNE logique métier : juste la forme des données.
"""

from datetime import date, time
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Les catégories d'objectifs autorisées (vérifiées dans core/goals.py).
CATEGORIES = ("etudes", "sport", "pro", "perso")


class Base(DeclarativeBase):
    """Classe mère commune : SQLAlchemy s'en sert pour connaître toutes les tables."""


class Goal(Base):
    """Un objectif : « Réussir mes partiels », « Neurosciences », « Courir 3x/semaine »..."""

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)  # numéro unique, attribué par SQLite
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(20))  # une valeur de CATEGORIES
    description: Mapped[str] = mapped_column(default="")
    weekly_minutes: Mapped[Optional[int]]  # temps visé par semaine (facultatif)
    active: Mapped[bool] = mapped_column(default=True)

    # Liens vers les autres tables (SQLAlchemy fait les jointures pour nous).
    tasks: Mapped[list["Task"]] = relationship(back_populates="goal")
    learning_sessions: Mapped[list["LearningSession"]] = relationship(
        back_populates="goal", order_by="LearningSession.position"
    )


class Task(Base):
    """Une tâche concrète, éventuellement placée à un jour et une heure."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    goal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("goals.id"))
    day: Mapped[Optional[date]]  # None = pas encore planifiée
    start_time: Mapped[Optional[time]]  # None = « dans la journée »
    duration_minutes: Mapped[int] = mapped_column(default=30)
    done: Mapped[bool] = mapped_column(default=False)
    reminded: Mapped[bool] = mapped_column(default=False)  # rappel déjà envoyé ?

    # Si cette tâche sert à faire une session d'apprentissage, on garde le lien.
    learning_session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("learning_sessions.id"))

    goal: Mapped[Optional[Goal]] = relationship(back_populates="tasks")
    learning_session: Mapped[Optional["LearningSession"]] = relationship()


class LearningSession(Base):
    """Une session d'un parcours d'apprentissage, avec un thème précis et une place dans l'ordre."""

    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id"))
    position: Mapped[int]  # 1, 2, 3... l'ordre du parcours
    topic: Mapped[str] = mapped_column(String(300))  # ex : « Le potentiel d'action »
    description: Mapped[str] = mapped_column(default="")  # ce qu'on fait pendant la session
    duration_minutes: Mapped[int] = mapped_column(default=45)
    done: Mapped[bool] = mapped_column(default=False)

    goal: Mapped[Goal] = relationship(back_populates="learning_sessions")
