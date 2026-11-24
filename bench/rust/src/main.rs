use bench_sim::{cli, sim};

fn main() {
    let cfg = match cli::parse(std::env::args().skip(1)) {
        Ok(Some(c)) => c,
        Ok(None) => {
            println!("{}", cli::AIDE);
            return;
        }
        Err(e) => {
            eprintln!("Erreur : {e}\n\n{}", cli::AIDE);
            std::process::exit(e.code);
        }
    };
    match sim::run(&cfg) {
        Ok(t) => eprintln!(
            "Terminé : n={} années={} fils={} init={:.3}s pas moyen={:.4}s total={:.3}s écriture={:.3}s",
            cfg.n, cfg.years, cfg.threads, t.init_s, t.step_mean_s, t.total_s, t.write_s
        ),
        Err(e) => {
            eprintln!("Erreur : {e}");
            std::process::exit(e.code);
        }
    }
}
