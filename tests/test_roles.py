"""Tests des trois rôles (motivatrice, calendrier, Notion), SANS réseau.

Les parties « pures » (traduction Markdown -> Notion, lecture d'un événement iCalendar,
messages de transition) sont testées directement. Pour le reste, on remplace iCloud et
Notion par de faux objets qui enregistrent ce qu'on leur demande.
"""

import asyncio
import json
from datetime import date, datetime, time
from types import SimpleNamespace as Obj
from zoneinfo import ZoneInfo

import icalendar
import pytest

from girlypop.agent import Agent
from girlypop.agent.tools import CALENDAR_TOOLS, NOTION_TOOLS, TOOLS, ToolExecutor
from girlypop.config import _notion_id, _parse_times
from girlypop.core import build_core
from girlypop.db import init_db
from girlypop.integrations.apple_calendar import event_to_dict
from girlypop.integrations.notion import markdown_to_blocks, rich_text
from girlypop.scheduler.jobs import Reminders, transition_message

PARIS = ZoneInfo("Europe/Paris")


@pytest.fixture
def core():
    return build_core(init_db("sqlite://"))


# --- Motivatrice ------------------------------------------------------------------------

def test_transition_finds_task_that_just_ended_and_the_next_one(core):
    today = date(2026, 11, 24)
    a = core.tasks.add_task("Réviser chap. 3", day=today, start_time=time(9, 0), duration_minutes=60)
    core.tasks.add_task("Courir", day=today, start_time=time(11, 0), duration_minutes=30)

    now = datetime(2026, 11, 24, 10, 2, tzinfo=PARIS)
    ended = core.tasks.ending_between(datetime(2026, 11, 24, 9, 57, tzinfo=PARIS), now)
    assert [t["id"] for t in ended] == [a["id"]]
    assert core.tasks.next_task(now)["title"] == "Courir"

    text = transition_message(ended[0], core.tasks.next_task(now))
    assert "Réviser chap. 3" in text and "Courir" in text and "11:00" in text


def test_reminders_send_each_message_once_and_feed_agent_memory(core):
    sent, noted = [], []
    agent = Obj(note=noted.append)
    config = Obj(timezone=PARIS, reminder_minutes_before=15, transition_nudges=True)
    reminders = Reminders(config, agent, core, send=_collect(sent))
    core.tasks.add_task("Lire", day=date(2026, 11, 24), start_time=time(9, 0), duration_minutes=30)

    end_time = datetime(2026, 11, 24, 9, 31, tzinfo=PARIS)
    asyncio.run(reminders.transitions(end_time))
    asyncio.run(reminders.transitions(end_time))  # 2e passage : rien de nouveau
    assert len(sent) == 1 and "Lire" in sent[0]
    assert noted == sent


def test_calendar_reminders_skip_all_day_and_duplicates():
    sent = []
    events = [
        {"title": "Cours de bio", "start": "2026-11-24 14:00", "end": "2026-11-24 16:00",
         "all_day": False, "location": "Amphi B", "calendar": "Fac"},
        {"title": "Anniv de Jade", "start": "2026-11-24", "end": "2026-11-25",
         "all_day": True, "location": None, "calendar": "Perso"},
    ]
    calendar = Obj(list_events=lambda start, end: events)
    config = Obj(timezone=PARIS, reminder_minutes_before=15, transition_nudges=False)
    reminders = Reminders(config, Obj(note=lambda t: None), None, _collect(sent), calendar)

    now = datetime(2026, 11, 24, 13, 50, tzinfo=PARIS)
    asyncio.run(reminders.calendar_reminders(now))
    asyncio.run(reminders.calendar_reminders(now))
    assert sent == ["📅 À 14:00 : **Cours de bio** (Amphi B). Prépare-toi ✨"]


def test_parse_motivation_times():
    assert _parse_times("10:30, 15:00") == (time(10, 30), time(15, 0))
    assert _parse_times("") == ()


# --- Mémoire courte de l'agent ------------------------------------------------------------

def test_agent_remembers_previous_exchanges():
    seen = []

    async def create(**kwargs):
        seen.append(list(kwargs["messages"]))  # copie : la boucle complète la liste ensuite
        return Obj(stop_reason="end_turn", content=[Obj(type="text", text="ok")])

    agent = Agent(build_core(init_db("sqlite://")), api_key="fake", model="claude-opus-5-5", timezone=PARIS)
    agent._client = Obj(beta=Obj(messages=Obj(create=create)))
    agent.note("⏰ À 09:00 : **Lire** (tâche n°1)")
    asyncio.run(agent.ask("fait !"))

    history = seen[-1]
    assert [m["role"] for m in history] == ["user", "assistant", "user"]
    assert "Lire" in history[1]["content"]


