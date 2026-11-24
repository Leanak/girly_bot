"""Les calendriers en lecture seule par « adresse iCal secrète » (Google Agenda, Outlook...).

Google Agenda donne, pour chaque agenda, une adresse secrète au format iCal (.ics) :
un simple lien qui renvoie tous les événements. Pas de compte développeur, pas d'OAuth :
on télécharge le fichier et on le lit avec `icalendar`.

Limites :
- LECTURE SEULE : Girlypop voit tes événements mais ne peut pas en ajouter.
  Pour écrire dans Google Agenda, utilise plutôt l'API (google_calendar.py).
- Google met à jour ce fichier avec un peu de retard (souvent quelques minutes,
  parfois plus) : un événement tout juste créé peut mettre un moment à apparaître.

Sécurité : ce lien donne accès à tout l'agenda, sans mot de passe. Il va dans .env
et nulle part ailleurs. S'il fuit, Google permet de le réinitialiser.
"""

import logging
import time as clock
import urllib.request
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

from girlypop.integrations.apple_calendar import event_to_dict

log = logging.getLogger(__name__)

CACHE_SECONDS = 10 * 60  # on ne retélécharge pas le fichier plus d'une fois toutes les 10 minutes


def parse_feeds(value: str) -> dict[str, str]:
    """Lit ICS_CALENDARS="Nom|https://...,Autre|https://..." -> {"Nom": url, "Autre": url}.

    Sans nom (juste l'URL), l'agenda s'appelle « Agenda 1 », « Agenda 2 »...
    """
    feeds = {}
    for i, item in enumerate(v.strip() for v in value.split(",")):
        if not item:
            continue
        name, _, url = item.rpartition("|")
        feeds[name.strip() or f"Agenda {i + 1}"] = url.strip()
    return feeds


def events_between(calendar: icalendar.Calendar, name: str, start: datetime, end: datetime,
                   tz: ZoneInfo) -> list[dict]:
    """Les événements d'un fichier .ics entre start et end. Fonction pure, testée sans réseau.

    recurring_ical_events déplie les répétitions (« tous les mardis ») en vraies occurrences.
    """
    events = [event_to_dict(e, name, tz) for e in recurring_ical_events.of(calendar).between(start, end)]
    return sorted(events, key=lambda e: e["start"])


class IcsCalendar:
    def __init__(self, feeds: dict[str, str], timezone: ZoneInfo):
        self._feeds = feeds
        self._tz = timezone
        self._cache: dict[str, tuple[float, icalendar.Calendar]] = {}

    @property
    def names(self) -> list[str]:
        return list(self._feeds)

    def list_events(self, start: datetime, end: datetime) -> list[dict]:
        events = []
        for name, url in self._feeds.items():
            try:
                events += events_between(self._download(name, url), name, start, end, self._tz)
            except Exception as e:  # un agenda injoignable ne doit pas empêcher de lire les autres
                log.warning("Agenda « %s » illisible : %s", name, e)
        return sorted(events, key=lambda e: e["start"])

    def list_events_for_days(self, first_day: date, last_day: date) -> list[dict]:
        start = datetime.combine(first_day, time.min, tzinfo=self._tz)
        end = datetime.combine(last_day + timedelta(days=1), time.min, tzinfo=self._tz)
        return self.list_events(start, end)

    def _download(self, name: str, url: str) -> icalendar.Calendar:
        cached = self._cache.get(name)
        if cached and clock.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        with urllib.request.urlopen(url, timeout=20) as response:
            calendar = icalendar.Calendar.from_ical(response.read())
        self._cache[name] = (clock.monotonic(), calendar)
        return calendar
