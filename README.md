# AirSentinel

Predicting Delhi's air quality 24–72 hours ahead, guessing why it's bad zone-by-zone, and
turning that into GRAP-ready action — feeding the Graded Response Action Plan better,
earlier information instead of replacing it. Built for the ET AI Hackathon (Problem
Statement 5).

**Start here:** [`AirSentinel_MasterDoc.pptx`](AirSentinel_MasterDoc.pptx) — the pitch deck
(architecture, GRAP relevance, hackathon-criteria breakdown, integration plan). For the full
technical gap-analysis and hardcoding/overfitting audit, see
[`PROJECT_STATUS.md`](PROJECT_STATUS.md).

## What's here

Three independent Python modules, each with its own `.venv`:

| Module | What it does | Status |
|---|---|---|
| [`forecasting/`](forecasting/) | Live DPCC CAAQMS scraper (13 Delhi zones) → CPCB AQI → 24/48/72h forecast, beats a persistence baseline | **Live** |
| [`vehicle_emissions/`](vehicle_emissions/) | Vehicle Emission Load Model ("tailpipe pollution") — real VAHAN RTO×fuel and RTO×class data, real BS6 emission limits | **Live, real data** — genuine per-zone variation, see its README |
| [`shared/`](shared/) | Fusion layer: GRAP stage mapper, alert generator, zone urgency ranking, themed dashboard | **Live** |

`forecasting`'s Python package is still importable as `airsentinel` (the folder was renamed
to match Person 1's role; the package name is the overall project brand).

## Run it

```powershell
# 1. Forecasting — live CAAQMS scrape + model
cd forecasting
python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m airsentinel.pipeline

# 2. Vehicle emissions — real VAHAN data (see vehicle_emissions/README.md)
cd ..\vehicle_emissions
python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e ..\forecasting
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m vehicle_emissions.build_reference_data
.\.venv\Scripts\python.exe -m vehicle_emissions.pipeline

# 3. Fusion + dashboard
cd ..\shared
python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m shared.pipeline --horizon 24
# open shared/outputs/dashboard.html
```

## Honesty principles this project follows throughout

- **Never fabricate.** Every module either uses real, cited data or fails loudly with
  instructions — never a plausible-looking placeholder presented as real.
- **Label what's estimated vs. directly real, visibly.** `vehicle_emissions` runs on real
  VAHAN per-RTO registration exports + real BS6 emission limits; where two real marginals
  had to be combined into an estimate (VAHAN doesn't expose the joint breakdown), the method
  is disclosed in `real_registrations.py`, not hidden. A `data_provenance` flag propagates
  to the dashboard automatically — green "live" for real data, amber "DEMO DATA" if the
  module ever falls back to the placeholder dataset (kept for future cities without real
  data yet).
- **Cite official constants.** CPCB AQI breakpoints, GRAP stage thresholds, BS6 emission
  limits — all cited to a specific, verifiable source.
- **Guard against overfitting.** `forecasting`'s model is the only fitted component in this
  project; it uses walk-forward cross-validation and persistence-anchored shrinkage so model
  selection can't prefer a configuration that beats the baseline in-sample while losing
  out-of-fold. `vehicle_emissions` and `shared` are deterministic (formulas, lookups,
  templates) — zero overfitting risk by construction.

See [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for the full component-by-component status
against the design plan, what was deliberately not built and why, and the complete
hardcoding/overfitting audit.
