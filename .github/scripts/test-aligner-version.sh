#!/bin/sh
# Tests de aligner-version.sh et de la garde verifier-version.sh (mission 087) : dépôt temporaire, manifestes
# factices, étiquettes synthétiques, origin dans un dépôt nu local. Appelé aussi par test-version-calendaire.sh.
D="$(cd "$(dirname "$0")" && pwd)"
A="$D/aligner-version.sh"
G="$D/verifier-version.sh"
ECHECS=0
verifie() { # nom attendu obtenu
  if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "ECHEC $1 : attendu '$2', obtenu '$3'"; ECHECS=$((ECHECS+1)); fi
}
contient() { # nom motif texte
  case "$3" in *"$2"*) echo "ok   $1";; *) echo "ECHEC $1 : '$2' absent de '$3'"; ECHECS=$((ECHECS+1));; esac
}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir "$T/depot" && cd "$T/depot" && git init -q . && git config user.email t@t && git config user.name t
git config commit.gpgsign false; git config tag.gpgsign false
mkdir -p simulate python tools/ci viewer-web
cat > simulate/Cargo.toml <<'F'
[package]
name = "simulate"
version = "0.0.1"
edition = "2021"

[dependencies]
serde = { version = "=1.0.229", features = ["derive"] }
F
cat > simulate/Cargo.lock <<'F'
[[package]]
name = "serde"
version = "1.0.229"

[[package]]
name = "simulate"
version = "0.0.1"
dependencies = [
 "serde",
]
F
cat > python/pyproject.toml <<'F'
[project]
name = "sylvigenese"
version = "0.0.1"

[tool.x]
version = "9.9.9"
F
printf 'Package: sylvigenese\nVersion: 0.0.1\nLicense: GPL-3\n' > DESCRIPTION
# Paquets Node (mission 089) : la version de tête et celle de packages[""] changent, pas celles des dépendances.
for p in tools/ci viewer-web; do
  printf '{\n  "name": "x",\n  "version": "0.0.1",\n  "dependencies": {\n    "dep": "1.0.0"\n  }\n}\n' > $p/package.json
  printf '{\n  "name": "x",\n  "version": "0.0.1",\n  "lockfileVersion": 3,\n  "packages": {\n    "": {\n      "name": "x",\n      "version": "0.0.1",\n      "dependencies": {\n        "dep": "1.0.0"\n      }\n    },\n    "node_modules/dep": {\n      "version": "0.0.1"\n    }\n  }\n}\n' > $p/package-lock.json
done
git add -A && git commit -q -m init
git tag v2026.11.16; git tag v2026.11.17; git tag v2026.10.30

# Garde : manifestes en retard -> refus nommé, code 1.
SORTIE=$("$G" v2026.11.18 2>&1); CODE=$?
verifie "garde : manifestes en retard, code 1" 1 "$CODE"
contient "garde : Cargo.toml nommé" "simulate/Cargo.toml porte « 0.0.1 »" "$SORTIE"
contient "garde : DESCRIPTION nommé" "DESCRIPTION porte « 0.0.1 »" "$SORTIE"
contient "garde : aucune étiquette posée" "aucune étiquette posée" "$SORTIE"
"$G" 2026.11.18 >/dev/null 2>&1; verifie "garde : étiquette sans v, code 2" 2 "$?"
"$G" v2026.11.x >/dev/null 2>&1; verifie "garde : étiquette non numérique, code 2" 2 "$?"
"$G" v2026.13.1 >/dev/null 2>&1; verifie "garde : mois 13, code 2" 2 "$?"
"$G" v2026.00.1 >/dev/null 2>&1; verifie "garde : mois 00, code 2" 2 "$?"

