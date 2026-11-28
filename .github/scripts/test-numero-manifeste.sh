#!/bin/sh
# Tests de numero-manifeste.sh (mission 090) : étiquette vAAAA.MM.N -> numéro des manifestes, mois 01 à 12.
D="$(cd "$(dirname "$0")" && pwd)"
S="$D/numero-manifeste.sh"
ECHECS=0
verifie() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "ECHEC $1 : attendu '$2', obtenu '$3'"; ECHECS=$((ECHECS+1)); fi; }
refuse() { # nom étiquette
  SORTIE=$("$S" "$2" 2>&1 >/dev/null); CODE=$?
  verifie "refus $1 : code 2" 2 "$CODE"
  case "$SORTIE" in *"étiquette invalide"*) echo "ok   refus $1 : nommé";; *) echo "ECHEC refus $1 : message '$SORTIE'"; ECHECS=$((ECHECS+1));; esac
  verifie "refus $1 : rien sur stdout" "" "$("$S" "$2" 2>/dev/null)"
}
for paire in 01:1 02:2 03:3 04:4 05:5 06:6 07:7 08:8 09:9 10:10 11:11 12:12; do
  verifie "mois ${paire%:*}" "2027.${paire#*:}.3" "$("$S" "v2027.${paire%:*}.3")"
done
verifie "janvier" "2027.1.1" "$("$S" v2027.01.1)"
verifie "octobre (zéro non retiré à tort)" "2026.10.5" "$("$S" v2026.10.5)"
verifie "novembre" "2026.11.19" "$("$S" v2026.11.19)"
verifie "décembre, compteur à deux chiffres" "2026.12.10" "$("$S" v2026.12.10)"
verifie "compteur à trois chiffres" "2026.9.100" "$("$S" v2026.09.100)"
refuse "sans v" 2026.11.19
refuse "mois 00" v2026.00.1
refuse "mois 13" v2026.13.1
refuse "mois à un chiffre" v2026.1.1
refuse "compteur 0" v2026.11.0
refuse "compteur avec zéro en tête" v2026.11.01
refuse "compteur non numérique" v2026.11.x
refuse "suffixe -rc1" v2026.11.5-rc1
refuse "année courte" v26.11.1
refuse "quatre champs" v2026.11.1.2
refuse "vide" ""
if [ "$ECHECS" -eq 0 ]; then echo "Tous les tests passent."; else echo "$ECHECS échec(s)."; exit 1; fi
