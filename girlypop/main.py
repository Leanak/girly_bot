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
from girlypop.integrations import AppleCalendar, Calendars, IcsCalendar, NotionNotes
from girlypop.integrations.ics_calendar import parse_feeds
from girlypop.scheduler import build_scheduler

log = logging.getLogger("girlypop")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = load_config()                                  # 1. lit .env
    session_factory = init_db(config.database_url)          # 2. ouvre SQLite, crée les tables
    core = build_core(session_factory)                      # 3. services métier

    # 4. Intégrations : seulement si leurs identifiants sont dans .env.
    apple = None
    if config.calendar_enabled:
        apple = AppleCalendar(
            config.icloud_username, config.icloud_app_password, config.timezone,
            url=config.caldav_url, own_calendar_name=config.girlypop_calendar_name,
            read_calendar_names=config.read_calendar_names,
        )
    feeds = parse_feeds(config.ics_calendars)  # Google Agenda & co, en lecture seule
    ics = IcsCalendar(feeds, config.timezone) if feeds else None
    calendar = Calendars(apple, ics) if (apple or ics) else None
    notion = NotionNotes(config.notion_token, config.notion_parent_page_id) if config.notion_enabled else None
    log.info("📅 Calendriers : %s", calendar.describe() if calendar else "aucun configuré")
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
