"""Les outils que Claude peut utiliser, et leur traduction en appels au cœur métier.

Deux parties :
1. TOOLS : la description de chaque outil, envoyée à Claude (nom, rôle, paramètres en JSON Schema).
   Claude lit ces descriptions pour décider quoi appeler : une bonne description = un bon agent.
2. ToolExecutor : quand Claude demande un outil, on exécute la vraie fonction du cœur.

Pour ajouter un outil : une méthode dans core/, une entrée dans TOOLS, une ligne dans ToolExecutor.
"""

import json
from datetime import date, time
from typing import Any, Optional

from girlypop.core import Core

DATE = {"type": "string", "description": "Date au format AAAA-MM-JJ"}
TIME = {"type": "string", "description": "Heure au format HH:MM"}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "add_goal",
        "description": "Enregistre un nouvel objectif de Léa (études, sport, pro ou perso).",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Nom court, ex : 'Neurosciences'"},
                "category": {"type": "string", "enum": ["etudes", "sport", "pro", "perso"]},
                "description": {"type": "string", "description": "Ce que Léa veut atteindre, en une phrase"},
                "weekly_minutes": {"type": "integer", "description": "Temps visé par semaine, en minutes"},
            },
            "required": ["title", "category"],
        },
    },
    {
        "name": "list_goals",
        "description": "Liste les objectifs actifs de Léa.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_task",
        "description": "Ajoute une tâche. Le jour et l'heure sont facultatifs (sans jour = à planifier plus tard).",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "goal_id": {"type": "integer", "description": "Objectif lié, si la tâche en fait partie"},
                "day": DATE,
                "start_time": TIME,
                "duration_minutes": {"type": "integer"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_tasks",
        "description": "Liste les tâches non faites d'un jour donné, ou toutes si aucun jour n'est donné.",
        "input_schema": {"type": "object", "properties": {"day": DATE}},
    },
    {
        "name": "schedule_task",
        "description": "Place (ou déplace) une tâche existante à un jour et une heure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "day": DATE,
                "start_time": TIME,
                "duration_minutes": {"type": "integer"},
            },
            "required": ["task_id", "day"],
        },
    },
    {
        "name": "complete_task",
        "description": "Marque une tâche comme faite (et la session d'apprentissage liée, s'il y en a une).",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "create_learning_path",
        "description": (
            "Ajoute des sessions d'apprentissage ordonnées à un objectif. Chaque session a un thème précis "
            "et progressif, et une description de ce que Léa fera concrètement pendant la session."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer"},
                "sessions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string"},
                            "description": {"type": "string"},
                            "duration_minutes": {"type": "integer"},
                        },
                        "required": ["topic", "description"],
                    },
                },
            },
            "required": ["goal_id", "sessions"],
        },
    },
    {
        "name": "list_learning_sessions",
        "description": "Liste toutes les sessions du parcours d'un objectif, dans l'ordre, avec leur état.",
        "input_schema": {
            "type": "object",
            "properties": {"goal_id": {"type": "integer"}},
            "required": ["goal_id"],
        },
    },
    {
        "name": "plan_learning_session",
        "description": "Place une session d'apprentissage dans le planning (crée la tâche correspondante).",
        "input_schema": {
            "type": "object",
            "properties": {"session_id": {"type": "integer"}, "day": DATE, "start_time": TIME},
            "required": ["session_id", "day"],
        },
    },
    {
        "name": "get_day_overview",
        "description": "Vue d'ensemble d'un jour : objectifs, tâches du jour, tâches à planifier, prochaines sessions.",
        "input_schema": {"type": "object", "properties": {"day": DATE}, "required": ["day"]},
    },
    {
        "name": "get_week_overview",
        "description": "Vue d'ensemble de 7 jours à partir de start : tâches par jour, objectifs, prochaines sessions.",
        "input_schema": {"type": "object", "properties": {"start": DATE}, "required": ["start"]},
    },
]


def _date(value: Optional[str]) -> Optional[date]:
    return date.fromisoformat(value) if value else None


def _time(value: Optional[str]) -> Optional[time]:
    return time.fromisoformat(value) if value else None


class ToolExecutor:
    """Fait le pont entre le nom d'un outil (texte envoyé par Claude) et la fonction du cœur."""

    def __init__(self, core: Core):
        self._core = core

    def run(self, name: str, args: dict) -> str:
        """Exécute l'outil et renvoie le résultat en JSON (du texte, que Claude sait lire)."""
        c = self._core
        match name:
            case "add_goal":
                result = c.goals.add_goal(
                    args["title"], args["category"], args.get("description", ""), args.get("weekly_minutes")
                )
            case "list_goals":
                result = c.goals.list_goals()
            case "add_task":
                result = c.tasks.add_task(
                    args["title"],
                    goal_id=args.get("goal_id"),
                    day=_date(args.get("day")),
                    start_time=_time(args.get("start_time")),
                    duration_minutes=args.get("duration_minutes", 30),
                )
            case "list_tasks":
                result = c.tasks.list_tasks(day=_date(args.get("day")))
            case "schedule_task":
                result = c.tasks.schedule_task(
                    args["task_id"], _date(args["day"]), _time(args.get("start_time")), args.get("duration_minutes")
                )
            case "complete_task":
                result = c.tasks.complete_task(args["task_id"])
            case "create_learning_path":
                result = c.learning.add_sessions(args["goal_id"], args["sessions"])
            case "list_learning_sessions":
                result = c.learning.list_sessions(args["goal_id"])
            case "plan_learning_session":
                result = c.learning.plan_session(args["session_id"], _date(args["day"]), _time(args.get("start_time")))
            case "get_day_overview":
                result = c.planner.day_overview(_date(args["day"]))
            case "get_week_overview":
                result = c.planner.week_overview(_date(args["start"]))
            case _:
                raise ValueError(f"Outil inconnu : {name}")
        return json.dumps(result, ensure_ascii=False)
