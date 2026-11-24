# Banc d'essai sylvigenese -- cœur R (SPEC §1 à §8). Jetable.
# Disposition de l'état : matrices ncell x S (colonne s = essence s, cellule c = i*N + j).

PAR <- list(S = 8L, fec = 100.0, alpha = 50.0, Rcells = 16L, k = 0.05, est = 0.01,
            hrec = 3.0, g = 1e-4, Dmax = 1.0e6)
PAR$tol <- 0.5 + 0.25 * (0:7)
PAR$r   <- 0.3 + 0.05 * (0:7)
PAR$m   <- 0.05 + 0.01 * (0:7)

# Compile (ou recharge depuis le cache) src/bench.cpp.
load_cpp <- function(root, cache = Sys.getenv("SYLVI_CACHE", file.path(root, ".cache"))) {
  dir.create(cache, showWarnings = FALSE, recursive = TRUE)
  Rcpp::sourceCpp(file.path(root, "src", "bench.cpp"), env = globalenv(),
                  cacheDir = cache, rebuild = FALSE, verbose = FALSE)
}

fail <- function(msg) {            # arrêt avec message en français, code de sortie 1
  cat(msg, "\n", file = stderr(), sep = "")
  quit(save = "no", status = 1L)
}

# ---- Noyau (§5), f64, somme = 1. Matrice (2R+1)^2 indexée [di+R+1, dj+R+1]. -------------
make_kernel <- function(alpha = PAR$alpha, R = PAR$Rcells) {
  d <- seq.int(-R, R)
  dist <- 25 * sqrt(outer(d^2, d^2, "+"))
  K <- ifelse(dist <= 25 * R, exp(-dist / alpha), 0)
  K / sum(K)
}

# Plus petite taille 2^a 3^b 5^c >= n (stats::fft est efficace sur ces tailles).
next_smooth <- function(n) {
  repeat {
    m <- n
    for (p in c(2, 3, 5)) while (m %% p == 0) m <- m / p
    if (m == 1) return(as.integer(n))
    n <- n + 1
  }
}

# Contexte FFT : remplissage F >= N + R (zéros, pas de repli torique), FFT du noyau.
make_fft_ctx <- function(N, K = make_kernel()) {
  R <- (nrow(K) - 1L) / 2L
  F <- next_smooth(N + R)
  Kp <- matrix(0, F, F)
  idx <- (seq.int(-R, R) %% F) + 1L          # noyau recentré à l'origine (indices modulo F)
  Kp[idx, idx] <- K
  list(N = N, F = F, Kf = fft(Kp))
}

# Dispersion par FFT (§6.2). P : ncell x S. Deux essences par FFT complexe (réelle + imaginaire ;
# le noyau est réel). Le noyau est symétrique, donc matrix(v, N, N) (indexé [j,i]) convient.
disperse_fft <- function(P, ctx) {
  N <- ctx$N; F <- ctx$F; S <- ncol(P); sc <- 1 / (as.double(F) * F)
  Q <- matrix(0, nrow(P), S)
  for (a in seq.int(1L, S, by = 2L)) {
    b <- if (a + 1L <= S) a + 1L else NA_integer_
    Z <- matrix(0 + 0i, F, F)
    Z[1:N, 1:N] <- matrix(complex(real = P[, a], imaginary = if (is.na(b)) 0 else P[, b]), N, N)
    W <- fft(fft(Z) * ctx$Kf, inverse = TRUE)[1:N, 1:N]
    Q[, a] <- as.vector(Re(W)) * sc
    if (!is.na(b)) Q[, b] <- as.vector(Im(W)) * sc
  }
  Q
}

