//! Tests du lecteur GeoTIFF (mission 015, spec §9).
//!
//! Les fichiers d'essai sont dans `simulate/tests/fixtures/` (écrits par rasterio et terra,
//! voir `make_fixtures.py` et `make_fixtures_terra.R`), plus le jeu fictif `zone_fictive`.
//! Ordre des axes : x = est, y = nord, EPSG:2154.
//!
//! Valeurs des fichiers d'essai (300 colonnes × 270 lignes, pixel 25 m, coin nord-ouest
//! (700000 ; 6501000)) : Float32 = 1000 b + 0,5 l + 0,25 c ; UInt16 = (7 l + 3 c + 100 b) mod 60000.

use simulate::geotiff::{self, Raster};
use std::path::PathBuf;

fn fixtures() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests").join("fixtures")
}

fn zone_fictive() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("zone_fictive")
        .join("inputs")
}

fn lire_fixture(nom: &str) -> Raster {
    match geotiff::lire(&fixtures().join(nom)) {
        Ok(raster) => raster,
        Err(e) => panic!("{nom} devrait être lu : {e}"),
    }
}

fn attendu_flottant(bande: usize, ligne: usize, colonne: usize) -> f32 {
    1000.0 * bande as f32 + 0.5 * ligne as f32 + 0.25 * colonne as f32
}

/// Vérifie georéférencement, nodata et chaque valeur d'un fichier d'essai Float32.
fn verifier_fichier_flottant(raster: &Raster, bandes: usize) {
    assert_eq!((raster.largeur, raster.hauteur), (300, 270));
    assert_eq!(raster.bandes.len(), bandes);
    assert_eq!((raster.origine_x, raster.origine_y), (700000.0, 6501000.0));
    assert_eq!((raster.pixel_x, raster.pixel_y), (25.0, 25.0));
    assert_eq!(raster.nodata, -9999.0);
    for b in 0..bandes {
        for l in 0..raster.hauteur {
            for c in 0..raster.largeur {
                assert_eq!(raster.valeur(b, l, c), attendu_flottant(b, l, c), "bande {b} ligne {l} colonne {c}");
            }
        }
    }
}

fn refuse(nom: &str) -> String {
    let erreur = match geotiff::lire(&fixtures().join(nom)) {
        Ok(_) => panic!("{nom} devrait être refusé"),
        Err(e) => e,
    };
    assert_eq!(erreur.code, 2, "{nom} : code de sortie 2 attendu, message : {}", erreur.message);
    erreur.message
}

// --- Fichiers acceptés ------------------------------------------------------------------

#[test]
fn rasterio_float32_deflate_deux_bandes() {
    verifier_fichier_flottant(&lire_fixture("rasterio_float32_deflate.tif"), 2);
}

#[test]
fn rasterio_float32_sans_compression() {
    verifier_fichier_flottant(&lire_fixture("rasterio_float32_sans_compression.tif"), 1);
}

#[test]
fn terra_float32_deflate() {
    verifier_fichier_flottant(&lire_fixture("terra_float32_deflate.tif"), 1);
}

#[test]
fn terra_float32_predictor2() {
    verifier_fichier_flottant(&lire_fixture("terra_float32_predictor2.tif"), 1);
}

#[test]
fn rasterio_uint16_predictor2() {
    let raster = lire_fixture("rasterio_uint16_predictor2.tif");
    assert_eq!(raster.nodata, 65535.0);
    for l in 0..raster.hauteur {
        for c in 0..raster.largeur {
            let attendu = ((7 * l + 3 * c) % 60000) as f32;
            assert_eq!(raster.valeur(0, l, c), attendu, "ligne {l} colonne {c}");
        }
    }
}

/// Un point du terrain tombe au bon endroit : le point (707 260 E ; 6 494 495 N) est dans le
/// pixel de colonne 290 et de ligne 260, soit dans la tuile du coin sud-est (bord rempli).
#[test]
fn un_point_du_terrain_tombe_au_bon_endroit() {
    let raster = lire_fixture("rasterio_float32_deflate.tif");
    let (x, y) = (707_260.0_f64, 6_494_495.0_f64);
    let colonne = ((x - raster.origine_x) / raster.pixel_x).floor() as usize;
    let ligne = ((raster.origine_y - y) / raster.pixel_y).floor() as usize;
    assert_eq!((colonne, ligne), (290, 260));
    assert_eq!(raster.valeur(0, ligne, colonne), 0.5 * 260.0 + 0.25 * 290.0);
    assert_eq!(raster.valeur(1, ligne, colonne), 1000.0 + 0.5 * 260.0 + 0.25 * 290.0);
}

// --- Jeu fictif (écrit par rasterio) ----------------------------------------------------

