"""Tests du cœur métier, SANS Discord et SANS Claude.

Si ces tests passent, c'est la preuve que la couche core/ est bien indépendante.
On utilise une base SQLite en mémoire (« sqlite://») : elle disparaît à la fin du test.
"""

import json
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from girlypop.agent.tools import TOOLS, ToolExecutor
from girlypop.bot.discord_bot import split_message
from girlypop.core import build_core
from girlypop.db import init_db

PARIS = ZoneInfo("Europe/Paris")


@pytest.fixture
def core():
    # Une fixture pytest : un nouveau cœur tout neuf est fabriqué pour chaque test.
    return build_core(init_db("sqlite://"))


def test_add_and_list_goals(core):
    core.goals.add_goal("Neurosciences", "perso", weekly_minutes=180)
    goals = core.goals.list_goals()
    assert [g["title"] for g in goals] == ["Neurosciences"]


def test_unknown_category_is_refused(core):
    with pytest.raises(ValueError):
        core.goals.add_goal("Truc", "n'importe-quoi")


def test_learning_path_order_and_next_session(core):
    goal = core.goals.add_goal("Neurosciences", "perso")
    core.learning.add_sessions(
        goal["id"],
        [
            {"topic": "Le neurone", "description": "Lire un chapitre d'intro"},
            {"topic": "Le potentiel d'action", "description": "Vidéo + schéma"},
        ],
    )
    first = core.learning.next_sessions()[0]
    assert first["topic"] == "Le neurone" and first["position"] == 1

    # Planifier la session crée une tâche ; la session suivante devient « la prochaine ».
    planned = core.learning.plan_session(first["id"], date(2026, 11, 24), time(18, 0))
    assert core.learning.next_sessions()[0]["topic"] == "Le potentiel d'action"

    # Finir la tâche valide la session.
    core.tasks.complete_task(planned["task_id"])
    assert core.learning.list_sessions(goal["id"])[0]["done"] is True


def test_reminders(core):
    task = core.tasks.add_task("Réviser chap. 3", day=date(2026, 11, 24), start_time=time(14, 0))
    now = datetime(2026, 11, 24, 13, 50, tzinfo=PARIS)

    assert [t["id"] for t in core.tasks.due_for_reminder(now, 15)] == [task["id"]]
    core.tasks.mark_reminded(task["id"])
    assert core.tasks.due_for_reminder(now, 15) == []  # pas de double rappel


def test_tool_executor_calls_core(core):
    # On simule ce que ferait Claude : appeler un outil par son nom avec des arguments JSON.
    tools = ToolExecutor(core)
    result = json.loads(tools.run("add_task", {"title": "Courir", "day": "2026-11-24", "start_time": "07:00"}))
    assert result["start_time"] == "07:00"
    overview = json.loads(tools.run("get_day_overview", {"day": "2026-11-24"}))
    assert overview["tasks_today"][0]["title"] == "Courir"


def test_every_tool_is_handled(core):
    # Chaque outil décrit à Claude doit exister dans ToolExecutor (sinon : « Outil inconnu »).
    tools = ToolExecutor(core)
    for tool in TOOLS:
        try:
            tools.run(tool["name"], {})
        except ValueError as e:
            assert "Outil inconnu" not in str(e)
        except (KeyError, TypeError):
            pass  # arguments manquants : normal ici, l'outil existe bien


def test_split_message():
    chunks = split_message("a" * 4500)
    assert all(len(c) <= 2000 for c in chunks) and "".join(chunks) == "a" * 4500
