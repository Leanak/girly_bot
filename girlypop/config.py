"""Configuration : lit le fichier .env et expose les réglages dans un objet `Config`.

C'est le seul endroit du code qui lit les variables d'environnement. Les autres
modules reçoivent la config en paramètre (voir main.py).
"""

import os
import re
from dataclasses import dataclass
from datetime import time
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


def _parse_time(value: str) -> time:
    """Transforme "07:30" en objet time(7, 30)."""
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def _parse_times(value: str) -> tuple[time, ...]:
    """Transforme "10:30, 15:00" en (time(10, 30), time(15, 0)). Vide = aucune heure."""
    return tuple(_parse_time(v.strip()) for v in value.split(",") if v.strip())


def _optional_time(value: str) -> Optional[time]:
    """Une heure, ou None si la valeur est vide (= fonction désactivée)."""
    return _parse_time(value) if value.strip() else None


def _flag(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "oui", "yes", "on")


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

    # --- Rôle Motivatrice ---
    motivation_times: tuple[time, ...]  # heures des petits messages de motivation
    evening_checkin_time: Optional[time]  # bilan du soir (None = désactivé)
    transition_nudges: bool  # message « on passe à la suite ? » à la fin d'une tâche

    # --- Rôle Assistante de temps : calendrier Apple (facultatif) ---
    icloud_username: Optional[str]
    icloud_app_password: Optional[str]
    caldav_url: str
    girlypop_calendar_name: str  # le seul calendrier où elle écrit
    read_calendar_names: tuple[str, ...]  # vide = elle lit tous tes calendriers

    # --- Agendas en lecture seule par adresse iCal secrète : Google Agenda, Outlook... (facultatif) ---
    ics_calendars: str  # "Nom|https://...,Autre|https://..."

    # --- Google Agenda par l'API, lecture + écriture (facultatif) ---
    google_enabled: bool
    google_token_file: str
    google_write_calendar: str  # "primary", ou l'ID / le nom d'un agenda

    # --- Rôle Prof particulière : Notion (facultatif) ---
    notion_token: Optional[str]
    notion_parent_page_id: Optional[str]

    @property
    def calendar_enabled(self) -> bool:
        return bool(self.icloud_username and self.icloud_app_password)

    @property
    def notion_enabled(self) -> bool:
        return bool(self.notion_token and self.notion_parent_page_id)


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
        motivation_times=_parse_times(os.getenv("MOTIVATION_TIMES", "10:30,14:30,17:00")),
        evening_checkin_time=_optional_time(os.getenv("EVENING_CHECKIN_TIME", "21:00")),
        transition_nudges=_flag(os.getenv("TRANSITION_NUDGES", "true")),
        icloud_username=os.getenv("ICLOUD_USERNAME") or None,
        icloud_app_password=os.getenv("ICLOUD_APP_PASSWORD") or None,
        caldav_url=os.getenv("CALDAV_URL", "https://caldav.icloud.com/"),
        girlypop_calendar_name=os.getenv("GIRLYPOP_CALENDAR_NAME", "Girlypop"),
        ics_calendars=os.getenv("ICS_CALENDARS", ""),
        google_enabled=_flag(os.getenv("GOOGLE_CALENDAR", "false")),
        google_token_file=os.getenv("GOOGLE_TOKEN_FILE", "google_token.json"),
        google_write_calendar=os.getenv("GOOGLE_WRITE_CALENDAR", "primary"),
        read_calendar_names=tuple(n.strip() for n in os.getenv("READ_CALENDARS", "").split(",") if n.strip()),
        notion_token=os.getenv("NOTION_TOKEN") or None,
        notion_parent_page_id=_notion_id(os.getenv("NOTION_PARENT_PAGE_ID", "")),
    )


def _notion_id(value: str) -> Optional[str]:
    """Accepte l'ID nu OU le lien complet de la page (on garde les 32 caractères de la fin)."""
    value = value.strip().split("?")[0].rstrip("/")
    if not value:
        return None
    match = re.search(r"([0-9a-fA-F]{32})$", value.replace("-", ""))
    return match.group(1) if match else value