/// Somme et valeurs d'angle de référence calculées avec rasterio (numpy, float64).
fn verifier_zone(nom: &str, largeur: usize, pixel: f64, nodata: f64, bandes: &[(f64, f64, f64)]) {
    let raster = geotiff::lire(&zone_fictive().join(nom)).unwrap_or_else(|e| panic!("{nom} : {e}"));
    assert_eq!((raster.largeur, raster.hauteur), (largeur, largeur), "{nom}");
    assert_eq!((raster.origine_x, raster.origine_y), (700000.0, 6501000.0), "{nom}");
    assert_eq!((raster.pixel_x, raster.pixel_y), (pixel, pixel), "{nom}");
    assert_eq!(raster.nodata, nodata, "{nom}");
    assert_eq!(raster.bandes.len(), bandes.len(), "{nom}");
    for (b, (somme, premier, dernier)) in bandes.iter().enumerate() {
        let valeurs = &raster.bandes[b];
        let somme_lue: f64 = valeurs.iter().map(|v| f64::from(*v)).sum();
        assert!((somme_lue - somme).abs() < 1e-6 * somme.abs().max(1.0), "{nom} bande {b} : somme {somme_lue} au lieu de {somme}");
        assert_eq!(f64::from(valeurs[0]), *premier, "{nom} bande {b} : coin nord-ouest");
        assert_eq!(f64::from(*valeurs.last().unwrap()), *dernier, "{nom} bande {b} : coin sud-est");
    }
}

#[test]
fn zone_fictive_dtm() {
    verifier_zone("dtm.tif", 40, 25.0, -9999.0, &[(554376.160369873, 346.260009765625, 366.260009765625)]);
}

#[test]
fn zone_fictive_chm_plusieurs_tuiles() {
    verifier_zone("chm.tif", 2000, 0.5, -9999.0, &[(52498391.94932613, 9.350000381469727, 0.0)]);
}

#[test]
fn zone_fictive_h_pot_maille_26_6() {
    verifier_zone("h_pot.tif", 38, 26.6, -9999.0, &[(45276.93000411987, 33.65999984741211, 35.529998779296875)]);
}

#[test]
fn zone_fictive_station_type_uint16() {
    verifier_zone("station_type.tif", 50, 20.0, 65535.0, &[(6119.0, 1.0, 4.0)]);
}

#[test]
fn zone_fictive_station_gradients_trois_bandes() {
    verifier_zone(
        "station_gradients.tif",
        50,
        20.0,
        -9999.0,
        &[
            (12423.946980953217, 4.586999893188477, 5.245999813079834),
            (-2425.606001107022, -1.555999994277954, 0.22100000083446503),
            (78.802999940468, 0.5040000081062317, 0.01899999938905239),
        ],
    );
}

// --- Fichiers refusés avec le code 2 ----------------------------------------------------

#[test]
fn refus_gdal_defaut_planarconfig_1() {
    let message = refuse("refus_planar1_gdal_defaut.tif");
    assert!(message.contains("PLANARCONFIG=1"), "{message}");
    assert!(message.contains("INTERLEAVE=BAND"), "{message}");
}

#[test]
fn refus_predictor_3() {
    assert!(refuse("refus_predictor3.tif").contains("PREDICTOR 3"));
}

#[test]
fn refus_bigtiff() {
    assert!(refuse("refus_bigtiff.tif").contains("BigTIFF"));
}

#[test]
fn refus_epsg_4326() {
    assert!(refuse("refus_epsg4326.tif").contains("4326"));
}

#[test]
fn refus_zstd() {
    assert!(refuse("refus_zstd.tif").contains("ZSTD"));
}

#[test]
fn refus_lzw_et_defaut_terra() {
    assert!(refuse("refus_lzw.tif").contains("LZW"));
    assert!(refuse("refus_terra_defaut.tif").contains("LZW"));
}

#[test]
fn refus_bandes_de_lignes() {
    assert!(refuse("refus_bandes_de_lignes.tif").contains("tuiles"));
}

#[test]
fn refus_tuiles_de_128() {
    assert!(refuse("refus_tuiles_128.tif").contains("128"));
}

#[test]
fn refus_float64() {
    assert!(refuse("refus_float64.tif").contains("Float32 ou UInt16"));
}

#[test]
fn refus_fichier_absent_non_tiff_et_tronque() {
    let absent = geotiff::lire(&fixtures().join("n_existe_pas.tif")).unwrap_err();
    assert_eq!(absent.code, 2);

    let non_tiff = geotiff::lire_octets(b"ceci n'est pas un TIFF du tout").unwrap_err();
    assert_eq!(non_tiff.code, 2);

    let complet = std::fs::read(fixtures().join("rasterio_float32_deflate.tif")).unwrap();
    let tronque = geotiff::lire_octets(&complet[..complet.len() / 2]).unwrap_err();
    assert_eq!(tronque.code, 2, "{}", tronque.message);
}

/// Le nodata est obligatoire : sans la balise 42113, refus et non valeur par défaut.
#[test]
fn refus_nodata_absent() {
    let mut octets = std::fs::read(fixtures().join("rasterio_float32_deflate.tif")).unwrap();
    // IFD classique en petit boutiste : 2 octets de nombre d'entrées, puis 12 octets par entrée.
    let debut = u32::from_le_bytes([octets[4], octets[5], octets[6], octets[7]]) as usize;
    let nombre = u16::from_le_bytes([octets[debut], octets[debut + 1]]) as usize;
    let mut trouve = false;
    for i in 0..nombre {
        let p = debut + 2 + 12 * i;
        if u16::from_le_bytes([octets[p], octets[p + 1]]) == 42113 {
            octets[p..p + 2].copy_from_slice(&42999u16.to_le_bytes()); // balise inconnue
            trouve = true;
        }
    }
    assert!(trouve, "le fichier d'essai doit porter la balise 42113");
    let erreur = geotiff::lire_octets(&octets).unwrap_err();
    assert_eq!(erreur.code, 2);
    assert!(erreur.message.contains("nodata"), "{}", erreur.message);
}

