# Surfaces des sylvoécorégions (SER) — mission 006 (reprise)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-24
- **Source des surfaces :** archive IGN `https://inventaire-forestier.ign.fr/IMG/zip/ts_2021-2025_ser.zip`
  (7 727 917 octets, 86 zip internes, un par SER), fichier interne `TS_2021-2025_<code>_Surface.xlsx`, onglet
  « Territoire ». Page de publication : https://inventaire-forestier.ign.fr/spip.php?rubrique253 (campagnes 2021 à 2025,
  51 tableaux par SER, mise en ligne annoncée le 07/10/2026 ; l'onglet « Lisez-moi » indique un fichier créé le
  07/07/2026, France hexagonale et Corse).
- **Extraction :** faite par l'orchestrateur (`/tmp/claude-0/ser/extraction_ts_2021-2025.csv`), reprise sans
  modification par l'acquéreur, qui n'a pas ouvert les xlsx lui-même (pas de lecteur dans sa session).
- **Statut :** surfaces des 86 SER obtenues. **Les 5 SER d'alluvions (L1 à L5) n'ont pas de surface** : pas de tableau
  dans l'archive.
- Codes et noms : https://inventaire-forestier.ign.fr/spip.php?article773 (86 SER) et
  https://inventaire-forestier.ign.fr/IMG/pdf/GRECO_L.pdf, légende p. 1 (L1 à L5).

## Termes (à ne pas confondre)