# Alignement sans origin : signalé, sur les étiquettes locales.
SORTIE=$("$A" 2026.11 2>&1); CODE=$?
verifie "aligner : code 0" 0 "$CODE"
contient "aligner : origin illisible signalé" "origin illisible" "$SORTIE"
contient "aligner : numéro calculé" "alignés sur 2026.11.18" "$SORTIE"
verifie "aligner : Cargo.toml" 'version = "2026.11.18"' "$(sed -n 3p simulate/Cargo.toml)"
verifie "aligner : dépendance de Cargo.toml intacte" 'serde = { version = "=1.0.229", features = ["derive"] }' "$(sed -n 7p simulate/Cargo.toml)"
verifie "aligner : Cargo.lock, simulate" 'version = "2026.11.18"' "$(sed -n 7p simulate/Cargo.lock)"
verifie "aligner : Cargo.lock, serde intact" 'version = "1.0.229"' "$(sed -n 3p simulate/Cargo.lock)"
verifie "aligner : pyproject" 'version = "2026.11.18"' "$(sed -n 3p python/pyproject.toml)"
verifie "aligner : pyproject, autre table intacte" 'version = "9.9.9"' "$(sed -n 6p python/pyproject.toml)"
verifie "aligner : DESCRIPTION" 'Version: 2026.11.18' "$(sed -n 2p DESCRIPTION)"
verifie "aligner : package.json de viewer-web" '  "version": "2026.11.18",' "$(sed -n 3p viewer-web/package.json)"
verifie "aligner : package.json, dépendance intacte" '    "dep": "1.0.0"' "$(sed -n 5p viewer-web/package.json)"
verifie "aligner : package-lock de tools/ci, tête" '  "version": "2026.11.18",' "$(sed -n 3p tools/ci/package-lock.json)"
verifie "aligner : package-lock de tools/ci, packages[\"\"]" '      "version": "2026.11.18",' "$(sed -n 8p tools/ci/package-lock.json)"
verifie "aligner : package-lock, version d'une dépendance intacte" '      "version": "0.0.1"' "$(sed -n 14p viewer-web/package-lock.json)"
verifie "aligner : rien d'autre ne bouge" "8" "$(git diff --numstat | wc -l | tr -d ' ')"
AVANT=$(git diff); "$A" 2026.11 >/dev/null 2>&1
verifie "aligner : relancé, même résultat" "$AVANT" "$(git diff)"

# Garde : manifestes alignés -> passe.
"$G" v2026.11.18 >/dev/null 2>&1; verifie "garde : manifestes alignés, code 0" 0 "$?"
# Un seul manifeste en retard -> refus qui nomme celui-là seul.
sed 's/^Version: .*/Version: 2026.11.17/' DESCRIPTION > D.tmp && mv D.tmp DESCRIPTION
SORTIE=$("$G" v2026.11.18 2>&1); CODE=$?
verifie "garde : un manifeste en retard, code 1" 1 "$CODE"
contient "garde : DESCRIPTION en retard nommé" "DESCRIPTION porte « 2026.11.17 »" "$SORTIE"
case "$SORTIE" in *Cargo.toml*) verifie "garde : les autres ne sont pas nommés" non oui;; *) verifie "garde : les autres ne sont pas nommés" oui oui;; esac
# Une PR passée entre-temps : la release calculée est .19, les manifestes disent .18 -> refus.
"$A" 2026.11 >/dev/null 2>&1; git commit -qam aligne; git tag v2026.11.18
"$G" "$("$D/version-calendaire.sh" 2026.11)" >/dev/null 2>&1; verifie "garde : release passée entre-temps, code 1" 1 "$?"
# package-lock dont packages[""] diverge de la tête : refus nommé.
sed '8s/2026.11.18/2026.11.17/' viewer-web/package-lock.json > L.tmp && mv L.tmp viewer-web/package-lock.json
SORTIE=$("$G" v2026.11.18 2>&1); CODE=$?
verifie "garde : package-lock divergent, code 1" 1 "$CODE"
contient "garde : package-lock divergent nommé" "viewer-web/package-lock.json porte « 2026.11.18 / 2026.11.17 »" "$SORTIE"
git checkout -q -- viewer-web/package-lock.json
# Manifeste sans version : alignement refusé, rien n'est écrit.
sed '/^Version:/d' DESCRIPTION > D.tmp && mv D.tmp DESCRIPTION
"$A" 2026.11 >/dev/null 2>&1; verifie "aligner : DESCRIPTION sans version, code 1" 1 "$?"
verifie "aligner : rien n'est écrit sur refus" 'version = "2026.11.18"' "$(sed -n 3p simulate/Cargo.toml)"
SORTIE=$("$G" v2026.11.18 2>&1); CODE=$?
verifie "garde : version illisible, code 1" 1 "$CODE"
contient "garde : version illisible nommée" "DESCRIPTION porte « (version illisible) »" "$SORTIE"
git checkout -q -- DESCRIPTION

