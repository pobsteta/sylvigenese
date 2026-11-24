# Journal de sylvigenese

> **Règle du sommier : on n'efface pas, on ajoute.**
> Chaque inscription est datée et signée (agent ou personne). Une correction est une
> nouvelle ligne qui renvoie à l'ancienne. Un hook refuse toute modification qui
> supprimerait ou réécrirait une inscription existante.
>
> Format : `AAAA-MM-JJ · auteur · mission · ce qui a été fait / décidé / bloqué`
>
> **Le carnet des écarts** (fiche n° 3), en une ligne marquée `écart` :
> `AAAA-MM-JJ · auteur · mission · écart · attendu : … · vu : … · vérifié : comment (ou « non ») · décision : …`
> La décision est l'une des trois : **garder** (vérifié : on adopte), **creuser** (prochain
> essai, daté), **abandonner** (vrai hasard : on le note).
> Règle : on ne sanctionne pas un écart signalé ; on regarde d'abord, on corrige ensuite,
> s'il le faut.
>
> **Les changements de cap** (fiche n° 13), en une ligne marquée `cap`, signée par qui l'a
> décidé : `AAAA-MM-JJ · auteur · mission · cap · ancien → nouveau · pourquoi : … · fait : …`
>
> **La délégation**, en une ligne marquée `délégation`, signée de Pascal :
> `AAAA-MM-JJ · Pascal · — · délégation · portée : … · jusqu'à : … · réservé : …`
> Chaque décision prise par délégation :
> `AAAA-MM-JJ · Claude (orchestrateur, par délégation) · mission · décidé : … · pourquoi : … · ce que Pascal peut défaire : …`

2026-11-24 · Claude (orchestrateur) · — · méthode installée (plugin imperatrice 1.0.0, identique au dépôt pobsteta/methode-imperatrice cloné en lecture) : CLAUDE.md, pilotage/ (equipe, kanban, journal, missions/), docs/adr/. Brief existant gardé tel quel (docs/BRIEF.md), pas de docs/brief.md en doublon. Reste à remplir : « ma réponse d'abord » de Pascal, validation brief et spec (/brief), équipe (/mission), .claude/test-command (stack à trancher), questions ouvertes BRIEF §14.
2026-11-24 · Claude (orchestrateur) · — · à la demande de Pascal : README avec badges (modèle marculus), CI et release automatiques en version calendaire vAAAA.MM.N (scripts repris de marculus, filtre adapté : tests/ ne compte pas), LICENSE GPL-3. Tests des scripts verts en local. Pas encore de .claude/test-command.
