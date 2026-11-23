# Roadmap de Girlypop

Chaque étape produit quelque chose qui **marche** et que tu peux tester sur ton téléphone.
Coche au fur et à mesure.

---

## Étape 0 — Le squelette ✅ (cette pull request)
- [x] Doc d'architecture et roadmap
- [x] Les 5 couches en place : `bot/`, `agent/`, `core/`, `db/`, `scheduler/`
- [x] Tables : objectifs, tâches, sessions d'apprentissage
- [x] Outils pour Claude : objectifs, tâches, planning, parcours d'apprentissage
- [x] Brief du matin, plan de la semaine, rappels
- [x] Tests du cœur sans Discord ni IA

## Étape 1 — Faire tourner le bot sur ton ordi
**But : Girlypop te répond sur Discord.**
1. Créer le bot Discord :
   - Va sur <https://discord.com/developers/applications> → *New Application* → nomme-la « Girlypop ».
   - Onglet **Bot** → *Reset Token* → copie le token dans `.env` (`DISCORD_TOKEN`).
   - Toujours dans **Bot**, active **Message Content Intent** (sinon le bot ne peut pas lire tes messages).
   - Onglet **OAuth2 → URL Generator** : coche `bot`, puis les permissions *Send Messages* et
     *Read Message History*. Ouvre l'URL générée et invite le bot sur un serveur à toi (crée-en un
     vide si besoin : il faut partager un serveur avec le bot pour pouvoir lui écrire en privé).
2. Trouver ton identifiant Discord : *Paramètres → Avancés → Mode développeur*, puis clic droit sur
   ton pseudo → *Copier l'identifiant*. Mets-le dans `DISCORD_OWNER_ID`.
3. Créer une clé API Claude sur <https://platform.claude.com> (*API Keys*), la mettre dans
   `ANTHROPIC_API_KEY`. Ajoute un petit crédit et une limite de dépense mensuelle.
4. `python -m girlypop.main`, puis écris en privé au bot : « Salut ! »

👉 Ce que tu apprends : tokens, intents, variables d'environnement, boucle d'événements.

## Étape 2 — Jouer avec les objectifs et les tâches
**But : comprendre la boucle d'agent en la regardant tourner.**
- Donne-lui tes objectifs, ajoute des tâches, demande « qu'est-ce que j'ai demain ? ».
- Regarde les logs dans le terminal : chaque appel d'outil y est affiché (`🔧 outil: ...`).
- Ouvre `girlypop.db` avec [DB Browser for SQLite](https://sqlitebrowser.org/) pour voir les lignes
  apparaître.
- Exercice : ajoute un outil `delete_task` (une fonction dans `core/tasks.py`, une description dans
  `agent/tools.py`). C'est le meilleur moyen de comprendre comment les couches se parlent.

## Étape 3 — Les parcours d'apprentissage
**But : « neurosciences et crochet » planifiés intelligemment.**
- Demande-lui de te créer un parcours, vérifie les thèmes proposés.
- Améliorer le prompt (`agent/prompts.py`) pour qu'elle adapte la difficulté et la durée.
- Ajouter un outil pour noter une session (« trop facile », « trop dur ») et ajuster la suite.

## Étape 4 — Une mémoire de conversation
**But : qu'elle se souvienne de ce que tu viens de dire.**
- Aujourd'hui chaque message est indépendant. Garder les derniers échanges par jour (en base ou en
  mémoire) et les renvoyer à Claude.
- Ajouter une table `notes` pour les préférences durables (« je suis plus efficace le matin »,
  « pas de sport le mercredi »), et un outil pour qu'elle les enregistre elle-même.

## Étape 5 — Des rappels plus vivants
- Message de motivation personnalisé par Claude (au lieu d'un texte fixe).
- Boutons Discord sous les rappels : ✅ Fait / ⏰ Reporter de 30 min (les *Views* de discord.py).
- Check-in du soir : « Comment s'est passée ta journée ? » et report automatique des tâches non faites.

## Étape 6 — Héberger Girlypop 24h/24
**But : qu'elle tourne même quand ton ordi est éteint.**
- Écrire un `Dockerfile` et un `docker-compose.yml` (avec un volume pour garder `girlypop.db`).
- Déployer sur un petit serveur (un VPS à quelques euros par mois, ou un Raspberry Pi chez toi).
- Sauvegarder régulièrement le fichier de base de données.

## Étape 7 — Pour aller plus loin (idées)
- Synchroniser avec Google Calendar.
- Statistiques de la semaine (temps passé par objectif).
- Mode focus / Pomodoro : « lance 25 minutes de focus » → elle te prévient à la fin.
- Messages vocaux.
