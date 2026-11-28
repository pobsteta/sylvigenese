# Mission 089 — refuser avant la fusion une PR du produit dont les manifestes ne portent pas la prochaine release

## Mission

**En une phrase :** Qu'une PR vers `main` qui change le produit soit refusée par la CI si les
manifestes ne portent pas le numéro de la prochaine release, pour que la garde de `release.yml`
ne refuse plus l'étiquette après la fusion (décision de Pascal du 28/11/2026 ; suite de la
mission 087, relecture de la PR 19, mineur n° 2).

**Pourquoi :** le 28/11, la PR n° 20 a changé des scripts de `viewer-web` sans lancer
`.github/scripts/aligner-version.sh`. Après la fusion, la release calculée était v2026.11.19 et
les manifestes portaient 2026.11.18 : la garde a refusé l'étiquette, et il a fallu la PR n° 21
pour aligner. Le contrôle doit avoir lieu sur la PR, avant la fusion.

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Ce qui est attendu

1. **Un contrôle sur les PR** dans `.github/workflows/ci.yml` (job ou étape, sur l'événement
   `pull_request` seulement) qui réutilise les scripts existants, sans dupliquer leur logique :
   - si `.github/scripts/release-necessaire.sh` dit qu'aucun fichier du produit ne change par
     rapport à la dernière étiquette, en tenant compte de la tête de la PR : le contrôle passe ;
   - sinon, il calcule le numéro de la prochaine release (`version-calendaire.sh`) et lance
     `verifier-version.sh` avec ce numéro ; en cas d'écart, **échec nommé** en français qui dit
     quel manifeste est en retard et la commande à lancer (`aligner-version.sh`).
   - Le clone doit avoir les étiquettes et l'historique (`fetch-depth: 0`, comme les autres jobs).
2. **Changement de mois** : une PR alignée en novembre et fusionnée en décembre doit être refusée
   à la relance de sa CI ; le dire dans le message (relancer `aligner-version.sh`). Ne rien
   deviner : si le numéro ne peut pas être calculé, échec nommé.
3. **Les deux `package.json`** (`tools/ci/package.json`, `viewer-web/package.json`, aujourd'hui
   `0.0.1`) : les ajouter aux manifestes alignés et vérifiés (`manifestes-version.sh`,
   `aligner-version.sh`, `verifier-version.sh`), et `package-lock.json` qui suit, si c'est
   simple et sans effet sur `npm ci`. Sinon, le dire et laisser `0.0.1`.
4. **README** (section sur la version, mission 087) : dire que la CI refuse désormais la PR, et
   le geste à faire.

## Harnais

- **Peut :** `.github/workflows/ci.yml`, `.github/scripts/` (scripts et leurs tests),
  `tools/ci/package.json` et `package-lock.json`, `viewer-web/package.json` et
  `package-lock.json` (champ `version` seulement), `README.md`.
- **Ne doit pas :** changer `release.yml` (sa garde reste) ; changer un résultat de la chaîne ;
  pousser ; poser une étiquette ; commiter ; toucher à `main`, à `.claude/`, à
  `pilotage/journal.md` ; changer les manifestes au-delà de l'alignement sur le numéro calculé.
- **Câblé :** aucune commande git qui écrit dans le dépôt (essais dans des dépôts temporaires,
  comme `test-aligner-version.sh`).

## Tests

- Tests des scripts dans un dépôt temporaire, au style de `test-aligner-version.sh` et
  `test-release-necessaire.sh` : PR sans fichier du produit → passe ; PR du produit alignée →
  passe ; PR du produit en retard → refus nommé avec la commande ; changement de mois → refus ;
  numéro incalculable → refus nommé.
- `bash .github/scripts/test-*.sh` verts ; `actionlint` ou équivalent si présent, sinon relecture
  du YAML dite ; le job de la CI vu vert sur la PR qui portera la mission.

## Dépend de / rouge attendu jusqu'à

- La PR n° 21 (alignement sur 2026.11.19) doit être fusionnée avant celle de cette mission.
- Aucun rouge attendu.

## Échantillon terrain

- Sur la PR qui porte la mission, Pascal voit le nouveau contrôle vert. Le dev montre, dans un
  dépôt temporaire, le message de refus d'une PR en retard.
