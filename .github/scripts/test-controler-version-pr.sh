#!/bin/sh
# Tests de controler-version-pr.sh (mission 089), le contrôle de la CI sur les PR : dépôt temporaire, manifestes
# factices, étiquettes synthétiques. Les scripts sont copiés hors du dépôt d'essai pour ne pas fausser ses diffs.
# Mois courant UTC partout (c'est celui que lit version-calendaire.sh) ; le changement de mois est simulé par des
# manifestes alignés sur un mois passé.
D="$(cd "$(dirname "$0")" && pwd)"
ECHECS=0
verifie() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "ECHEC $1 : attendu '$2', obtenu '$3'"; ECHECS=$((ECHECS+1)); fi; }
contient() { case "$3" in *"$2"*) echo "ok   $1";; *) echo "ECHEC $1 : '$2' absent de '$3'"; ECHECS=$((ECHECS+1));; esac; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir "$T/scripts" && cp "$D"/aligner-version.sh "$D"/manifestes-version.sh "$D"/release-necessaire.sh \
  "$D"/verifier-version.sh "$D"/version-calendaire.sh "$D"/controler-version-pr.sh "$T/scripts/"
C="$T/scripts/controler-version-pr.sh"
MOIS=$(date -u +%Y.%m)

mkdir "$T/depot" && cd "$T/depot" && git init -q . && git config user.email t@t && git config user.name t
git config commit.gpgsign false; git config tag.gpgsign false
mkdir -p simulate python tools/ci viewer-web R docs
printf '[package]\nname = "simulate"\nversion = "0.0.1"\n' > simulate/Cargo.toml
printf '[[package]]\nname = "simulate"\nversion = "0.0.1"\n' > simulate/Cargo.lock
printf '[project]\nname = "x"\nversion = "0.0.1"\n' > python/pyproject.toml
printf 'Package: x\nVersion: 0.0.1\n' > DESCRIPTION
for p in tools/ci viewer-web; do
  printf '{\n  "name": "x",\n  "version": "0.0.1"\n}\n' > $p/package.json
  printf '{\n  "name": "x",\n  "version": "0.0.1",\n  "packages": {\n    "": {\n      "name": "x",\n      "version": "0.0.1"\n    }\n  }\n}\n' > $p/package-lock.json
done
echo 'a <- 1' > R/a.R; echo 'doc' > docs/a.txt
git add -A && git commit -q -m init && git tag "v$MOIS.1"

# 1. Aucune étiquette dans le clone : refus nommé, rien n'est deviné.
git tag -d "v$MOIS.1" >/dev/null
SORTIE=$("$C" 2>&1); CODE=$?
verifie "sans étiquette : code 1" 1 "$CODE"
contient "sans étiquette : incalculable nommé" "incalculable" "$SORTIE"
contient "sans étiquette : fetch-depth dit" "fetch-depth: 0" "$SORTIE"
git tag "v$MOIS.1"

# 2. PR sans fichier du produit (docs, *.md, test) : passe, même avec des manifestes en retard.
echo 'doc 2' >> docs/a.txt; echo '# n' > NOTE.md; git add -A; git commit -q -m docs
SORTIE=$("$C" 2>&1); CODE=$?
verifie "PR sans produit : code 0" 0 "$CODE"
contient "PR sans produit : dit rien à vérifier" "rien à vérifier" "$SORTIE"

# 3. PR du produit, manifestes en retard : refus nommé, avec la commande.
echo 'a <- 2' > R/a.R; git add -A; git commit -q -m produit
SORTIE=$("$C" 2>&1); CODE=$?
verifie "PR produit en retard : code 1" 1 "$CODE"
contient "PR en retard : numéro attendu" "$MOIS.2" "$SORTIE"
contient "PR en retard : Cargo.toml nommé" "simulate/Cargo.toml porte « 0.0.1 »" "$SORTIE"
contient "PR en retard : DESCRIPTION nommé" "DESCRIPTION porte « 0.0.1 »" "$SORTIE"
contient "PR en retard : package.json de viewer-web nommé" "viewer-web/package.json porte « 0.0.1 »" "$SORTIE"
contient "PR en retard : package-lock de tools/ci nommé" "tools/ci/package-lock.json porte « 0.0.1 »" "$SORTIE"
contient "PR en retard : la commande est dite" ".github/scripts/aligner-version.sh" "$SORTIE"
contient "PR en retard : changement de mois dit" "un mois a changé" "$SORTIE"

# 4. PR du produit alignée : passe.
"$T/scripts/aligner-version.sh" >/dev/null 2>&1; git add -A; git commit -q -m aligne
SORTIE=$("$C" 2>&1); CODE=$?
verifie "PR produit alignée : code 0" 0 "$CODE"
contient "PR alignée : numéro dit" "$MOIS.2" "$SORTIE"

# 5. Changement de mois : alignée sur un mois passé, la relance de la CI refuse.
for f in simulate/Cargo.toml python/pyproject.toml; do sed -i 's/^version = ".*"/version = "2020.01.4"/' $f; done
sed -i 's/^Version: .*/Version: 2020.01.4/' DESCRIPTION
sed -i '/^name = "simulate"$/{n;s/^version = .*/version = "2020.01.4"/;}' simulate/Cargo.lock
for p in tools/ci viewer-web; do sed -i 's/"version": "[^"]*"/"version": "2020.01.4"/' $p/package.json $p/package-lock.json; done
git add -A; git commit -q -m mois
SORTIE=$("$C" 2>&1); CODE=$?
verifie "mois changé : code 1" 1 "$CODE"
contient "mois changé : ancien numéro nommé" "porte « 2020.01.4 »" "$SORTIE"
contient "mois changé : relancer aligner-version.sh" "relancer aligner-version.sh" "$SORTIE"

# 6. Numéro incalculable (version-calendaire.sh en échec) : refus nommé.
printf '#!/bin/sh\necho "boum" >&2; exit 2\n' > "$T/scripts/version-calendaire.sh"
SORTIE=$("$C" 2>&1); CODE=$?
verifie "numéro incalculable : code 1" 1 "$CODE"
contient "numéro incalculable : nommé" "numéro de la prochaine release incalculable" "$SORTIE"

# 7. Hors dépôt git : refus nommé.
cd "$T" && mkdir hors && cd hors
SORTIE=$(GIT_CEILING_DIRECTORIES="$T" "$C" 2>&1); CODE=$?
verifie "hors dépôt : code 1" 1 "$CODE"
contient "hors dépôt : nommé" "pas de dépôt git" "$SORTIE"

if [ "$ECHECS" -eq 0 ]; then echo "Tous les tests passent."; else echo "$ECHECS échec(s)."; exit 1; fi
