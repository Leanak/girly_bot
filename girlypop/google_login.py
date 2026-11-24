"""Connexion à Google Agenda, à faire UNE fois : `python -m girlypop.google_login`.

Ton navigateur s'ouvre, tu choisis ton compte Google et tu acceptes. Le jeton est
enregistré dans google_token.json (ignoré par git), et le bot l'utilise ensuite tout seul.
"""

import os

from dotenv import load_dotenv

from girlypop.integrations.google_calendar import login


def main() -> None:
    load_dotenv()
    credentials = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
    token = os.getenv("GOOGLE_TOKEN_FILE", "google_token.json")
    if not os.path.exists(credentials):
        raise SystemExit(f"{credentials} introuvable : télécharge-le depuis Google Cloud (docs/ROADMAP.md).")
    print("🌐 Ton navigateur va s'ouvrir : choisis ton compte Google et accepte.")
    login(credentials, token)
    print(f"✅ C'est bon ! Autorisation enregistrée dans {token}. Tu peux lancer le bot.")


if __name__ == "__main__":
    main()
