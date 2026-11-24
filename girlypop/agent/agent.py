"""L'agent : la boucle qui fait dialoguer Claude et nos outils.

Le principe (voir docs/ARCHITECTURE.md, flux A) :
  1. On envoie à Claude : les consignes + le message + la liste des outils.
  2. Si Claude répond « je veux appeler tel outil », on l'exécute et on lui renvoie le résultat.
  3. On recommence jusqu'à ce que Claude réponde avec du texte final.

Mémoire courte : l'agent garde les derniers échanges (texte seulement) et les renvoie
à Claude à chaque message. Comme ça, quand tu réponds « fait ! » à un rappel, elle
sait de quoi tu parles. Cette mémoire vit dans la RAM : elle s'efface au redémarrage
(ce qui doit durer va en base, via les outils).

On écrit cette boucle à la main (plutôt qu'avec l'assistant automatique du SDK)
pour que tu voies exactement ce qui se passe.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import anthropic

from girlypop.agent.prompts import build_system_prompt
from girlypop.agent.tools import NETWORK_TOOLS, ToolExecutor
from girlypop.core import Core
from girlypop.integrations import Calendars, NotionNotes

log = logging.getLogger(__name__)

MAX_STEPS = 15  # garde-fou : on n'enchaîne jamais plus de 15 allers-retours avec Claude
HISTORY_LIMIT = 20  # nombre de messages gardés en mémoire courte (10 échanges)
WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


class Agent:
    def __init__(
        self,
        core: Core,
        api_key: str,
        model: str,
        timezone: ZoneInfo,
        calendar: Optional[Calendars] = None,
        notion: Optional[NotionNotes] = None,
    ):
        # AsyncAnthropic : version « async » du client, pour ne pas bloquer Discord pendant qu'on attend Claude.
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._tz = timezone
        self._tools = ToolExecutor(core, calendar, notion)
        self._system = build_system_prompt(calendar=calendar is not None, notion=notion is not None)
        self._history: list[dict] = []  # mémoire courte : [{"role": "user"|"assistant", "content": "..."}]
        # Un seul échange à la fois (ex : un rappel automatique pendant que tu écris) : sinon les
        # deux conversations se mélangeraient dans la mémoire courte.
        self._lock = asyncio.Lock()

    async def ask(self, text: str, label: Optional[str] = None) -> str:
        """Envoie un message à Claude, laisse-le utiliser les outils, et renvoie sa réponse finale.

        `label` : pour les messages automatiques (brief, bilan...), le texte court à garder en
        mémoire à la place de la longue consigne.
        """
        async with self._lock:
            # Claude ne connaît pas la date du jour : on la lui donne au début du message.
            now = datetime.now(self._tz)
            context = f"[Nous sommes le {WEEKDAYS[now.weekday()]} {now:%Y-%m-%d}, il est {now:%H:%M}.]\n"
            answer = await self._run(self._history + [{"role": "user", "content": context + text}])
            self._remember(context + (label or text), answer)
            return answer

    def note(self, sent_text: str, label: str = "[Message automatique de Girlypop]") -> None:
        """Ajoute à la mémoire courte un message envoyé sans Claude (ex : un rappel du scheduler)."""
        self._remember(label, sent_text)

    def _remember(self, user_text: str, answer: str) -> None:
        self._history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": answer}]
        self._history = self._history[-HISTORY_LIMIT:]  # nombre pair : on commence toujours par "user"

    async def _run(self, messages: list[dict]) -> str:
        """La boucle d'agent elle-même (voir le docstring du module)."""
        messages = list(messages)  # copie : les étapes intermédiaires (outils) ne vont pas en mémoire

        for _ in range(MAX_STEPS):
            try:
                response = await self._client.beta.messages.create(
                    model=self._model,
                    max_tokens=16000,
                    system=self._system,
                    tools=self._tools.tools,
                    messages=messages,
                    # effort : combien Claude réfléchit avant de répondre (low, medium, high...).
                    output_config={"effort": "medium"},
                    # Si le modèle principal refuse une demande, l'API réessaie toute seule sur un autre modèle.
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
            except anthropic.RateLimitError:
                return "Je suis un peu débordée là 😅 Réessaie dans une minute."
            except anthropic.APIConnectionError:
                return "Je n'arrive pas à joindre mon cerveau (problème réseau) 🌧️"
            except anthropic.APIStatusError as e:
                log.error("Erreur API Claude %s : %s", e.status_code, e.message)
                return "Oups, j'ai eu un souci technique. Regarde les logs du terminal."

            # On garde la réponse COMPLÈTE de Claude dans l'historique (texte, réflexion, appels d'outils).
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "refusal":
                return "Je ne peux pas t'aider sur ce point, désolée."

            if response.stop_reason != "tool_use":
                # Claude a fini : on récupère tous les morceaux de texte de sa réponse.
                return "\n".join(b.text for b in response.content if b.type == "text").strip() or "✨"

            # Claude veut utiliser un ou plusieurs outils : on les exécute tous...
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                log.info("🔧 outil: %s %s", block.name, block.input)
                try:
                    if block.name in NETWORK_TOOLS:  # iCloud / Notion : dans un thread, pour ne pas figer Discord
                        output = await asyncio.to_thread(self._tools.run, block.name, block.input)
                    else:
                        output = self._tools.run(block.name, block.input)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
                except Exception as e:  # une erreur d'outil n'arrête pas l'agent : on la signale à Claude
                    log.warning("   ↳ erreur: %s", e)
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": f"Erreur : {e}", "is_error": True}
                    )
            # ...et on renvoie tous les résultats d'un coup, dans un seul message.
            messages.append({"role": "user", "content": results})

        return "J'ai dû m'arrêter avant la fin (trop d'étapes). Tu peux reformuler ?"
