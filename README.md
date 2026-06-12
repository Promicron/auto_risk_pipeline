# Auto Insurance Risk Pipeline

A small data pipeline demonstrating ingestion, normalization, risk scoring, and reporting for auto insurance datasets. The project supports two input modes:

- `freMTPL2freq.csv` — The French freMTPL2freq dataset (single CSV). When present, the pipeline runs the `freMTPL2` adapter.
- Tabular sample data (`drivers.csv`, `vehicles.csv`, `telematics.csv`, `claims.csv`) — the default demo flow.

Project structure

- `run_pipeline.py` — entrypoint that orchestrates the pipeline stages.
- `pipeline/` — pipeline stages:
  - `ingest.py` — load and validate CSV inputs
  - `normalize.py` — standard pipeline normalization for the demo data
  - `score.py` — risk scoring for demo data
  - `report.py` — reporting and SQLite output for demo data
  - `fremtpl2.py` — adapter (normalize/score/report) for the `freMTPL2freq` dataset
- `data/raw/` — raw input CSVs (sample generator writes here)
- `data/generate_sample_data.py` — writes sample `drivers`, `vehicles`, `telematics`, `claims` CSVs
- `reports/` — output database and summary JSON files

Requirements

This repository uses Python 3.8+ and the libraries listed in `requirements.txt`. Install with pip:

```bash
python -m pip install -r requirements.txt
```

Quickstart

1. Generate sample demo data (optional):

```bash
python data/generate_sample_data.py
```

This writes demo CSVs to `data/raw/`.

2. Run the pipeline (default demo mode uses the generated CSV files):

```bash
python run_pipeline.py --raw data/raw --out reports
```

3. Run with `freMTPL2freq.csv` (single-file mode):

Place `freMTPL2freq.csv` into `data/raw/` and run the same command. If the file is present, the pipeline will use the `fremtpl2` adapter and write `reports/fremtpl2_risk.db` and `reports/fremtpl2_summary.json`.

Outputs

- `reports/risk_pipeline.db` — SQLite DB (demo mode)
- `reports/summary.json` — portfolio summary (demo mode)
- `reports/fremtpl2_risk.db` — SQLite DB (freMTPL2 mode)
- `reports/fremtpl2_summary.json` — summary (freMTPL2 mode)

Notes & next steps

- The `ingest.py` loader validates schemas defined in the module. Add or adjust schemas there if you introduce new input formats.
- If you want to centralize pipeline branching, consider refactoring `run_pipeline.py` to use a small dispatcher helper.

Contributing

PRs are welcome. Please run the pipeline locally and include sample output or tests for changes to scoring or normalization logic.

License

MIT-style internal example. No license specified.
