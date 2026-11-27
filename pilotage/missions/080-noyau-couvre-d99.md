# Mission 080 — le noyau de dispersion couvre la distance à 99 % de chaque essence

## Mission

**En une phrase :** Faire refuser par `simulate` (code 2, message nommé avec l'essence, son d99 et le K demandé) un `kernel_truncation_cells` qui ne couvre pas la distance à 99 % de dispersion de chaque essence présente (décision de Pascal du 27/11/2026).

## L'Homme

- **Agent :** `dev` (Rust) — **Temps de la main :** donner.

## Harnais

- **Peut :** `simulate/src/` (dispersion, contrôles, entrées), `simulate/tests/`, `contracts/` (si `params/regeneration` doit porter d99), `tests/m5/` (fixtures seulement), `docs/adr/0006-niveau-ser.md` (une ligne).
- **Ne doit pas :** inventer un d99 ; changer un résultat quand K couvre déjà le d99 ; casser l'identité entre fils.
- **Câblé :** aucune commande git qui écrit ; vérification sur une copie `git archive HEAD`.

## Tests

- K trop court refusé, nommé ; K suffisant : sorties identiques à avant (octets) ; cargo, contrats et m5 verts, aucun sauté.