// --- Mémoire ----------------------------------------------------------------------------

#[test]
fn memoire_insuffisante_donne_le_code_4() {
    let erreur = geotiff::reserver_f32(usize::MAX / 8).unwrap_err();
    assert_eq!(erreur.code, 4);
    assert!(erreur.message.contains("mémoire insuffisante"));
}

// --- Accord avec le profil --------------------------------------------------------------

/// Les constantes du lecteur sont celles de `contracts/geotiff_profile.json`.
#[test]
fn constantes_conformes_au_profil() {
    let chemin = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("contracts").join("geotiff_profile.json");
    let texte = std::fs::read_to_string(chemin).unwrap();
    // Le JSON est du YAML valide : on réutilise l'analyseur déjà présent.
    let profil: serde_norway::Value = serde_norway::from_str(&texte).unwrap();
    let permis = &profil["allowed"];
    assert_eq!(permis["tile_size"][0].as_u64(), Some(geotiff::TUILE as u64));
    assert_eq!(permis["tile_size"][1].as_u64(), Some(geotiff::TUILE as u64));
    assert_eq!(permis["planar_config"].as_u64(), Some(geotiff::ENTRELACEMENT_ATTENDU));
    assert_eq!(permis["epsg"].as_u64(), Some(geotiff::EPSG_ATTENDU));
    assert_eq!(permis["bigtiff"].as_bool(), Some(false));
    let predicteurs: Vec<u64> = permis["predictor"].as_sequence().unwrap().iter().map(|v| v.as_u64().unwrap()).collect();
    assert_eq!(predicteurs, geotiff::PREDICTEURS.to_vec());
    let compressions = permis["compression"].as_mapping().unwrap();
    let mut codes: Vec<u64> = compressions.keys().map(|k| k.as_str().unwrap().parse().unwrap()).collect();
    codes.sort();
    let mut lus = vec![geotiff::COMPRESSION_AUCUNE];
    lus.extend(geotiff::COMPRESSIONS_DEFLATE);
    lus.sort();
    assert_eq!(codes, lus);
}

// --- Refus qui vont au-delà de la lettre du profil (relecture 1/3) ------------------------

#[test]
fn refus_pixel_point() {
    assert!(refuse("refus_pixel_point.tif").contains("RasterPixelIsPoint"));
}

#[test]
fn refus_georeferencement_par_matrice() {
    assert!(refuse("refus_matrice_34264.tif").contains("34264"));
}

#[test]
fn refus_types_de_bandes_differents() {
    assert!(refuse("refus_types_mixtes.tif").contains("types différents"));
}

/// Position de l'entrée de la balise dans le premier IFD (fichier petit boutiste).
fn position_entree(octets: &[u8], balise: u16) -> usize {
    let debut = u32::from_le_bytes([octets[4], octets[5], octets[6], octets[7]]) as usize;
    let nombre = u16::from_le_bytes([octets[debut], octets[debut + 1]]) as usize;
    for i in 0..nombre {
        let p = debut + 2 + 12 * i;
        if u16::from_le_bytes([octets[p], octets[p + 1]]) == balise {
            return p;
        }
    }
    panic!("balise {balise} absente du fichier d'essai");
}

/// Une tuile creuse (début et taille à 0) a son propre message, et non « corrompu ».
#[test]
fn refus_tuile_creuse() {
    let mut octets = std::fs::read(fixtures().join("rasterio_uint16_predictor2.tif")).unwrap();
    for balise in [324u16, 325u16] {
        let p = position_entree(&octets, balise);
        let tableau = u32::from_le_bytes([octets[p + 8], octets[p + 9], octets[p + 10], octets[p + 11]]) as usize;
        octets[tableau..tableau + 4].copy_from_slice(&0u32.to_le_bytes());
    }
    let erreur = geotiff::lire_octets(&octets).unwrap_err();
    assert_eq!(erreur.code, 2);
    assert!(erreur.message.contains("tuile absente (fichier creux)"), "{}", erreur.message);
}

/// Le nombre de valeurs de la balise 258 doit être celui des bandes.
#[test]
fn refus_bits_et_bandes_incoherents() {
    let mut octets = std::fs::read(fixtures().join("rasterio_float32_deflate.tif")).unwrap();
    let p = position_entree(&octets, 258);
    octets[p + 4..p + 8].copy_from_slice(&1u32.to_le_bytes()); // une seule valeur pour 2 bandes
    let erreur = geotiff::lire_octets(&octets).unwrap_err();
    assert_eq!(erreur.code, 2);
    assert!(erreur.message.contains("balise 258"), "{}", erreur.message);
}
