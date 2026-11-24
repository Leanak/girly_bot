"""Couche intégrations : les services extérieurs (calendrier Apple, Notion).

Chaque intégration est FACULTATIVE : si ses identifiants ne sont pas dans .env,
elle n'est pas créée, ses outils ne sont pas proposés à Claude, et le reste du
bot marche normalement.

Comme le cœur, ces modules ne savent rien de Discord ni de l'IA : ils parlent
seulement à leur service (iCloud, Notion) et renvoient des dict simples.
"""

from girlypop.integrations.apple_calendar import AppleCalendar
from girlypop.integrations.notion import NotionNotes

__all__ = ["AppleCalendar", "NotionNotes"]