# origin en avance sur les étiquettes locales : refus, « git fetch --tags ».
git init -q --bare "$T/origin.git" && git remote add origin "$T/origin.git"
git push -q origin HEAD:refs/heads/main 2>/dev/null; git push -q origin --tags 2>/dev/null
git push -q origin "HEAD:refs/tags/v2026.11.19" 2>/dev/null
SORTIE=$("$A" 2026.11 2>&1); CODE=$?
verifie "aligner : étiquettes locales en retard, code 1" 1 "$CODE"
contient "aligner : dit de faire git fetch --tags" "git fetch --tags" "$SORTIE"
git fetch -q --tags origin
SORTIE=$("$A" 2026.11 2>&1); CODE=$?
verifie "aligner : après fetch, code 0" 0 "$CODE"
contient "aligner : après fetch, numéro suivant" "alignés sur 2026.11.20" "$SORTIE"
case "$SORTIE" in *"origin illisible"*) verifie "aligner : origin lisible, pas de signalement" non oui;; *) verifie "aligner : origin lisible, pas de signalement" oui oui;; esac

# Janvier et octobre (mission 090) : l'étiquette garde le zéro (v2027.01.1), les manifestes non (2027.1.1).
git tag v2027.01.1   # v2026.10.30 existe déjà (début du fichier)
SORTIE=$("$A" 2027.01 2>&1); CODE=$?
verifie "janvier : aligner, code 0" 0 "$CODE"
contient "janvier : numéro sans zéro du mois" "alignés sur 2027.1.2 (prochaine release v2027.01.2)" "$SORTIE"
verifie "janvier : Cargo.toml" 'version = "2027.1.2"' "$(sed -n 3p simulate/Cargo.toml)"
verifie "janvier : DESCRIPTION" 'Version: 2027.1.2' "$(sed -n 2p DESCRIPTION)"
verifie "janvier : package-lock, packages[\"\"]" '      "version": "2027.1.2",' "$(sed -n 8p tools/ci/package-lock.json)"
"$G" v2027.01.2 >/dev/null 2>&1; verifie "janvier : garde passe sur l'étiquette v2027.01.2" 0 "$?"
sed 's/^Version: .*/Version: 2027.01.2/' DESCRIPTION > D.tmp && mv D.tmp DESCRIPTION
SORTIE=$("$G" v2027.01.2 2>&1); CODE=$?
verifie "janvier : manifeste avec le zéro du mois, refusé" 1 "$CODE"
contient "janvier : manifeste avec zéro nommé" "DESCRIPTION porte « 2027.01.2 »" "$SORTIE"
git checkout -q -- DESCRIPTION 2>/dev/null; sed 's/^Version: .*/Version: 2027.1.2/' DESCRIPTION > D.tmp && mv D.tmp DESCRIPTION
SORTIE=$("$A" 2026.10 2>&1); CODE=$?
verifie "octobre : aligner, code 0" 0 "$CODE"
contient "octobre : le zéro final du mois est gardé" "alignés sur 2026.10.31 (prochaine release v2026.10.31)" "$SORTIE"
verifie "octobre : Cargo.toml" 'version = "2026.10.31"' "$(sed -n 3p simulate/Cargo.toml)"
"$G" v2026.10.31 >/dev/null 2>&1; verifie "octobre : garde passe" 0 "$?"

if [ "$ECHECS" -eq 0 ]; then echo "Tous les tests passent."; else echo "$ECHECS échec(s)."; exit 1; fi
