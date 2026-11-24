"""La couche Discord : recevoir tes messages, renvoyer les réponses.

Elle ne réfléchit pas : tout message reçu est transmis à l'agent, et la réponse
de l'agent est renvoyée telle quelle. Elle expose aussi `send_to_owner`, que le
scheduler utilise pour t'écrire de lui-même (brief du matin, rappels).
"""

import logging

import discord

from girlypop.agent import Agent

log = logging.getLogger(__name__)

DISCORD_MAX_LENGTH = 2000  # Discord refuse les messages de plus de 2000 caractères


def split_message(text: str, limit: int = DISCORD_MAX_LENGTH) -> list[str]:
    """Coupe un long texte en morceaux de moins de `limit` caractères, si possible entre deux lignes."""
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


class GirlypopBot(discord.Client):
    def __init__(self, agent: Agent, owner_id: int):
        # Les « intents » disent à Discord quels événements on veut recevoir.
        # message_content doit AUSSI être activé sur le portail développeur Discord.
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self._agent = agent
        self._owner_id = owner_id

    async def on_ready(self) -> None:
        # Appelé par discord.py une fois la connexion WebSocket établie.
        log.info("Connectée à Discord en tant que %s ✨", self.user)

    async def on_message(self, message: discord.Message) -> None:
        # Appelé par discord.py pour CHAQUE message que le bot voit.
        if message.author.id != self._owner_id:
            return  # on ignore tout le monde sauf toi (et le bot lui-même)
        if not isinstance(message.channel, discord.DMChannel) and self.user not in message.mentions:
            return  # sur un serveur, on ne répond que si on est mentionnée (@Girlypop)

        log.info("📩 %s", message.content)
        async with message.channel.typing():  # affiche « Girlypop est en train d'écrire... »
            answer = await self._agent.ask(message.content)
        for chunk in split_message(answer):
            await message.channel.send(chunk)

    async def send_to_owner(self, text: str) -> None:
        """T'envoie un message privé (utilisé par le scheduler)."""
        await self.wait_until_ready()
        user = await self.fetch_user(self._owner_id)
        for chunk in split_message(text):
            await user.send(chunk)
