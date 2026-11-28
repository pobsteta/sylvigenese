#!/bin/sh
# Contrôle de la CI sur les pull requests (mission 089, décision de Pascal du 28/11/2026) : une PR qui change
# le produit doit porter, dans les manifestes, le numéro de la prochaine release ; sinon la garde de release.yml
# refuserait l'étiquette après la fusion. Réutilise release-necessaire.sh, version-calendaire.sh et
# verifier-version.sh sans dupliquer leur logique.
# Usage : controler-version-pr.sh   (lancé dans le clone de la PR, étiquettes et historique présents : fetch-depth: 0)
# Code 0 : aucun fichier du produit ne change depuis la dernière étiquette, ou les manifestes sont alignés.
# Le numéro des manifestes se déduit de l'étiquette par numero-manifeste.sh (mois sans zéro en tête, mission 090).
# Code 1 : manifestes en retard (chacun nommé, avec la commande à lancer), ou numéro de release incalculable.
# La tête testée est HEAD (sur GitHub, le commit de fusion de la PR) : la tête de main n'est pas consultée.
set -u
D="$(cd "$(dirname "$0")" && pwd)"

refus() { echo "contrôle de version : refus : $1" >&2; exit 1; }

git rev-parse --git-dir >/dev/null 2>&1 || refus "pas de dépôt git ici : numéro de la prochaine release incalculable."
git rev-parse --verify -q 'HEAD^{commit}' >/dev/null || refus "HEAD introuvable : numéro de la prochaine release incalculable."
if [ -z "$(git tag --list 'v*' | head -n 1)" ]; then
  refus "aucune étiquette v* dans le clone : numéro de la prochaine release incalculable (le clone doit avoir les étiquettes et l'historique : fetch-depth: 0)."
fi

# TETE = HEAD : on ne compare pas à la tête de origin/main (la PR n'en est pas la tête).
DECISION=$("$D/release-necessaire.sh" HEAD "" HEAD)
case "$DECISION" in
  "pas de release"*)
    echo "contrôle de version : rien à vérifier, aucun fichier du produit ne change ($DECISION)"
    exit 0 ;;
esac

TAG=$("$D/version-calendaire.sh" 2>/dev/null) || TAG=""
NUM=$("$D/numero-manifeste.sh" "$TAG" 2>/dev/null) || \
  refus "numéro de la prochaine release incalculable (version-calendaire.sh n'a pas rendu de vAAAA.MM.N : « $TAG »)."

SORTIE=$("$D/verifier-version.sh" "$TAG" 2>&1); CODE=$?
case "$CODE" in
  0)
    echo "contrôle de version : $DECISION ; les manifestes portent déjà le numéro de la prochaine release ($NUM, étiquette $TAG)."
    exit 0 ;;
  1) ;;
  *) refus "la garde verifier-version.sh a échoué pour une autre raison que des manifestes en retard (code $CODE) : $SORTIE" ;;
esac
RETARD=$(printf '%s\n' "$SORTIE" | grep '^  - ')
cat >&2 <<MSG
contrôle de version : refus : cette PR change le produit ($DECISION),
mais les manifestes ne portent pas le numéro de la prochaine release $NUM (étiquette $TAG). Manifestes en retard :
$RETARD
À faire dans la PR : « git fetch --tags », puis
  .github/scripts/aligner-version.sh
et valider le changement. Sans cela, release.yml refuserait de poser l'étiquette après la fusion.
Si la PR était alignée plus tôt, c'est qu'un mois a changé ou qu'une autre release est passée depuis :
relancer aligner-version.sh donne le nouveau numéro.
MSG
exit 1
