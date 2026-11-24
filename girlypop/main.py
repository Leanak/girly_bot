"""Point d'entrée : `python -m girlypop.main`.

C'est le SEUL fichier qui connaît toutes les couches. Il les construit de bas en haut
et passe à chacune ce dont elle a besoin (injection de dépendances) :

    config -> db -> core -> intégrations (facultatives) -> agent -> bot -> scheduler
"""

import asyncio
import logging

from girlypop.agent import Agent
from girlypop.bot import GirlypopBot
from girlypop.config import load_config
from girlypop.core import build_core
from girlypop.db import init_db
from girlypop.integrations import AppleCalendar, NotionNotes
from girlypop.scheduler import build_scheduler

log = logging.getLogger("girlypop")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = load_config()                                  # 1. lit .env
    session_factory = init_db(config.database_url)          # 2. ouvre SQLite, crée les tables
    core = build_core(session_factory)                      # 3. services métier

    # 4. Intégrations : seulement si leurs identifiants sont dans .env.
    calendar = None
    if config.calendar_enabled:
        calendar = AppleCalendar(
            config.icloud_username, config.icloud_app_password, config.timezone,
            url=config.caldav_url, own_calendar_name=config.girlypop_calendar_name,
            read_calendar_names=config.read_calendar_names,
        )
    notion = NotionNotes(config.notion_token, config.notion_parent_page_id) if config.notion_enabled else None
    log.info("📅 Calendrier Apple : %s", "branché" if calendar else "non configuré")
    log.info("📚 Notion : %s", "branché" if notion else "non configuré")

    agent = Agent(core, config.anthropic_api_key, config.claude_model, config.timezone,
                  calendar=calendar, notion=notion)  # 5. IA
    bot = GirlypopBot(agent, config.discord_owner_id)       # 6. Discord
    scheduler = build_scheduler(config, agent, core, bot.send_to_owner, calendar)  # 7. réveils

    async with bot:
        scheduler.start()               # démarre les réveils dans la même boucle d'événements
        await bot.start(config.discord_token)  # se connecte à Discord et tourne jusqu'à Ctrl+C


if __name__ == "__main__":
    asyncio.run(main())
