"""Configuration : lit le fichier .env et expose les réglages dans un objet `Config`.

C'est le seul endroit du code qui lit les variables d'environnement. Les autres
modules reçoivent la config en paramètre (voir main.py).
"""

import os
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


def _parse_time(value: str) -> time:
    """Transforme "07:30" en objet time(7, 30)."""
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


@dataclass(frozen=True)
class Config:
    # frozen=True : l'objet est en lecture seule une fois créé (comme un `const` en C).
    discord_token: str
    discord_owner_id: int
    anthropic_api_key: str
    claude_model: str
    timezone: ZoneInfo
    morning_brief_time: time
    weekly_plan_day: str
    weekly_plan_time: time
    reminder_minutes_before: int
    database_url: str


def load_config() -> Config:
    """Charge .env puis construit la Config. Plante tout de suite si un secret manque."""
    load_dotenv()  # copie le contenu de .env dans os.environ

    missing = [k for k in ("DISCORD_TOKEN", "DISCORD_OWNER_ID", "ANTHROPIC_API_KEY") if not os.getenv(k)]
    if missing:
        raise SystemExit(f"Variables manquantes dans .env : {', '.join(missing)} (voir .env.example)")

    return Config(
        discord_token=os.environ["DISCORD_TOKEN"],
        discord_owner_id=int(os.environ["DISCORD_OWNER_ID"]),
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        claude_model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5"),
        timezone=ZoneInfo(os.getenv("TIMEZONE", "Europe/Paris")),
        morning_brief_time=_parse_time(os.getenv("MORNING_BRIEF_TIME", "07:30")),
        weekly_plan_day=os.getenv("WEEKLY_PLAN_DAY", "sun"),
        weekly_plan_time=_parse_time(os.getenv("WEEKLY_PLAN_TIME", "19:00")),
        reminder_minutes_before=int(os.getenv("REMINDER_MINUTES_BEFORE", "15")),
        database_url=os.getenv("DATABASE_URL", "sqlite:///girlypop.db"),
    )