# Convolution directe, pour les tests seulement (jamais utilisée par la simulation).
disperse_direct <- function(P, N, K = make_kernel()) {
  R <- (nrow(K) - 1L) / 2L
  Q <- matrix(0, nrow(P), ncol(P))
  for (s in seq_len(ncol(P))) {
    M <- matrix(P[, s], N, N, byrow = TRUE)           # M[i,j], c = i*N + j
    O <- matrix(0, N, N)
    for (di in -R:R) for (dj in -R:R) {
      w <- K[di + R + 1, dj + R + 1]
      if (w == 0) next
      ii <- max(1, 1 + di):min(N, N + di); jj <- max(1, 1 + dj):min(N, N + dj)
      if (length(ii) && length(jj)) O[ii, jj] <- O[ii, jj] + w * M[ii - di, jj - dj]
    }
    Q[, s] <- as.vector(t(O))
  }
  Q
}

# ---- État initial (§3) -------------------------------------------------------------------
init_state <- function(N, seed) {
  nc <- N * N; S <- PAR$S; cells <- as.numeric(0:(nc - 1))
  forest <- as.integer(u_vec(seed, 0, cells, 100) < 0.7)
  Hmax <- B <- matrix(0, nc, S)
  for (s in 0:(S - 1)) {
    Hmax[, s + 1] <- to_f32(10 + 30 * u_vec(seed, 0, cells, 200 + s))
    B[, s + 1]    <- to_f32(forest * 5 * u_vec(seed, 0, cells, 300 + s))
  }
  list(B = B, D = matrix(0, nc, S), H = matrix(0, nc, S), Hmax = Hmax, forest = forest)
}

# Refus à la lecture (avant le premier pas) d'un Hmax non strictement positif ou non fini.
validate_input <- function(st, N) {
  bad <- which(!is.finite(st$Hmax) | st$Hmax <= 0, arr.ind = FALSE)
  if (length(bad)) {
    p <- bad[1]; nc <- nrow(st$Hmax)
    s <- (p - 1) %/% nc; c <- (p - 1) %% nc
    fail(sprintf(paste0("Entrée invalide : Hmax doit être strictement positif ; Hmax = %s ",
                        "pour l'essence %d, cellule %d (ligne %d, colonne %d). Arrêt avant le premier pas."),
                 format(st$Hmax[p]), s, c, c %/% N, c %% N))
  }
}

# Contrôle du §6.8 : arrêt avec message en français nommant année, cellule, essence.
check_or_stop <- function(st, year, N) {
  v <- check_state(st$B, st$D, st$H, PAR$Dmax)
  if (length(v)) {
    s <- v[1]; c <- v[2]; nm <- c("B", "D", "H")[v[3]]
    what <- switch(v[4], "vaut NaN", sprintf("est négative (%s)", format(v[5])),
                   sprintf("dépasse Dmax = %s (%s)", format(PAR$Dmax), format(v[5])))
    fail(sprintf("Contrôle échoué : %s[essence %d, cellule %d (ligne %d, colonne %d)] %s, année %d. Arrêt.",
                 nm, s, c, c %/% N, c %% N, what, year))
  }
}

# ---- Moyenne 3x3 sur les cellules présentes (étape 3 de r-base) ---------------------------
window3_mean <- function(Bt, cnt) {            # Bt : N x N ; cnt : nombre de cellules présentes
  N <- nrow(Bt); Pd <- matrix(0, N + 2, N + 2); Pd[2:(N + 1), 2:(N + 1)] <- Bt
  tot <- matrix(0, N, N)
  for (a in 0:2) for (b in 0:2) tot <- tot + Pd[(1 + a):(N + a), (1 + b):(N + b)]
  tot / cnt
}
window3_count <- function(N) {
  Pd <- matrix(0, N + 2, N + 2); Pd[2:(N + 1), 2:(N + 1)] <- 1
  tot <- matrix(0, N, N)
  for (a in 0:2) for (b in 0:2) tot <- tot + Pd[(1 + a):(N + a), (1 + b):(N + b)]
  tot
}

