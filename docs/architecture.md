# Architecture : le biome au centre

Le catalogue de biomes relie les calculs à la 3D.

Ce schéma reprend le tableau blanc du projet (état du 24 novembre 2026) : <https://claude.ai/artifact/DKaryvwdnEHPTbxhFXNaRt>. Le lien n'est accessible qu'aux personnes avec qui le tableau a été partagé. En cas d'écart, `BRIEF.md` fait foi : il intègre notamment la décision sur la hauteur (MNH LiDAR HD et potentialité de la station), postérieure au tableau.

```mermaid
flowchart LR
  subgraph R["Calculs R : ce que contient le biome"]
    S["<b>sylvostation</b><br/>Où : types de station, gradients"]
    T["<b>typopeuplement</b><br/>Strate arborée : essences, densité"]
    N["<b>nemeton</b><br/>Détails : bois mort, micro-habitats"]
    L["<b>lidR + LiDAR HD</b><br/>MNT, arbres détectés"]
  end

  subgraph DYN["Dynamique : ce qui nourrit GAMA"]
    IFN["<b>IFN (IGN)</b><br/>Accroissement, mortalité, recrutement"]
    REG["<b>Régénération</b><br/>Semis en cohortes : lumière, sous-bois, gibier"]
  end

  B["<b>Catalogue de biomes</b><br/>Un fichier par biome<br/>station × typopeuplement × stade<br/>Strates : arborée, arbustive, herbacée, sol<br/>Lisible et corrigeable par un forestier"]
  C["<b>Carte des biomes + MNT</b><br/>Quel biome s'applique où"]
  G["<b>GAMA</b><br/>Fait évoluer arbres (D, H, houppier) et biomes,<br/>année après année"]
  TAR["<b>Tarif nemeton</b><br/>Volume, biomasse, carbone par arbre et par an"]

  subgraph V["Moteur 3D : instancie, comme NDunes"]
    IT["<b>iTowns + 3D Tiles</b><br/>SER → France, sur le web"]
    GD["<b>Godot 4</b><br/>Massif → petite plante"]
    GEN["<b>Générateur tarif-nemeton</b><br/>Arbres 3D par modèle architectural (Hallé)"]
  end

  S --> B
  T --> B
  N --> B
  L --> C
  B --> C
  B <--> G
  IFN --> G
  REG --> G
  G --> TAR
  B --> IT
  C --> GD
```

## Lecture

| Bloc | Rôle |
|---|---|
| Calculs R | disent ce que contient un biome et où il s'applique |
| Catalogue de biomes | contrat entre les calculs et la 3D |
| Dynamique | alimente la simulation : accroissement, mortalité, recrutement, régénération |
| GAMA | fait évoluer arbres et biomes |
| Tarif nemeton | convertit chaque arbre simulé en volume, biomasse et carbone |
| Moteur 3D | n'invente rien : il instancie ce que décrit le biome |

Le prototype de la vue massif est dans `viewer-massif/`.
