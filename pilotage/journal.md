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
2026-11-24 · dev · 004-banc-rust · variante Rust du banc livrée dans bench/rust/ (rustfft 6.4.1, rayon 1.12.0, FFT sur toute la grille) ; 10 tests verts ; identité au bit près entre 1 et 4 fils ; N=500, Y=100 : 14,3 s à 1 fil, 7,1 s à 4 fils, 58 Mo ; ambiguïtés A1 à A8 de la spec remontées.
2026-11-24 · Claude (orchestrateur) · banc · décidé : précisions techniques P1 à P9 ajoutées à bench/SPEC.md §10 en réponse aux ambiguïtés A1 à A8 (arrondi f32 par étape, réduction par ligne, format, contrôle) · pourquoi : c'est la spec du banc, écrite par l'orchestrateur, et non une question de sens ou de valeur · ce que Pascal peut défaire : chaque précision, la variante Rust les suit déjà.
2026-11-24 · dev · 002-banc-python · variantes py-numpy et py-numba du banc livrées dans bench/python/ ; 39 tests verts ; N=500, Y=100 : py-numpy 21,0 s (1 fil) et 20,6 s (4 fils), py-numba 10,7 s et 7,3 s ; sorties identiques entre 1 et 4 fils ; écart relatif maximal avec Rust 1,4e-12 ; 5 points remontés (négatif par arrondi FFT, compilation numba hors init, ordre des étapes, taille FFT, numpy mono-fil).
2026-11-24 · dev · 003-banc-r · variantes r-base et r-rcpp du banc livrées dans bench/r/ ; 63 tests verts ; N=500, Y=100 : r-base 52,3 s (1 fil), r-rcpp 28,6 s (1 fil) et 24,4 s (4 fils) ; sorties identiques entre 1 et 4 fils ; écart relatif maximal avec Rust 1,4e-12 ; l'aléa, l'arrondi f32, le contrôle et les réductions passent par Rcpp même en r-base ; état stocké en double dans R.
2026-11-24 · relecteur · 002-003-004-banc · relecture croisée : 3 suites vertes (39/63/10), états N=500 identiques au bit près entre les 5 variantes ; à reprendre pour l'équité : FFT Rust complexe non appariée (environ 2 fois le travail de FFT de R et Python, classement numba/Rust à remesurer), mémoire R gonflée (double + Q de toutes les essences à la fois), r-base en partie en C++, ligne de commande R qui corrige ou ignore en silence (graine, --inject-nan), recrutement non testé dans les 3 langages ; 5 amendements de spec à trancher · décision : à Pascal.
2026-11-24 · Pascal · banc · décidé : reprendre les trois implémentations après la relecture croisée et adopter les amendements de la spec (AM1 FFT réelle ou appariée, AM2 domaine de la graine, AM3 codes de sortie communs dont mémoire insuffisante, AM4 résumé de référence partagé) ; machine de référence (B1) : d'abord le PC Linux local de Pascal.
2026-11-24 · Claude (orchestrateur) · 005-banc-mesures · mission de mesure arrêtée avant la fin pour ne pas mesurer du code en cours de reprise ; résultats partiels gardés dans bench/results/ comme mesure « avant reprise » ; l'erreur r-base N=1000 (code 143) vient de l'arrêt (SIGTERM), pas de R. Référence AM4 produite par py-numba, identique au bit près à Rust.
2026-11-24 · dev · 004-banc-rust · reprise : variante Rust corrigée selon AM1 à AM4 (deux essences par FFT complexe, codes 2/3/4, entiers stricts, référence N=16 à écart 0) ; 15 tests verts ; identité au bit près entre 1 et 4 fils ; N=500, Y=100 : 12,0 s à 1 fil, 5,2 s à 4 fils, 62 Mo (mesure prise pendant que les reprises R et Python tournaient) ; résumé inchangé par rapport à la première version.
2026-11-24 · dev · 002-banc-python · reprise (AM1 à AM4) : codes de sortie 2/3/4 en français, entiers stricts et graine dans [0, 2^53), référence partagée N=16 testée, contrôle et ordre P7 testés, FFT sur un seul fil pour garantir par construction l'identité entre 1 et T fils ; 85 tests verts ; sorties N=500 inchangées au bit près ; py-numba à 4 fils : 8,2 s (7,3 s avant, au prix de la garantie).
2026-11-24 · dev · 003-banc-r · reprise (AM1 à AM4) : validation stricte des entiers, codes de sortie 2/3/4, calcul par paire d'essences, 109 tests verts ; N=500, Y=100 : r-base 55,5 s (427 Mo), r-rcpp 31,0 s (280 Mo, 1 fil) et 24,9 s (4 fils) ; summary.csv désormais identique à Rust (écart 0) et entre variantes.
2026-11-24 · Pascal · banc · machine de référence (B1, en partie) : PC Linux de Pascal, i7 à 8 cœurs, environ 3,2 GHz (à vérifier par Pascal) ; mémoire vive et temps maximal pour une SER encore inconnus ; le script de mesure sera lancé par Pascal, ou par Claude quand Pascal est connecté à son PC.
2026-11-24 · Pascal · banc · machine de référence (B1) précisée : Intel Core i7-4940MX à 3,1 GHz, 4 cœurs physiques (8 processeurs logiques avec l'hyperthreading), 31 Go de mémoire vive ; temps maximal pour une SER encore à fixer.
