"""Les outils que Claude peut utiliser, et leur traduction en appels au cœur métier.

Deux parties :
1. TOOLS : la description de chaque outil, envoyée à Claude (nom, rôle, paramètres en JSON Schema).
   Claude lit ces descriptions pour décider quoi appeler : une bonne description = un bon agent.
2. ToolExecutor : quand Claude demande un outil, on exécute la vraie fonction du cœur.

Pour ajouter un outil : une méthode dans core/, une entrée dans TOOLS, une ligne dans ToolExecutor.

Les outils du calendrier Apple et de Notion ne sont proposés à Claude QUE si
l'intégration est configurée dans .env (sinon Claude ne sait même pas qu'ils existent).
"""

import json
from datetime import date, time
from typing import Any, Optional

from girlypop.core import Core
from girlypop.integrations import AppleCalendar, NotionNotes

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


CALENDAR_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_calendar_events",
        "description": (
            "Lit les événements du calendrier Apple de Léa (cours, rendez-vous, sorties...) entre deux jours "
            "inclus. À consulter AVANT de proposer un planning, pour ne rien placer par-dessus."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"first_day": DATE, "last_day": DATE},
            "required": ["first_day", "last_day"],
        },
    },
    {
        "name": "add_calendar_event",
        "description": (
            "Ajoute un événement dans le calendrier « Girlypop » de Léa (visible sur son iPhone). "
            "Ne l'utilise que si Léa le demande ou a validé le planning proposé."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "day": DATE,
                "start_time": TIME,
                "duration_minutes": {"type": "integer"},
                "description": {"type": "string"},
            },
            "required": ["title", "day", "start_time", "duration_minutes"],
        },
    },
]

NOTION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_notion_page",
        "description": (
            "Crée une fiche de cours dans le Notion de Léa, sous sa page « Cours ». Le contenu est en "
            "Markdown simple : # ## ### titres, - listes, 1. listes numérotées, - [ ] cases à cocher, "
            "> citations, ```code```, --- séparateur, **gras**, *italique*, [lien](https://...). "
            "Pas de tableaux ni d'images. Renvoie le lien de la page."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titre de la fiche, ex : 'Le potentiel d'action'"},
                "content": {"type": "string", "description": "Le cours complet, en Markdown simple"},
                "emoji": {"type": "string", "description": "Un emoji pour l'icône de la page, ex : '🧠'"},
                "parent_page_id": {
                    "type": "string",
                    "description": "Facultatif : ID d'une page existante sous laquelle ranger la fiche (ex : un sujet)",
                },
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "append_to_notion_page",
        "description": "Ajoute du contenu (Markdown simple) à la fin d'une page Notion existante.",
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string"}, "content": {"type": "string"}},
            "required": ["page_id", "content"],
        },
    },
    {
        "name": "search_notion_pages",
        "description": (
            "Cherche parmi les fiches Notion déjà créées (par mot du titre). Sans query : liste les plus "
            "récentes. Utile pour éviter les doublons ou retrouver une page à compléter."
        ),
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
]

# Ces outils passent par Internet : l'agent les lance dans un thread pour ne pas bloquer Discord.
NETWORK_TOOLS = {t["name"] for t in CALENDAR_TOOLS + NOTION_TOOLS}


def _date(value: Optional[str]) -> Optional[date]:
    return date.fromisoformat(value) if value else None


def _time(value: Optional[str]) -> Optional[time]:
    return time.fromisoformat(value) if value else None


class ToolExecutor:
    """Fait le pont entre le nom d'un outil (texte envoyé par Claude) et la fonction du cœur."""

    def __init__(
        self, core: Core, calendar: Optional[AppleCalendar] = None, notion: Optional[NotionNotes] = None
    ):
        self._core = core
        self._calendar = calendar
        self._notion = notion
        # La liste des outils envoyée à Claude dépend de ce qui est branché.
        self.tools = TOOLS + (CALENDAR_TOOLS if calendar else []) + (NOTION_TOOLS if notion else [])

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
            case "get_calendar_events" if self._calendar:
                result = self._calendar.list_events_for_days(_date(args["first_day"]), _date(args["last_day"]))
            case "add_calendar_event" if self._calendar:
                result = self._calendar.create_event(
                    args["title"], _date(args["day"]), _time(args["start_time"]),
                    args["duration_minutes"], args.get("description", ""),
                )
            case "create_notion_page" if self._notion:
                result = self._notion.create_page(
                    args["title"], args["content"], args.get("emoji") or "📚", args.get("parent_page_id")
                )
            case "append_to_notion_page" if self._notion:
                result = self._notion.append_to_page(args["page_id"], args["content"])
            case "search_notion_pages" if self._notion:
                result = self._notion.search_pages(args.get("query", ""))
            case _:
                raise ValueError(f"Outil inconnu : {name}")
        return json.dumps(result, ensure_ascii=False)
