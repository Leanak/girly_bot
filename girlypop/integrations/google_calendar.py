"""Google Agenda via l'API officielle : lecture ET écriture.

Pour écrire dans Google Agenda, un simple lien ne suffit plus : il faut que tu
autorises Girlypop une fois, avec ton compte Google (c'est le protocole OAuth,
le même que « Se connecter avec Google » sur un site).

Les deux fichiers en jeu, tous deux ignorés par git :
- google_credentials.json : la « carte d'identité » de ton appli Girlypop, que tu
  télécharges une fois depuis Google Cloud (voir docs/ROADMAP.md, étape 1 quinquies).
- google_token.json : ton autorisation, créée par `python -m girlypop.google_login`.
  Elle se renouvelle toute seule ; si tu la supprimes, il suffit de relancer la commande.

Comme pour iCloud, ces appels sont bloquants : l'agent et le scheduler les lancent
dans un thread.
"""

import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

log = logging.getLogger(__name__)

# Les droits demandés : lire la liste de tes agendas, lire et créer des événements.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def login(credentials_file: str, token_file: str) -> None:
    """Ouvre ton navigateur pour que tu autorises Girlypop, puis enregistre le jeton.

    À lancer UNE fois, sur ton ordi : `python -m girlypop.google_login`.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow  # utile seulement ici

    flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
    creds = flow.run_local_server(port=0)  # petit serveur local qui reçoit la réponse de Google
    Path(token_file).write_text(creds.to_json())


def event_from_google(item: dict, calendar_name: str, tz: ZoneInfo) -> dict:
    """Un événement de l'API Google -> le même dict que pour Apple. Fonction pure, testée."""
    start, end = item["start"], item["end"]
    all_day = "date" in start
    if all_day:
        start_txt, end_txt = start["date"], end["date"]
    else:
        s = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
        e = datetime.fromisoformat(end["dateTime"]).astimezone(tz)
        start_txt, end_txt = s.strftime("%Y-%m-%d %H:%M"), e.strftime("%Y-%m-%d %H:%M")
    return {
        "title": item.get("summary", "(sans titre)"),
        "start": start_txt,
        "end": end_txt,
        "all_day": all_day,
        "location": item.get("location") or None,
        "calendar": calendar_name,
    }


class GoogleCalendar:
    def __init__(self, token_file: str, timezone: ZoneInfo, write_calendar: str = "primary"):
        if not Path(token_file).exists():
            raise SystemExit(
                f"Google Agenda : {token_file} introuvable. Lance d'abord `python -m girlypop.google_login`."
            )
        self._token_file = token_file
        self._creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        self._tz = timezone
        self._write_calendar = write_calendar  # « primary », un ID d'agenda ou son nom
        self._service = None

    # --- Lecture -------------------------------------------------------------------------

    def list_events(self, start: datetime, end: datetime) -> list[dict]:
        events = []
        for cal in self._calendars():
            # singleEvents=True : Google déplie lui-même les événements répétés.
            items = self._api().events().list(
                calendarId=cal["id"], timeMin=start.isoformat(), timeMax=end.isoformat(),
                singleEvents=True, orderBy="startTime", maxResults=250,
            ).execute().get("items", [])
            events += [event_from_google(i, cal["summary"], self._tz) for i in items if i.get("status") != "cancelled"]
        return sorted(events, key=lambda e: e["start"])

    def list_events_for_days(self, first_day: date, last_day: date) -> list[dict]:
        start = datetime.combine(first_day, time.min, tzinfo=self._tz)
        end = datetime.combine(last_day + timedelta(days=1), time.min, tzinfo=self._tz)
        return self.list_events(start, end)

    # --- Écriture ------------------------------------------------------------------------

    def create_event(self, title: str, day: date, start_time: time, duration_minutes: int,
                     description: str = "") -> dict:
        start = datetime.combine(day, start_time, tzinfo=self._tz)
        end = start + timedelta(minutes=duration_minutes)
        cal_id, cal_name = self._target()
        body = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": str(self._tz)},
            "end": {"dateTime": end.isoformat(), "timeZone": str(self._tz)},
        }
        created = self._api().events().insert(calendarId=cal_id, body=body).execute()
        return {"title": title, "start": start.strftime("%Y-%m-%d %H:%M"), "end": end.strftime("%H:%M"),
                "calendar": cal_name, "link": created.get("htmlLink")}

    # --- Interne -------------------------------------------------------------------------

    def _api(self):
        if not self._creds.valid:
            # Le jeton d'accès dure 1 h : on le renouvelle avec le « refresh token », sans te redemander.
            try:
                self._creds.refresh(Request())
            except RefreshError as e:
                raise RuntimeError(
                    "Autorisation Google expirée : relance `python -m girlypop.google_login` sur l'ordi"
                ) from e
            Path(self._token_file).write_text(self._creds.to_json())
            self._service = None
        if self._service is None:
            self._service = build("calendar", "v3", credentials=self._creds, cache_discovery=False)
        return self._service

    def _calendars(self) -> list[dict]:
        """Les agendas cochés dans Google Agenda (ceux que tu vois d'habitude)."""
        items = self._api().calendarList().list().execute().get("items", [])
        return [c for c in items if c.get("selected")] or items

    def _target(self) -> tuple[str, str]:
        """Trouve l'agenda où écrire, à partir de son ID ou de son nom."""
        wanted = self._write_calendar
        for cal in self._api().calendarList().list().execute().get("items", []):
            if wanted in (cal["id"], cal.get("summary")) or (wanted == "primary" and cal.get("primary")):
                return cal["id"], cal.get("summary", cal["id"])
        raise ValueError(f"Agenda Google « {wanted} » introuvable (vérifie GOOGLE_WRITE_CALENDAR)")
