"""Tous tes calendriers réunis derrière une seule porte.

L'agent et le scheduler ne veulent pas savoir d'où vient un événement (iCloud,
Google...) : ils parlent à `Calendars`, qui interroge chaque source et fusionne.
C'est le même principe qu'une interface en C++ : plusieurs implémentations,
un seul point d'entrée.

- Lecture : toutes les sources (Apple + agendas iCal comme Google).
- Écriture : seulement le calendrier Apple « Girlypop », s'il est branché.
"""

from datetime import date, datetime, time
from typing import Optional

from girlypop.integrations.apple_calendar import AppleCalendar
from girlypop.integrations.ics_calendar import IcsCalendar


class Calendars:
    def __init__(self, apple: Optional[AppleCalendar] = None, ics: Optional[IcsCalendar] = None):
        self._apple = apple
        self._ics = ics

    @property
    def can_write(self) -> bool:
        return self._apple is not None

    def describe(self) -> str:
        """Pour le log de démarrage : quelles sources sont branchées."""
        parts = (["Apple"] if self._apple else []) + (self._ics.names if self._ics else [])
        return ", ".join(parts)

    def list_events(self, start: datetime, end: datetime) -> list[dict]:
        events = []
        for source in (self._apple, self._ics):
            if source is not None:
                events += source.list_events(start, end)
        return sorted(events, key=lambda e: e["start"])

    def list_events_for_days(self, first_day: date, last_day: date) -> list[dict]:
        events = []
        for source in (self._apple, self._ics):
            if source is not None:
                events += source.list_events_for_days(first_day, last_day)
        return sorted(events, key=lambda e: e["start"])

    def create_event(self, title: str, day: date, start_time: time, duration_minutes: int,
                     description: str = "") -> dict:
        if self._apple is None:
            raise ValueError("Aucun calendrier modifiable : branche le calendrier Apple pour que je puisse écrire")
        return self._apple.create_event(title, day, start_time, duration_minutes, description)
