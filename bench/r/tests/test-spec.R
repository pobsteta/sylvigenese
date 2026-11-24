test_that("§2 : valeurs de référence de l'aléa (u_vec)", {
  ref <- list(c(42, 0, 0, 0, 0.7415648787718233), c(42, 1, 0, 0, 0.1599103928769201),
              c(42, 0, 1, 0, 0.14994666025136738), c(42, 0, 0, 1, 0.5322551776720237),
              c(42, 99, 999999, 7, 0.8685522737309959), c(7, 3, 123456, 2, 0.3924761688504701))
  for (r in ref) expect_equal(u_vec(r[1], r[2], r[3], r[4]), r[5], tolerance = 1e-15)
  # vectorisé : même résultat que cellule par cellule
  v <- u_vec(42, 5, c(0, 10, 999999), 3)
  expect_identical(v, c(u_vec(42, 5, 0, 3), u_vec(42, 5, 10, 3), u_vec(42, 5, 999999, 3)))
  expect_true(all(v >= 0 & v < 1))
})

test_that("§5 : noyau normalisé (somme = 1 à 1e-12), tronqué, symétrique", {
  K <- make_kernel()
  expect_lt(abs(sum(K) - 1), 1e-12)
  expect_equal(dim(K), c(33L, 33L))
  expect_equal(K[1, 1], 0)                    # coin : d = 25*16*sqrt(2) > 400
  expect_gt(K[1, 17], 0)                      # d = 400 exactement : retenu
  expect_equal(K, t(K)); expect_equal(K, K[33:1, 33:1])
  expect_true(all(K[17, ] == rev(K[17, ])))
})

test_that("§6.2 : la FFT égale la convolution directe (écart relatif < 1e-9)", {
  N <- 24; set.seed(1)
  P <- matrix(runif(N * N * 3) * 500, N * N, 3)
  ctx <- make_fft_ctx(N)
  expect_gte(ctx$F, N + 16)                   # remplissage d'au moins 16 cellules
  Qf <- disperse_fft(P, ctx); Qd <- disperse_direct(P, N)
  expect_lt(max(abs(Qf - Qd) / max(abs(Qd))), 1e-9)
  # une source ponctuelle au coin retombe au bon endroit (pas de repli torique)
  P1 <- matrix(0, N * N, 2); P1[1, 1] <- 1       # cellule (0,0)
  Q1 <- disperse_fft(P1, ctx)
  K <- make_kernel()
  expect_equal(Q1[1, 1], K[17, 17], tolerance = 1e-12)             # la cellule elle-même
  expect_equal(Q1[0 * N + 5 + 1, 1], K[17, 17 + 5], tolerance = 1e-9)  # (0,5)
  expect_equal(Q1[N * 1 + 0 + 1, 1], K[17 + 1, 17], tolerance = 1e-9)  # (1,0)
  expect_equal(Q1[0 * N + (N - 1) + 1, 1], 0, tolerance = 1e-12)  # (0,23) : hors portée
  expect_equal(Q1[, 2], rep(0, N * N), tolerance = 1e-14)          # l'autre essence reste nulle
})

test_that("taille de remplissage FFT : 2^a 3^b 5^c >= N + 16", {
  expect_equal(next_smooth(516), 540L)
  expect_equal(next_smooth(1016), 1024L)
  expect_equal(make_fft_ctx(500)$F, 540L)
})

test_that("§3 : état initial reproductible", {
  a <- init_state(10, 42); b <- init_state(10, 42)
  expect_identical(a, b)
  expect_equal(a$forest[1], as.integer(u_vec(42, 0, 0, 100) < 0.7))
  expect_equal(a$Hmax[1, 3], as.double(as.single(10 + 30 * u_vec(42, 0, 0, 202))))
  expect_true(all(a$B[a$forest == 0, ] == 0))
})

