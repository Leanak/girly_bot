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

## Étape 1 bis — Brancher le calendrier Apple
**But : elle planifie autour de tes vrais rendez-vous et te les rappelle.**
1. Il faut la **double authentification** activée sur ton identifiant Apple (c'est le cas par défaut).
2. Va sur <https://account.apple.com> (ou appleid.apple.com) → *Connexion et sécurité* →
   **Mots de passe pour app** → « + » → nomme-le « Girlypop ». Apple affiche un mot de passe du
   type `abcd-efgh-ijkl-mnop` : copie-le tout de suite (il ne sera plus jamais affiché).
3. Dans `.env` :
   ```
   ICLOUD_USERNAME=ton-adresse@icloud.com   # l'e-mail de ton identifiant Apple
   ICLOUD_APP_PASSWORD=abcd-efgh-ijkl-mnop
   ```
   Facultatif : `READ_CALENDARS=Perso,Fac` pour qu'elle ne lise que certains calendriers.
4. Relance le bot. Dans le terminal, tu dois voir `📅 Calendrier Apple : branché`.
   Écris-lui « qu'est-ce que j'ai cette semaine ? ».
5. Quand tu valides un planning, elle peut l'écrire dans un calendrier **« Girlypop »** qu'elle crée
   elle-même : il apparaît sur ton iPhone et tu peux le masquer d'un tap. Elle ne modifie jamais
   tes autres calendriers.

🔒 Ce mot de passe donne accès à ton calendrier, tes contacts et ton iCloud Mail : garde-le dans `.env`
uniquement. Tu peux le révoquer à tout moment depuis la même page Apple.

👉 Ce que tu apprends : CalDAV (un protocole standard), le format iCalendar (.ics), les fuseaux horaires.

## Étape 1 ter — Brancher Notion
**But : elle te prépare des fiches de cours.**
1. Va sur <https://www.notion.so/profile/integrations> → **Nouvelle intégration**. Nom : « Girlypop »,
   type : **Interne**, ton espace de travail. Dans *Capacités*, garde lire, modifier et insérer du contenu.
2. Copie le **Secret** (il commence par `ntn_`) dans `.env` : `NOTION_TOKEN=ntn_...`
3. Dans Notion, crée une page **« 📚 Cours »**. Menu `•••` en haut à droite → **Connexions** →
   ajoute « Girlypop ». Elle ne voit que cette page et ses sous-pages, pas le reste de ton Notion.
4. Copie le lien de cette page (`•••` → *Copier le lien*) dans `.env` : `NOTION_PARENT_PAGE_ID=https://www.notion.so/...`
   (le lien entier marche, elle en extrait l'identifiant).
5. Relance le bot (`📚 Notion : branché`), puis : « fais-moi une fiche sur le potentiel d'action ».

👉 Ce que tu apprends : les API REST, les tokens d'intégration, traduire un format (Markdown) en un autre (blocs Notion).

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
- [x] Mémoire courte : les 10 derniers échanges (et ses rappels automatiques) sont renvoyés à Claude.
  Elle vit en RAM et s'efface au redémarrage.
- La rendre durable : la sauvegarder en base pour survivre aux redémarrages.
- Ajouter une table `notes` pour les préférences durables (« je suis plus efficace le matin »,
  « pas de sport le mercredi »), et un outil pour qu'elle les enregistre elle-même.

## Étape 5 — Des rappels plus vivants
- [x] Messages de motivation écrits par Claude dans la journée (`MOTIVATION_TIMES`).
- [x] « On passe à la suite ? » à la fin de chaque tâche, avec la suivante.
- [x] Rappels des événements du calendrier Apple.
- [x] Bilan du soir avec proposition de report des tâches non faites.
- Boutons Discord sous les rappels : ✅ Fait / ⏰ Reporter de 30 min (les *Views* de discord.py).

## Étape 6 — Héberger Girlypop 24h/24
**But : qu'elle tourne même quand ton ordi est éteint.**
- Écrire un `Dockerfile` et un `docker-compose.yml` (avec un volume pour garder `girlypop.db`).
- Déployer sur un petit serveur (un VPS à quelques euros par mois, ou un Raspberry Pi chez toi).
- Sauvegarder régulièrement le fichier de base de données.

## Étape 7 — Pour aller plus loin (idées)
- Synchroniser avec Google Calendar.
- Prof particulière : lui donner la recherche web de Claude pour citer des sources vérifiées dans les fiches.
- Statistiques de la semaine (temps passé par objectif).
- Mode focus / Pomodoro : « lance 25 minutes de focus » → elle te prévient à la fin.
- Messages vocaux.
