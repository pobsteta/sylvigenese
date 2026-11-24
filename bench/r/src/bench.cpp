// [[Rcpp::depends(RcppParallel)]]
// Banc d'essai sylvigenese : partie C++ (Rcpp).
//  - u_vec, to_f32, check_state, row_summary : utilisées par r-base ET r-rcpp ;
//  - step_cells : cœur par cellule, utilisé par r-rcpp seulement.
// Disposition : matrice ncell x S en colonnes (R), donc X[s*ncell + c], soit [s][i][j]
// avec c = i*N + j (SPEC §1).
#include <Rcpp.h>
#include <RcppParallel.h>
#include <cmath>
#include <cstdint>
#include <vector>
using namespace Rcpp;

static inline double u_one(uint64_t seed, uint64_t year, uint64_t cell, uint64_t sp) {
  uint64_t x = seed ^ (year * 0x9E3779B97F4A7C15ULL) ^ (cell * 0xBF58476D1CE4E5B9ULL) ^
               (sp * 0x94D049BB133111EBULL);
  x += 0x9E3779B97F4A7C15ULL;
  uint64_t z = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
  z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
  z = z ^ (z >> 31);
  return (double)(z >> 11) * 1.1102230246251565e-16;  // 2^-53
}

// [[Rcpp::export]]
NumericVector u_vec(double seed, double year, NumericVector cells, double sp) {
  uint64_t sd = (uint64_t)seed, yr = (uint64_t)year, s = (uint64_t)sp;
  R_xlen_t n = cells.size();
  NumericVector out(n);
  for (R_xlen_t i = 0; i < n; i++) out[i] = u_one(sd, yr, (uint64_t)cells[i], s);
  return out;
}

// [[Rcpp::export]]
NumericVector to_f32(NumericVector x) {
  R_xlen_t n = x.size();
  NumericVector out(n);
  for (R_xlen_t i = 0; i < n; i++) out[i] = (double)(float)x[i];
  return out;
}

// Premier écart du §6.8, parcours essence puis cellule. Renvoie numeric(0) si tout va bien,
// sinon c(s, c, var(1=B,2=D,3=H), nature(1=NaN,2=négative,3=D>Dmax), valeur).
// [[Rcpp::export]]
NumericVector check_state(NumericMatrix B, NumericMatrix D, NumericMatrix H, double Dmax) {
  int nc = B.nrow(), S = B.ncol();
  const NumericMatrix* arr[3] = {&B, &D, &H};
  for (int s = 0; s < S; s++)
    for (int c = 0; c < nc; c++)
      for (int v = 0; v < 3; v++) {
        double x = (*arr[v])(c, s);
        if (std::isnan(x)) return NumericVector::create(s, c, v + 1, 1, x);
        if (x < 0) return NumericVector::create(s, c, v + 1, 2, x);
        if (v == 1 && x > Dmax) return NumericVector::create(s, c, v + 1, 3, x);
      }
  return NumericVector(0);
}

// Réductions du §7 : somme par ligne de grille (j croissant), puis somme des lignes (i croissant),
// en f64 ; mean_H sur les cellules où D > 0. Renvoie une matrice S x 3 (sum_B, sum_D, mean_H).
// [[Rcpp::export]]
NumericMatrix row_summary(NumericMatrix B, NumericMatrix D, NumericMatrix H, int N) {
  int S = B.ncol();
  NumericMatrix out(S, 3);
  for (int s = 0; s < S; s++) {
    double tb = 0, td = 0, th = 0, tn = 0;
    for (int i = 0; i < N; i++) {
      double rb = 0, rd = 0, rh = 0, rn = 0;
      for (int j = 0; j < N; j++) {
        int c = i * N + j;
        rb += B(c, s);
        rd += D(c, s);
        if (D(c, s) > 0) { rh += H(c, s); rn += 1; }
      }
      tb += rb; td += rd; th += rh; tn += rn;
    }
    out(s, 0) = tb; out(s, 1) = td; out(s, 2) = (tn > 0) ? th / tn : 0.0;
  }
  return out;
}

static inline double f32(double x) { return (double)(float)x; }

struct BtotWorker : public RcppParallel::Worker {
  const double* B; double* Btot; int nc, S;
  void operator()(std::size_t b, std::size_t e) {
    for (std::size_t c = b; c < e; c++) {
      double t = 0;
      for (int s = 0; s < S; s++) t += B[(std::size_t)s * nc + c];
      Btot[c] = t;
    }
  }
};

struct CellWorker : public RcppParallel::Worker {
  double *B, *D, *H; const double *Q, *Hmax, *Btot;
  const int* forest; int N, nc, S; uint64_t seed, year;
  const double *tol, *r, *m; double k, est, hrec, g;
  void operator()(std::size_t b, std::size_t e) {
    for (std::size_t c = b; c < e; c++) {
      int i = (int)(c / N), j = (int)(c % N);
      // 3x3 : moyenne sur les cellules présentes
      double sum = 0; int cnt = 0;
      for (int a = -1; a <= 1; a++) {
        int ii = i + a; if (ii < 0 || ii >= N) continue;
        for (int bb = -1; bb <= 1; bb++) {
          int jj = j + bb; if (jj < 0 || jj >= N) continue;
          sum += Btot[(std::size_t)ii * N + jj]; cnt++;
        }
      }
      double L = std::exp(-k * (sum / cnt));
      for (int s = 0; s < S; s++) {
        std::size_t p = (std::size_t)s * nc + c;
        // P1 : arrondi f32 à la fin de chaque étape 4, 5, 6, 7
        double d = f32(D[p] + forest[c] * est * Q[p] * std::pow(L, tol[s]));      // 4
        double h = H[p], hm = Hmax[p];
        if (d > 0) h += r[s] * L * (1.0 - h / hm);                                // 5
        if (h > hm) h = hm;                                                       // P9
        h = f32(h);
        d = f32(d * (1.0 - m[s] * (0.8 + 0.4 * u_one(seed, year, c, s))));        // 6
        double bv = B[p];
        if (h >= hrec) { bv = f32(bv + g * d); d = 0; h = 0; }                    // 7
        B[p] = bv; D[p] = d; H[p] = h;
      }
    }
  }
};

// Étapes 3 à 7, en place sur B, D, H (état arrondi en f32 en fin de pas).
// [[Rcpp::export]]
void step_cells(NumericMatrix B, NumericMatrix D, NumericMatrix H, NumericMatrix Q,
                NumericMatrix Hmax, IntegerVector forest, int N, double seed, double year,
                NumericVector tol, NumericVector r, NumericVector m, NumericVector par) {
  int nc = B.nrow(), S = B.ncol();
  std::vector<double> Btot(nc);
  BtotWorker w1; w1.B = B.begin(); w1.Btot = Btot.data(); w1.nc = nc; w1.S = S;
  RcppParallel::parallelFor(0, nc, w1, 4096);
  CellWorker w2;
  w2.B = B.begin(); w2.D = D.begin(); w2.H = H.begin(); w2.Q = Q.begin(); w2.Hmax = Hmax.begin();
  w2.Btot = Btot.data(); w2.forest = forest.begin(); w2.N = N; w2.nc = nc; w2.S = S;
  w2.seed = (uint64_t)seed; w2.year = (uint64_t)year;
  w2.tol = tol.begin(); w2.r = r.begin(); w2.m = m.begin();
  w2.k = par[0]; w2.est = par[1]; w2.hrec = par[2]; w2.g = par[3];
  RcppParallel::parallelFor(0, nc, w2, 1024);
}
