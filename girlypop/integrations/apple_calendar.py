"""Le calendrier Apple (iCloud), via le protocole standard CalDAV.

CalDAV, c'est le « langage » que parlent les calendriers entre eux (iCloud, Google,
Nextcloud...). La bibliothèque `caldav` fait les requêtes HTTP pour nous, et
`icalendar` lit le format des événements (.ics).

Connexion : ton identifiant Apple + un MOT DE PASSE D'APPLICATION (pas ton vrai mot de
passe), créé sur appleid.apple.com. Voir docs/ROADMAP.md, étape « Calendrier Apple ».

Règle de prudence : Girlypop LIT tous tes calendriers, mais n'ÉCRIT que dans un
calendrier à elle (« Girlypop » par défaut), créé automatiquement. Tes vrais
calendriers ne sont jamais modifiés.

Attention : ces appels passent par Internet et sont « bloquants » (synchrones).
L'agent et le scheduler les lancent dans un thread à part (asyncio.to_thread)
pour que Discord ne se fige pas pendant ce temps.
"""

import logging
from datetime import date, datetime, time, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

import caldav

log = logging.getLogger(__name__)

ICLOUD_URL = "https://caldav.icloud.com/"


def event_to_dict(component, calendar_name: str, tz: ZoneInfo) -> dict:
    """Transforme un VEVENT (format iCalendar) en dict simple que Claude sait lire.

    Fonction « pure » (pas de réseau) : c'est elle qu'on teste dans tests/.
    """
    start = component.decoded("dtstart")
    end = component.decoded("dtend") if "dtend" in component else None
    # Un événement « toute la journée » a une date sans heure.
    all_day = isinstance(start, date) and not isinstance(start, datetime)
    if all_day:
        end = end or start + timedelta(days=1)
        start_txt, end_txt = start.isoformat(), end.isoformat()
    else:
        start = _local(start, tz)
        end = _local(end, tz) if end else start + timedelta(hours=1)
        start_txt, end_txt = start.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M")
    return {
        "title": str(component.get("summary", "(sans titre)")),
        "start": start_txt,
        "end": end_txt,
        "all_day": all_day,
        "location": str(component.get("location", "")) or None,
        "calendar": calendar_name,
    }


def _local(value: datetime, tz: ZoneInfo) -> datetime:
    """Ramène une heure dans ton fuseau (une heure « flottante », sans fuseau, est supposée locale)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


class AppleCalendar:
    def __init__(
        self,
        username: str,
        app_password: str,
        timezone: ZoneInfo,
        url: str = ICLOUD_URL,
        own_calendar_name: str = "Girlypop",
        read_calendar_names: Iterable[str] = (),
    ):
        self._client = caldav.DAVClient(url=url, username=username, password=app_password)
        self._tz = timezone
        self._own_name = own_calendar_name
        # Vide = on lit tous les calendriers. Sinon, seulement ceux listés (ex : "Perso,Cours").
        self._read_names = {n.strip().lower() for n in read_calendar_names if n.strip()}
        self._principal = None  # connexion ouverte à la première utilisation (pas au démarrage)

    # --- Lecture -------------------------------------------------------------------------

    def list_events(self, start: datetime, end: datetime) -> list[dict]:
        """Tous les événements entre start et end, triés par heure de début."""
        events = []
        for cal in self._calendars():
            name = cal.get_display_name() or "?"
            if self._read_names and name.lower() not in self._read_names and name != self._own_name:
                continue
            # expand=True : déplie les événements récurrents (« tous les lundis ») en occurrences.
            for found in cal.search(start=start, end=end, event=True, expand=True):
                for component in found.icalendar_instance.walk("VEVENT"):
                    events.append(event_to_dict(component, name, self._tz))
        return sorted(events, key=lambda e: e["start"])

    def list_events_for_days(self, first_day: date, last_day: date) -> list[dict]:
        start = datetime.combine(first_day, time.min, tzinfo=self._tz)
        end = datetime.combine(last_day + timedelta(days=1), time.min, tzinfo=self._tz)
        return self.list_events(start, end)

    # --- Écriture (uniquement dans le calendrier Girlypop) -------------------------------

    def create_event(
        self, title: str, day: date, start_time: time, duration_minutes: int, description: str = ""
    ) -> dict:
        start = datetime.combine(day, start_time, tzinfo=self._tz)
        end = start + timedelta(minutes=duration_minutes)
        cal = self._own_calendar()
        cal.add_event(dtstart=start, dtend=end, summary=title, description=description)
        return {"title": title, "start": start.strftime("%Y-%m-%d %H:%M"), "end": end.strftime("%H:%M"),
                "calendar": self._own_name}

    # --- Interne -------------------------------------------------------------------------

    def _calendars(self) -> list:
        if self._principal is None:
            self._principal = self._client.principal()  # 1re requête : vérifie aussi le mot de passe
        return self._principal.calendars()

    def _own_calendar(self):
        for cal in self._calendars():
            if cal.get_display_name() == self._own_name:
                return cal
        log.info("Création du calendrier « %s » sur iCloud", self._own_name)
        return self._principal.make_calendar(name=self._own_name)

