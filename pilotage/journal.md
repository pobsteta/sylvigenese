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
2026-11-24 · Claude (orchestrateur) · brief · réponse d'abord de Pascal recopiée mot pour mot en tête de docs/BRIEF.md (pas de docs/brief.md : il entrerait en collision avec BRIEF.md sur un disque insensible à la casse). Premières questions du brief posées.
2026-11-24 · Pascal · brief · cap · simulation à concurrence non spatialisée → simulation spatialisée sur des SER entières · pourquoi : régions SER entières à traiter, rapidité et robustesse primordiales · fait : ADR 0001 (moteur de simulation) proposée par Claude, comparaison Python / R / Rust confiée au contradicteur.
2026-11-24 · contradicteur · brief · critique de l'ADR 0001 rendue (docs/adr/0001-critique-contradicteur.md) : 3 bloquants (pas de cible mesurable ni d'amendement du BRIEF ; ordre de grandeur sous-dimensionné, mémoire limitante, zone tampon absente ; banc sans R et inéquitable sur l'algorithme), 5 importants (TreeMig / LANDIS-II / iLand non examinés, déterminisme en parallèle, GDAL et PROJ inutiles au moteur, contradictions avec les jalons, voisinage IFN non défini) · décision : à Pascal.
2026-11-24 · Pascal · 001-moteurs-existants · décidé : lancer la mission de l'acquereur sur TreeMig, LANDIS-II et iLand avant tout banc d'essai (point I1 de la critique de l'ADR 0001). Points B1, B3 et I4 encore à trancher.
2026-11-24 · acquereur · 001-moteurs-existants · rendu : iLand GPL-3 (lue), LANDIS-II Apache 2.0 (lue), TreeMig CC-BY-NC-SA annoncée (non lue), consignés dans docs/referentiels/moteurs-existants.{md,csv} ; aucune performance à l'échelle SER obtenue ; plusieurs hôtes bloqués par le réseau de la session ; avis : référence de validation plutôt que réutilisation ; décision sur l'option G à Pascal.
2026-11-24 · Pascal · banc · décidé : lancer le banc d'essai à trois langages (Python, R, Rust) au même algorithme, en exploration jetable (point B3 de la critique de l'ADR 0001).