# ---- Un pas annuel : variante r-base (R vectorisé) -----------------------------------------
step_base <- function(st, Q, ctx, seed, year) {
  N <- ctx$N; S <- PAR$S; nc <- N * N
  Btot <- st$B[, 1]; for (s in 2:S) Btot <- Btot + st$B[, s]
  Bbar <- window3_mean(matrix(Btot, N, N), ctx$cnt)            # [j,i], fenêtre symétrique
  L <- exp(-PAR$k * as.vector(Bbar))
  cells <- as.numeric(0:(nc - 1))
  for (s in 0:(S - 1)) {
    p <- s + 1L
    d <- to_f32(st$D[, p] + st$forest * PAR$est * Q[, p] * L^PAR$tol[p])        # 4 (P1)
    h <- st$H[, p]; hm <- st$Hmax[, p]
    gr <- d > 0
    h[gr] <- h[gr] + PAR$r[p] * L[gr] * (1 - h[gr] / hm[gr])                    # 5
    over <- !is.na(h) & h > hm; h[over] <- hm[over]                            # P9 : pas de pmin
    h <- to_f32(h)
    d <- to_f32(d * (1 - PAR$m[p] * (0.8 + 0.4 * u_vec(seed, year, cells, s)))) # 6
    b <- st$B[, p]
    rec <- !is.na(h) & h >= PAR$hrec                                            # 7
    b[rec] <- b[rec] + PAR$g * d[rec]; d[rec] <- 0; h[rec] <- 0
    st$B[, p] <- to_f32(b); st$D[, p] <- d; st$H[, p] <- h
  }
  st
}

# ---- Simulation complète. Renvoie l'état final, le tableau summary et les temps. -----------
run_sim <- function(variant, N, years, seed, threads, inject_nan = NA, hmax_zero = FALSE) {
  stopifnot(variant %in% c("r-base", "r-rcpp"))
  if (!is.na(inject_nan) && (inject_nan < 1 || inject_nan > years))
    fail(sprintf("--inject-nan %d est hors de 1 … %d : refusé.", inject_nan, years))
  t0 <- proc.time()[["elapsed"]]
  st <- init_state(N, seed)
  if (hmax_zero) st$Hmax[1, 1] <- 0
  validate_input(st, N)
  K <- make_kernel(); ctx <- make_fft_ctx(N, K)
  if (variant == "r-base") ctx$cnt <- window3_count(N)
  if (variant == "r-rcpp") RcppParallel::setThreadOptions(numThreads = as.integer(threads))
  init_s <- proc.time()[["elapsed"]] - t0

  S <- PAR$S
  summ <- matrix(0, years * S, 5); colnames(summ) <- c("year", "species", "sum_B", "sum_D", "mean_H")
  tl <- proc.time()[["elapsed"]]
  for (year in seq_len(years)) {
    if (!is.na(inject_nan) && year == inject_nan) st$H[1, 1] <- NaN         # H[0,0] = NaN
    Q <- disperse_fft(PAR$fec * st$B, ctx)                                  # 1, 2
    if (variant == "r-base") {
      st <- step_base(st, Q, ctx, seed, year)                               # 3 à 7
    } else {
      step_cells(st$B, st$D, st$H, Q, st$Hmax, st$forest, N, seed, year,
                 PAR$tol, PAR$r, PAR$m, c(PAR$k, PAR$est, PAR$hrec, PAR$g))
    }
    check_or_stop(st, year, N)                                              # 8
    rs <- row_summary(st$B, st$D, st$H, N)                                  # §7
    rows <- (year - 1L) * S + seq_len(S)
    summ[rows, ] <- cbind(year, 0:(S - 1), rs)
  }
  loop_s <- proc.time()[["elapsed"]] - tl
  list(state = st, summary = summ,
       timing = list(init_s = init_s, step_mean_s = loop_s / max(years, 1),
                     total_s = init_s + loop_s))
}

format_summary <- function(summ) {
  c("year,species,sum_B,sum_D,mean_H",
    sprintf("%d,%d,%.16e,%.16e,%.16e", as.integer(summ[, 1]), as.integer(summ[, 2]),
            summ[, 3], summ[, 4], summ[, 5]))
}
