//! Générateur à compteur de la spec §2. Toute l'arithmétique est modulo 2^64 :
//! le débordement est voulu ici, donc écrit explicitement avec `wrapping_*`
//! (le profil release garde `overflow-checks = true` pour tout le reste).

const C1: u64 = 0x9E37_79B9_7F4A_7C15;
const C2: u64 = 0xBF58_476D_1CE4_E5B9;
const C3: u64 = 0x94D0_49BB_1331_11EB;

/// `u(seed, year, cell, sp)` dans [0, 1).
#[inline]
pub fn u(seed: u64, year: u64, cell: u64, sp: u64) -> f64 {
    let mut x = seed
        ^ year.wrapping_mul(C1)
        ^ cell.wrapping_mul(C2)
        ^ sp.wrapping_mul(C3);
    x = x.wrapping_add(C1);
    let mut z = (x ^ (x >> 30)).wrapping_mul(C2);
    z = (z ^ (z >> 27)).wrapping_mul(C3);
    z ^= z >> 31;
    (z >> 11) as f64 * (1.0 / 9_007_199_254_740_992.0) // 2^-53
}

#[cfg(test)]
mod tests {
    use super::u;

    #[test]
    fn valeurs_de_reference_spec_2() {
        let cas: [(u64, u64, u64, u64, f64); 6] = [
            (42, 0, 0, 0, 0.7415648787718233),
            (42, 1, 0, 0, 0.1599103928769201),
            (42, 0, 1, 0, 0.14994666025136738),
            (42, 0, 0, 1, 0.5322551776720237),
            (42, 99, 999_999, 7, 0.8685522737309959),
            (7, 3, 123_456, 2, 0.3924761688504701),
        ];
        for (seed, year, cell, sp, attendu) in cas {
            assert_eq!(u(seed, year, cell, sp), attendu, "u({seed},{year},{cell},{sp})");
        }
    }

    #[test]
    fn dans_zero_un() {
        for c in 0..10_000 {
            let v = u(42, 3, c, 5);
            assert!((0.0..1.0).contains(&v));
        }
    }
}