# --- Calendrier Apple ----------------------------------------------------------------------

def test_event_to_dict_timed_and_all_day():
    timed = icalendar.Event()
    timed.add("summary", "Dentiste")
    timed.add("dtstart", datetime(2026, 11, 24, 13, 0, tzinfo=ZoneInfo("UTC")))
    timed.add("dtend", datetime(2026, 11, 24, 13, 30, tzinfo=ZoneInfo("UTC")))
    d = event_to_dict(timed, "Perso", PARIS)
    assert (d["start"], d["end"], d["all_day"]) == ("2026-11-24 14:00", "2026-11-24 14:30", False)

    all_day = icalendar.Event()
    all_day.add("summary", "Vacances")
    all_day.add("dtstart", date(2026, 12, 20))
    d = event_to_dict(all_day, "Perso", PARIS)
    assert (d["start"], d["end"], d["all_day"]) == ("2026-12-20", "2026-12-21", True)


def test_calendar_tools_only_offered_when_configured(core):
    names = lambda ex: {t["name"] for t in ex.tools}
    assert names(ToolExecutor(core)) == {t["name"] for t in TOOLS}

    calls = []
    fake_cal = Obj(
        list_events_for_days=lambda a, b: calls.append((a, b)) or [],
        create_event=lambda *args: calls.append(args) or {"ok": True},
    )
    ex = ToolExecutor(core, calendar=fake_cal)
    assert {t["name"] for t in CALENDAR_TOOLS} <= names(ex)
    ex.run("get_calendar_events", {"first_day": "2026-11-24", "last_day": "2026-11-30"})
    ex.run("add_calendar_event", {"title": "Bio", "day": "2026-11-25", "start_time": "10:00", "duration_minutes": 45})
    assert calls[0] == (date(2026, 11, 24), date(2026, 11, 30))
    assert calls[1] == ("Bio", date(2026, 11, 25), time(10, 0), 45, "")


def test_calendar_tool_refused_when_not_configured(core):
    with pytest.raises(ValueError):
        ToolExecutor(core).run("get_calendar_events", {"first_day": "2026-11-24", "last_day": "2026-11-24"})


# --- Notion ---------------------------------------------------------------------------------

def test_markdown_to_notion_blocks():
    md = """# Le neurone
Une cellule **excitable**, voir [Wikipédia](https://fr.wikipedia.org/wiki/Neurone).

## Notions clés
- Dendrites
1. Le signal arrive
- [ ] Relire la fiche
> Le cerveau contient ~86 milliards de neurones.
---
```python
print("spike")
```"""
    types = [b["type"] for b in markdown_to_blocks(md)]
    assert types == ["heading_1", "paragraph", "heading_2", "bulleted_list_item", "numbered_list_item",
                     "to_do", "quote", "divider", "code"]


def test_rich_text_bold_link_and_long_text():
    parts = rich_text("Un **potentiel** d'[action](https://ex.org)")
    assert parts[1]["annotations"]["bold"] is True
    assert parts[3]["text"]["link"] == {"url": "https://ex.org"}
    assert all(len(p["text"]["content"]) <= 2000 for p in rich_text("a" * 4500))


def test_notion_tool_creates_page(core):
    created = []
    fake_notion = Obj(create_page=lambda *args: created.append(args) or {"url": "https://notion.so/x"})
    ex = ToolExecutor(core, notion=fake_notion)
    assert {t["name"] for t in NOTION_TOOLS} <= {t["name"] for t in ex.tools}
    out = json.loads(ex.run("create_notion_page", {"title": "Le neurone", "content": "# Le neurone"}))
    assert out["url"] == "https://notion.so/x"
    assert created == [("Le neurone", "# Le neurone", "📚", None)]


def test_notion_id_accepts_link_or_id():
    raw = "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d"
    assert _notion_id(f"https://www.notion.so/leanak/Cours-{raw}?pvs=4") == raw
    assert _notion_id("1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d") == raw
    assert _notion_id("") is None


def _collect(sink):
    async def send(text):
        sink.append(text)
    return send