- `surface_totale_km2` : ligne « Total » de l'onglet « Territoire », en milliers d'ha, convertie en km²
  (× 1 000 ÷ 100). Résolution de la valeur publiée : 10 km² (un dixième de millier d'ha).
- `surface_boisee_km2` : **superficie forestière** au sens IGN (phrase « La superficie forestière totale est de
  X ± Y ha », convertie en km² = ha ÷ 100). L'IGN la définit dans le fichier ; ce n'est pas une surface « boisée »
  calculée sur une couche géographique. Le nom de la colonne vient du gabarit de mission ; l'intervalle de confiance
  (IC) est dans la colonne `ecart`. Définition exacte de la forêt dans l'onglet : relevée par l'orchestrateur, non
  relue par l'acquéreur.
- `taux_boisement` : en **pour cent**, entier arrondi, tel que publié (« Le taux de boisement est de N % »).
- Millésime : campagnes d'inventaire 2021 à 2025 (moyenne mobile sur cinq ans). Les surfaces totales viennent du
  même tableau, donc de la même géométrie des SER (couche IGN à 1/200 000, données de référence 1985-2002).

## Résumé

| | Plus grande SER | Valeur | Cellules à 10 m | Cellules à 25 m |
|---|---|---|---|---|
| Par surface totale | **C20 « Plateaux calcaires du Nord-Est »** | 29 980 km² | 299 800 000 | 47 968 000 |
| Par superficie forestière | **C20** (la même) | 1 144 000 ha = 11 440 km² (IC ± 38 000 ha) ; taux 38 % | 114 400 000 | 18 304 000 |

- **Calcul simple, non une mesure :** cellules = surface en km² × 10⁶ m² ÷ (côté en m)². À 10 m : 29 980 × 10 000 =
  299 800 000. À 25 m : 29 980 × 1 600 = 47 968 000. Pour la forêt seule : 11 440 × 10 000 = 114 400 000 et
  11 440 × 1 600 = 18 304 000. Cela suppose une grille couvrant toute la SER (ou seulement les cellules forestières,
  pour la ligne « superficie forestière »).
- Seconde par surface totale : F30 « Coteaux de la Garonne », 27 480 km² (274 800 000 cellules à 10 m). Seconde par
  superficie forestière : F21 « Landes de Gascogne », 877 000 ha (8 770 km²), ± 32 000 ha, soit moins que C20 d'environ
  267 000 ha, nettement au-delà des deux IC. En surface totale, F30 et C20 sont proches (écart de 2 500 km²), mais la
  précision de ces valeurs (10 km²) permet de les distinguer ; la marge due à la géométrie à 1/200 000 n'est pas
  quantifiée.
- Ordre de grandeur de l'ADR : la SER moyenne y est d'environ 6 400 km² ; la plus grande est 4,7 fois plus grande
  (299,8 millions de cellules à 10 m contre 64 millions). Le dimensionnement par la moyenne est donc sous-estimé
  d'un facteur d'environ 4,7 pour la plus grande SER en surface totale.
- **Surface de la France métropolitaine :** somme des surfaces totales des 86 SER (tableaux IGN, onglet Territoire,
  somme faite par l'orchestrateur) : **549 390 km²**. À comparer aux « environ 550 000 km² » de l'ADR : concordant.
  Valeurs recueillies par recherche web, non lues à la source : 543 940 km² (cadastre INSEE) et 551 695 km² (IGN,
  laisse de basse mer). La somme reste dans cet intervalle ; la définition du périmètre de l'IGN pour les SER n'est pas
  vérifiée.
- Hypothèse de l'ADR, B2 : les « six SER à plus de 70 % » : l'extraction donne six SER strictement au-dessus de 70 %
  (G70 82 %, D11 76 %, F21 75 %, K11 73 %, H30 71 %, I12 71 %) et une à 70 % (I13). Concordant avec le contradicteur
  (mémentos 2016-2017 lus par moteur de recherche, non lus à la source). Landes de Gascogne : 75 %, concordant.

## Vérification de l'extraction (deux SER au moins, source indépendante)

Les deux sources se trompent pour des raisons différentes : le tableau IGN 2021-2025 vient d'un inventaire par
points (campagnes récentes) ; les fiches SER de 2013 viennent des campagnes de 2006 à 2010, avec un autre mode de
calcul (pourcentage de la surface de forêt de production, hors peupleraies, pour les graphiques).

1. **F21 Landes de Gascogne.** Extraction : 11 650 km², 877 000 ha, 75 %. Contrôle interne : 877 000 ha ÷ 1 165 000 ha
   = 75,3 %, soit le 75 % publié : cohérent. Fiche F21 (2013, p. 2) : forêt à 74 % du Plateau landais, plus d'un
   million d'ha avant les tempêtes de 1999 et 2009, environ 870 000 ha aujourd'hui (pour le plateau) : **870 000 ha
   contre 877 000 ha**, écart de 0,8 %, très inférieur à l'IC (± 32 000 ha) : concordance. La fiche dit aussi que F21
   représente 35 % de la superficie boisée de la GRECO F. L'extraction donne la somme des 12 SER de la GRECO F =
   2 659 000 ha (calcul simple : 54 + 78 + 7 + 57 + 318 + 877 + 119 + 181 + 442 + 321 + 94 + 111 milliers d'ha) et
   F21 = 877 ÷ 2 659 = **33 %** contre 35 % : **écart de 2 points**, attribuable à une autre période (2006-2010 contre
   2021-2025) et à la tempête de 2009 ; non élucidé davantage.
2. **Calcul interne, C20.** 1 144 000 ha ÷ 2 998 000 ha = 38,2 %, soit le 38 % publié : cohérent. Pas de fiche de
   2013 relue pour C20 : pas de seconde source pour cette SER (**le plus grand résultat n'est donc recoupé que
   par la cohérence interne du tableau, et par la somme nationale ci-dessous**).
3. **Somme nationale :** 549 390 km² pour 86 SER contre 543 940 à 551 695 km² selon la source de la superficie du
   territoire (écart de la somme : + 1,0 % par rapport au cadastre INSEE, − 0,4 % par rapport à la valeur IGN ;
   sources secondaires, non lues).
4. Non fait : somme des superficies forestières contre 17,7 Mha (page IGN « La surface forestière », moyenne
   2021-2025) ; cette comparaison serait la meilleure vérification de l'extraction complète. D'autres lignes de
   l'extraction (hors F21, C20) n'ont pas été recoupées avec une fiche.

## Écarts entre sources

- F21 : 33 % de la superficie forestière de la GRECO F (2021-2025) contre 35 % (fiche 2013, campagnes 2006-2010).
- F21 plateau landais : 870 000 ha (fiche 2013) contre 877 000 ha pour toute la SER (2021-2025) : concordant, mais ce
  sont deux périmètres différents (le plateau seul contre la SER).
- Échelle de la couche : 1/200 000 (description) contre 1/50 000 (`spatial_resolution`) dans les métadonnées
  data.gouv.fr du même jeu : non tranché ; ne change pas les surfaces des tableaux IGN.
- Taux national 32 % (IGN, 2021-2025) contre 31 % (mémento 2017, via moteur de recherche).
- Noms identiques pour D11/D12 (« Massif vosgien central ») et F11/F12 (« Terres rouges ») dans la lecture de la page
  IGN : à vérifier dans les fiches `D_11.pdf`, `D_12.pdf`, `F11.pdf`, `F12.pdf`.

## Points non vérifiés

1. Les valeurs des xlsx n'ont pas été relues par l'acquéreur : il dépend de l'extraction de l'orchestrateur. Une seule
   SER (F21) est recoupée avec une source indépendante ; C20 ne l'est que par cohérence interne.
2. Surfaces des 5 SER d'alluvions L1 à L5 : absentes de l'archive. La couche des alluvions n'est qu'un service WMTS
   (data.gouv.fr), donc inutilisable pour un calcul. À calculer par un outil SIG si elles comptent.
3. Définition IGN de la forêt (onglet) et la correspondance avec « boisée » : non relue.
4. Couche vecteur des SER (URL de téléchargement « shape », version, CRS) : non obtenue ; WFS Géoplateforme non
   établi ; cartes.gouv.fr, geodata.inrae.fr, www.ign.fr, insee.fr, observatoire-des-territoires.gouv.fr et
   fr.wikipedia.org sont injoignables (à autoriser dans le réseau de la session).
5. Surface officielle de la France métropolitaine : seule la somme des tableaux est établie.
6. Codes des alluvions dans les tableaux IGN (« L1 » ou autre) ; noms D12 et F12.
7. Le taux de boisement est arrondi à l'entier ; l'IC n'est donné que pour la superficie forestière.

## Trois points au sol

1. **C20 Plateaux calcaires du Nord-Est :** la plus grande SER (29 980 km² ; 1 144 000 ha forestiers, 38 %). Vérifier sur
   la carte IGN que son contour est bien d'un seul tenant et sur quelle étendue (Lorraine, Champagne, Bourgogne :
   hypothèse non vérifiée), et d'où vient le facteur 4,7 par rapport à la moyenne.
2. **F21 Landes de Gascogne et F30 Coteaux de la Garonne :** F21 est boisée à 75 % et 2e en superficie forestière ; F30 est 2e en surface totale (27 480 km², 16 % de boisement).
   Aller voir le front de boisement des Landes (tempêtes de 1999 et 2009, fiche F21) et la limite F21-F30.
3. **Alluvions L1 à L5 :** couche à part, qui recouvre les vallées des autres SER. Ne pas additionner leurs surfaces à
   celles des 86 SER ; vérifier avant de dimensionner la dispersion de graines à la frontière (ADR, B2).

## Liste de contrôle passée

1. Sources et emplacements : cochée pour les 86 SER (archive, fichier interne, onglet « Territoire », date de
   consultation 2026-11-24 ; millésime 2021-2025). Non cochée pour L1 à L5 (aucune surface, signalé). La date du
   fichier est double : « créé le 07/07/2026 » (Lisez-moi) et « mise en ligne 07/10/2026 » (page) : non conciliée.
2. Décomptes : CSV compté avec Grep : **91 lignes de données** (`^[A-L][0-9]+,`) ; **86 SER avec surface** (82 par
   motif simple + 4 noms à virgule entre guillemets : B23, B53, C51, F23) et 5 lignes L1 à L5 vides.
3. Termes : surface totale (km²) distinguée de superficie forestière IGN (ha, convertie en km²), taux en %,
   millésime donné ; limites dites. Non coché : équivalence « forestière » = « boisée ».
4. Statut : dit en tête ; non vérifié : voir la liste ci-dessus.

## Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* Le choix de la résolution (10 ou 25 m) et la tenue en 31 Go
et 5 jours pour la plus grande SER, C20 (ADR 0001, B2).

## Ligne de journal proposée

`2026-11-24 | acquereur | mission 006 (reprise) : surfaces des 86 SER reprises de l'archive IGN ts_2021-2025_ser.zip
(onglet Territoire) ; plus grande SER C20, 29 980 km² (299,8 M cellules à 10 m, 48,0 M à 25 m), aussi la plus grande en
superficie forestière (11 440 km²) ; somme des 86 SER 549 390 km² ; recoupement F21 avec la fiche 2013 ; alluvions
L1-L5 sans surface.`
