# Équipe de sylvigenese

> Produit par l'orchestrateur avec `/imperatrice:mission`, **validé par Pascal** avant
> tout démarrage. Règle de staffing : un agent par mission qui passe les trois
> questions, jamais un agent « par principe ».

- **Statut :** validée pour le jalon M0, par délégation de Pascal (2026-11-24)
- **Validée par :** Claude (orchestrateur, par délégation de Pascal), journal du 2026-11-24

## Plafond humain

- **PR ouvertes en même temps, au plus :** 3
- **Rythme de relecture de Pascal :** par délégation, c'est l'orchestrateur qui relit, puis le
  `relecteur`. Pascal relit quand il le veut.
- **Contrainte de l'environnement :** une seule branche de travail
  (`claude/youthful-allen-b094t9`), donc une PR par jalon. Les missions travaillent dans des
  dossiers disjoints et c'est l'orchestrateur qui intègre.

## Délégation

> Ce que Pascal demande à l'orchestrateur de trancher à sa place (skill `methode`,
> « La délégation »).

- **Parole de Pascal (24/11/2026), recopiée mot pour mot :** « Je valide tes choix et
  choisis ce qu'il y a de mieux jusqu'à obtenir une première version de la plateforme à ma
  place ».
- **Portée :** toutes les décisions nécessaires pour obtenir une première version (v1) de
  sylvigenese, telle que la décrit `docs/BRIEF.md` :
  - les arbitrages du brief et de la critique du contradicteur ;
  - la spec et les ADR ;
  - l'équipe et les missions ;
  - la relecture des PR.

  Correction du 2026-11-24 (journal) : la **fusion vers `main` reste à Pascal**. Elle
  déclenche une release publique automatique, ce qui touche l'extérieur (skill `boucle`,
  étape 5).
- **Parole de Pascal (25/11/2026), recopiée mot pour mot :** « Fusionne et continue. Valide les
  jalons sans mon autorisation ». Extension de la portée : la **validation des jalons** (critères
  a, sur le jeu fictif) et la **fusion vers `main`** de leurs PR, release publique automatique
  comprise, passent à l'orchestrateur, avec la CI verte et la relecture du `relecteur` comme
  conditions. La correction du 2026-11-24 sur la fusion est levée par cette parole.
- **Jusqu'à :** la v1, c'est-à-dire les jalons M0 à M6 du BRIEF §11 remplis, ou le premier
  retour de Pascal qui la reprend ou la restreint.
- **Réservé à Pascal :**
  - sa réponse d'abord ;
  - rendre la main ;
  - ce qui touche l'extérieur et ne se défait pas : publication hors du dépôt, contact avec
    des tiers, dépense, partage, élargissement du réseau ou des accès de l'environnement ;
  - le lancement du banc sur son PC.
- **Inscrite au journal le :** 2026-11-24.

## Le vivier (catalogue, pas une équipe)

| Agent | A / plan | Modèle | Écrit du code ? |
|---|---|---|---|
| `contradicteur` | Abstraction · Polos | opus | non |
| `acquereur` | Acquisition · Ponos | sonnet | non (référentiels et données) |
| `archiviste` | Archivage · Pontos | sonnet | non (docs) |
| `analyste` | Analyse · Ponos | sonnet | non |
| `afficheur` | Affichage · Ponos | sonnet | oui (interface) |
| `dev` | réalisation · Ponos | sonnet | oui |
| `testeur` | réalisation · Ponos | sonnet | oui (tests) |
| `relecteur` | contrôle · C3 | opus | non (lecture seule) |

## Missions

| Mission | Agent | Modèle | Temps de la main | Les 3 questions | Cycle |
|---|---|---|---|---|---|
| [009-contrats](missions/009-contrats.md) | `dev` | opus | prendre | 3 oui | M0 |
| [010-tests-contrats](missions/010-tests-contrats.md) | `testeur` | sonnet | donner | 3 oui | M0 |
| [011-table-essences](missions/011-table-essences.md) | `acquereur` | sonnet | donner | 3 oui | M0 |
| [012-squelette](missions/012-squelette.md) | `dev` | sonnet | donner | 3 oui | M0 |
| [013-jeu-fictif](missions/013-jeu-fictif.md) | `dev` | sonnet | donner | 3 oui | M0 |
| [014-ci](missions/014-ci.md) | `dev` | sonnet | donner | 3 oui | M0 |
| [015-lecteur-geotiff-rust](missions/015-lecteur-geotiff-rust.md) | `dev` | sonnet | donner | 3 oui | M0 |
| [016-referentiels-m0](missions/016-referentiels-m0.md) | `acquereur` | sonnet | donner | 3 oui | M0 |
| [017-prepare-grille](missions/017-prepare-grille.md) | `dev` | sonnet | donner | 3 oui | M1 |
| [018-prepare-arbres](missions/018-prepare-arbres.md) | `dev` | sonnet | donner | 3 oui | M1 |
| [019-prepare-ifn](missions/019-prepare-ifn.md) | `dev` | sonnet | donner | 3 oui | M1 |
| [020-biomes](missions/020-biomes.md) | `dev` | sonnet | donner | 3 oui | M1 |
| [021-tests-m1](missions/021-tests-m1.md) | `testeur` | sonnet | donner | 3 oui | M1 |
| [022-referentiel-ifn-dynamique](missions/022-referentiel-ifn-dynamique.md) | `acquereur` | sonnet | donner | 3 oui | M2a |
| [023-ifn-dynamique-contrats-fictif](missions/023-ifn-dynamique-contrats-fictif.md) | `dev` | sonnet | donner | 3 oui après 022 | M2a |
| [024-station-aux-placettes](missions/024-station-aux-placettes.md) | `dev` | opus | donner | 3 oui après 022 et 023 | M2a |
| [025-dynamics](missions/025-dynamics.md) | `dev` | opus | prendre (plan d'abord) | non à la 2e : plan d'abord | M2a |
| [026-tests-m2](missions/026-tests-m2.md) | `testeur` | sonnet | donner | 3 oui après 022 | M2a |
| [027-dettes-m1a](missions/027-dettes-m1a.md) | `dev` | sonnet | donner | 3 oui | M2a |
| [028-assets-etat-initial](missions/028-assets-etat-initial.md) | `dev` | sonnet | donner | 3 oui | M4a (état initial) |
| [029-viewer-web-etat-initial](missions/029-viewer-web-etat-initial.md) | `afficheur` | sonnet | donner | 3 oui après 028 | M4a (état initial) |
| [030-tests-m4-etat-initial](missions/030-tests-m4-etat-initial.md) | `testeur` | sonnet | donner | 3 oui | M4a (état initial) |
