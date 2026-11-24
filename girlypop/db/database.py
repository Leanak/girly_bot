"""Connexion à la base SQLite.

- `engine` : l'objet qui sait parler au fichier girlypop.db.
- `sessionmaker` : une « usine » à sessions. Une session = une conversation avec la
  base (on lit/écrit, puis on valide avec commit()).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from girlypop.db.models import Base


def init_db(database_url: str) -> sessionmaker[Session]:
    """Ouvre la base, crée les tables si elles n'existent pas, et renvoie l'usine à sessions."""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)  # CREATE TABLE IF NOT EXISTS pour chaque classe de models.py
    # expire_on_commit=False : les objets restent lisibles après commit() (plus simple pour débuter).
    return sessionmaker(engine, expire_on_commit=False)
