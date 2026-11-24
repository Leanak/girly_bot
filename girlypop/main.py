"""Point d'entrée : `python -m girlypop.main`.

C'est le SEUL fichier qui connaît toutes les couches. Il les construit de bas en haut
et passe à chacune ce dont elle a besoin (injection de dépendances) :

    config -> db -> core -> agent -> bot -> scheduler
"""

import asyncio
import logging

from girlypop.agent import Agent
from girlypop.bot import GirlypopBot
from girlypop.config import load_config
from girlypop.core import build_core
from girlypop.db import init_db
from girlypop.scheduler import build_scheduler


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = load_config()                                  # 1. lit .env
    session_factory = init_db(config.database_url)          # 2. ouvre SQLite, crée les tables
    core = build_core(session_factory)                      # 3. services métier
    agent = Agent(core, config.anthropic_api_key, config.claude_model, config.timezone)  # 4. IA
    bot = GirlypopBot(agent, config.discord_owner_id)       # 5. Discord
    scheduler = build_scheduler(config, agent, core, bot.send_to_owner)  # 6. réveils

    async with bot:
        scheduler.start()               # démarre les réveils dans la même boucle d'événements
        await bot.start(config.discord_token)  # se connecte à Discord et tourne jusqu'à Ctrl+C


if __name__ == "__main__":
    asyncio.run(main())
