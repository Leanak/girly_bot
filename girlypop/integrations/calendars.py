"""Tous tes calendriers réunis derrière une seule porte.

L'agent et le scheduler ne veulent pas savoir d'où vient un événement (iCloud,
Google...) : ils parlent à `Calendars`, qui interroge chaque source et fusionne.
C'est le même principe qu'une interface en C++ : plusieurs implémentations,
un seul point d'entrée.

- Lecture : toutes les sources branchées (Apple, Google par l'API, liens iCal).
- Écriture : Google Agenda (par l'API) et/ou le calendrier Apple « Girlypop ».
"""

from datetime import date, datetime, time
from typing import Optional

from girlypop.integrations.apple_calendar import AppleCalendar
from girlypop.integrations.ics_calendar import IcsCalendar


class Calendars:
    def __init__(self, apple: Optional[AppleCalendar] = None, ics: Optional[IcsCalendar] = None,
                 google=None):
        self._readers = [s for s in (apple, google, ics) if s is not None]
        # Les calendriers où elle peut écrire. Le premier de la liste est celui par défaut.
        self.writers = {name: s for name, s in (("google", google), ("apple", apple)) if s is not None}
        self._apple, self._google, self._ics = apple, google, ics

    @property
    def can_write(self) -> bool:
        return bool(self.writers)

    def describe(self) -> str:
        """Pour le log de démarrage : quelles sources sont branchées."""
        writes = f" (écriture : {', '.join(self.writers)})" if self.writers else " (lecture seule)"
        names = (["Apple"] if self._apple else []) + (["Google"] if self._google else [])
        names += self._ics.names if self._ics else []
        return ", ".join(names) + writes

    def list_events(self, start: datetime, end: datetime) -> list[dict]:
        events = []
        for source in self._readers:
            events += source.list_events(start, end)
        return sorted(events, key=lambda e: e["start"])

    def list_events_for_days(self, first_day: date, last_day: date) -> list[dict]:
        events = []
        for source in self._readers:
            events += source.list_events_for_days(first_day, last_day)
        return sorted(events, key=lambda e: e["start"])

    def create_event(self, title: str, day: date, start_time: time, duration_minutes: int,
                     description: str = "", target: Optional[str] = None) -> dict:
        if not self.writers:
            raise ValueError("Aucun calendrier modifiable : branche Google (API) ou Apple pour que je puisse écrire")
        target = target or next(iter(self.writers))
        if target not in self.writers:
            raise ValueError(f"Calendrier « {target} » non branché (disponibles : {', '.join(self.writers)})")
        return self.writers[target].create_event(title, day, start_time, duration_minutes, description)
