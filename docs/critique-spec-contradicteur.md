# Critique de la spec v1.0 et des ADR 0002 et 0003 (`contradicteur`, 24/11/2026)

Tous les points sont **retenus** par Claude (orchestrateur), par délégation de Pascal. Ils sont
reportés dans `docs/spec.md` v1.1 et dans les ADR.

## Points bloquants

| N° | Objection | Report |
|---|---|---|
| B1 | Le contrat nemeton était inventé : nemeton n'exporte rien, un polygone n'a qu'une essence, et la priorité de l'essence se contredisait. | spec §3 (`nemeton_stands.gpkg` et son export R) et §4 (essence tirée de nemeton, BD Forêt exclue). |
| B2 | tarif-nemeton est inaccessible depuis la CI. | spec §2 (module `import_tarif`), §3 (paramètres synthétiques dans le jeu fictif), §4 (étage B réécrit et cité). |
| B3 | MNT, masque forestier, SER et dates de vol manquaient, et le MNH était rééchantillonné. | spec §3 et §7 (`h0.tif`, MNH jamais rééchantillonné). |
| B4 | Frictionless ne couvre ni les rasters, ni le glTF, ni le JSON. | spec §2 (contrats en trois couches, un validateur en ligne de commande) ; ADR 0002. |
| B5 | La garde IFN contredisait « mêmes variables ». | spec §6 (tableau des deux côtés, limite connue, test de la garde). |

## Points importants

| N° | Objection | Report |
|---|---|---|
| I1 | La courbe de hauteur reprenait la formule synthétique du banc. | spec §5 (Chapman-Richards autonome, provisoire ; erreur si `h_pot` manque). |
| I2 | Certains critères n'étaient pas mesurables dans le conteneur. | spec §11 (M0, M4a, M5a, M6a). |
| I3 | Le profil GeoTIFF n'était pas fermé. | spec §9. |
| I4 | L'aléa et les contrôles du moteur étaient incomplets. | spec §6. |
| I5 | La chaîne 3D web n'était pas vérifiée. | spec §9 et §12 (examen du code d'iTowns dès M0, RAF20). |
| I6 | L'ADR 0003 surévaluait ce qu'elle reprend. | ADR 0003 révisée. |

## Points mineurs

| N° | Objection | Report |
|---|---|---|
| m1 | « Au kilomètre » dans `CLAUDE.md`. | Déjà corrigé avant la critique (700 m, `R/utils.R` de sylvostation). |
| m2 | Statut et crible de l'ADR 0002. | Corrigés. |
| m3 | Nomenclatures. | spec §8. |
| m4 | Lien de la vue web vers la vue massif. | spec §1.5. |

Les sources sont celles du rendu du contradicteur, résumées au journal du 24/11/2026.
