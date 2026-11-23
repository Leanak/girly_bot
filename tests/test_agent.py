"""Test de la boucle d'agent avec un FAUX Claude (aucun appel réseau, aucun coût).

Le faux Claude répond d'abord « appelle add_task », puis « C'est noté ! ».
On vérifie que l'agent a bien exécuté l'outil et renvoyé le texte final.
"""

import asyncio
from types import SimpleNamespace as Obj
from zoneinfo import ZoneInfo

from girlypop.agent import Agent
from girlypop.core import build_core
from girlypop.db import init_db


class FakeMessages:
    def __init__(self):
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            tool_call = Obj(type="tool_use", id="t1", name="add_task", input={"title": "Réviser chap. 3"})
            return Obj(stop_reason="tool_use", content=[tool_call])
        # Au 2e appel, Claude doit avoir reçu le résultat de l'outil.
        assert kwargs["messages"][-1]["content"][0]["type"] == "tool_result"
        return Obj(stop_reason="end_turn", content=[Obj(type="text", text="C'est noté ! ✨")])


def test_agent_loop_runs_tool_then_answers():
    core = build_core(init_db("sqlite://"))
    agent = Agent(core, api_key="fake", model="claude-opus-5-5", timezone=ZoneInfo("Europe/Paris"))
    agent._client = Obj(beta=Obj(messages=FakeMessages()))  # on remplace le vrai client par le faux

    answer = asyncio.run(agent.ask("Ajoute réviser le chapitre 3"))

    assert answer == "C'est noté ! ✨"
    assert core.tasks.list_tasks()[0]["title"] == "Réviser chap. 3"