test_that("§6.8 et §7 : arrêt avec message sur --inject-nan et --hmax-zero", {
  r <- run_cli("--variant", "r-base", "--n", "20", "--years", "4", "--inject-nan", "2",
               "--out", tempfile())
  expect_equal(r$status, 1L)
  expect_match(r$stderr, "année 2"); expect_match(r$stderr, "cellule 0"); expect_match(r$stderr, "essence 0")
  r <- run_cli("--variant", "r-rcpp", "--n", "20", "--years", "4", "--inject-nan", "2",
               "--out", tempfile())
  expect_equal(r$status, 1L); expect_match(r$stderr, "année 2")
  for (v in c("r-base", "r-rcpp")) {
    o <- tempfile()
    r <- run_cli("--variant", v, "--n", "20", "--years", "4", "--hmax-zero", "--out", o)
    expect_equal(r$status, 1L); expect_match(r$stderr, "avant le premier pas")
    expect_false(file.exists(file.path(o, "summary.csv")))   # refusé avant tout pas
  }
})

test_that("§6.8 : valeur négative et D > Dmax détectées (check_state)", {
  z <- matrix(0, 4, 8)
  expect_length(check_state(z, z, z, 1e6), 0)
  D <- z; D[3, 5] <- 2e6
  v <- check_state(z, D, z, 1e6); expect_equal(v[1:4], c(4, 2, 2, 3))   # s=4, c=2, var D, > Dmax
  B <- z; B[2, 1] <- -1; v <- check_state(B, z, z, 1e6); expect_equal(v[c(1, 2, 3, 4)], c(0, 1, 1, 2))
})

test_that("§7 : forme de summary.csv, 16 décimales (%.16e), state_final.f32", {
  o <- tempfile(); r <- run_cli("--variant", "r-rcpp", "--n", "16", "--years", "3", "--out", o)
  expect_equal(r$status, 0L)
  l <- readLines(file.path(o, "summary.csv"))
  expect_equal(l[1], "year,species,sum_B,sum_D,mean_H"); expect_length(l, 1 + 3 * 8)
  expect_equal(file.size(file.path(o, "state_final.f32")), 3 * 8 * 16 * 16 * 4)
  tj <- jsonlite::fromJSON(file.path(o, "timing.json"))
  expect_equal(tj$n, 16); expect_equal(tj$years, 3)
  expect_setequal(names(tj), c("lang", "n", "years", "threads", "init_s", "step_mean_s", "total_s", "write_s"))
})

read_f32 <- function(f) readBin(f, "numeric", n = file.size(f) / 4, size = 4, endian = "little")

test_that("§8 : identité au bit près entre 1 et 4 fils (r-rcpp, N=200, Y=5)", {
  a <- tempfile(); b <- tempfile()
  expect_equal(run_cli("--variant", "r-rcpp", "--n", "200", "--years", "5", "--threads", "1", "--out", a)$status, 0L)
  expect_equal(run_cli("--variant", "r-rcpp", "--n", "200", "--years", "5", "--threads", "4", "--out", b)$status, 0L)
  for (f in c("summary.csv", "state_final.f32"))
    expect_identical(unname(tools::md5sum(file.path(a, f))), unname(tools::md5sum(file.path(b, f))))
})

test_that("les deux variantes concordent à 1e-9 (relatif) sur summary.csv et l'état", {
  a <- tempfile(); b <- tempfile()
  run_cli("--variant", "r-base", "--n", "200", "--years", "5", "--out", a)
  run_cli("--variant", "r-rcpp", "--n", "200", "--years", "5", "--out", b)
  sa <- read.csv(file.path(a, "summary.csv")); sb <- read.csv(file.path(b, "summary.csv"))
  expect_equal(sa[, 1:2], sb[, 1:2])
  for (col in c("sum_B", "sum_D", "mean_H")) {
    den <- pmax(abs(sa[[col]]), 1e-300)
    expect_lt(max(abs(sa[[col]] - sb[[col]]) / den), 1e-9)
  }
  fa <- read_f32(file.path(a, "state_final.f32")); fb <- read_f32(file.path(b, "state_final.f32"))
  expect_lt(max(abs(fa - fb)), 1e-4 * max(abs(fa)))
})

test_that("P6 : --inject-nan hors de 1..Y refusé ; P4 : format %.16e", {
  r <- run_cli("--n", "10", "--years", "3", "--inject-nan", "9", "--out", tempfile())
  expect_equal(r$status, 1L); expect_match(r$stderr, "refusé")
  o <- tempfile(); run_cli("--n", "10", "--years", "2", "--out", o)
  expect_match(readLines(file.path(o, "summary.csv"))[2], "^1,0,[0-9]\\.[0-9]{16}e[+-][0-9]{2},")
})
