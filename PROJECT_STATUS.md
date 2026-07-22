# AirSentinel — Project Status & Gap Analysis vs. Design Plan

*Cross-references `AirSentinel_design_plan.pptx`'s system architecture (slide 5) and data
flow (slide 6) against what's actually built across the three modules in this folder. Written
2026-07-21.*

## Folder layout

```
airsentinel/                (root — was "light_pollution/" until this pass)
├── forecasting/           Forecasting & CAAQMS data pipeline (Person 1 track) — LIVE
│                           (folder renamed from "airsentinel/"; the Python package inside
│                            is still importable as `airsentinel` — see its README)
├── vehicle_emissions/     Vehicle Emission Load Model ("tailpipe pollution") — live on real VAHAN data
├── shared/                 Fusion layer + dashboard + alerts — LIVE, degrades gracefully
├── AirSentinel_MasterDoc.pptx   Pitch deck
├── README.md                    Entry point — start here
└── PROJECT_STATUS.md            This file — full gap analysis & audit
```

Each module is an independent Python project (own `.venv`, own `requirements.txt`) so the
two-person split can keep working on separate tracks without touching each other's
environments. `vehicle_emissions` and `shared` both consume `forecasting`'s outputs by file
(CSV) rather than by importing its runtime, except for the zone registry — `vehicle_emissions`
installs `forecasting` in editable mode specifically so the 13-zone list is never retyped
(see `vehicle_emissions/README.md` "Compatibility").

## Component-by-component status (design plan slide 5: system architecture)

### 01 · Data Sources
| Source | Status |
|---|---|
| CPCB/DPCC CAAQMS stations | **Live** — `forecasting` scrapes this directly from dpccairdata.com |
| IMD weather data | **Substituted** — `forecasting` uses each CAAQMS station's own met sensors (temp/humidity/wind) instead of a separate IMD feed; reasonable proxy, not identical to IMD, documented in `forecasting`'s honesty notes |
| Sentinel-2 / Sentinel-5P imagery | **Teammate's track** — satellite/Prithvi, not in this folder |
| VAHAN vehicle registrations | **Live, real data** — real VAHAN Tabular Summary exports (RTO × fuel-type, RTO × vehicle-class, all 10 relevant RTOs) combined via a documented estimation method (`real_registrations.py`) and the real, live-pulled RTO→zone mapping (`rto_mapping.py`); produces genuine per-zone variation, no longer a placeholder |
| Delhi Supersite data | **Same site as DPCC, confirmed working, data sparse** — it's a station on dpccairdata.com, not a separate site; the existing scraper pulls it unchanged, but real historical data was only found on one isolated date (station appears to have gone quiet ~March 2025) — see `shared/cross_validation.py` |
| SAFAR forecasts | **Real site, currently down** — safar.tropmet.res.in's TLS certificate is expired as of this session (`certificate has expired`); a site-side outage, not a scraping difficulty |

### 02 · Model Layer
| Module | Status |
|---|---|
| Forecasting Engine (24-72h per zone) | **Live** — `forecasting`, gradient-boosted trees (not the deck's "graph+LSTM" — see `forecasting/src/airsentinel/forecast.py` docstring for why), beats persistence baseline at all horizons |
| Satellite Attribution Engine (fine-tuned Prithvi) | **Teammate's track** |
| Vehicle Emission Load Model (VAHAN-based math model) | **Live on real data** — `vehicle_emissions`, deterministic formula, real VAHAN per-RTO counts (see below) |
| Enforcement Zone Ranker (hotspot + emission + land use) | **Not built** — explicitly out of scope for this session; `shared/zone_ranking.py` provides a narrower forecast-only urgency ranking as a stopgap, clearly scoped as *not* a replacement (see its docstring) |

### 03 · Fusion Layer
| Component | Status |
|---|---|
| GRAP Stage Mapper (forecast AQI → CAQM stage I-IV) | **Built this session** — `shared/grap.py`, official CAQM thresholds verified live against caqm.nic.in |
| Cross-validation check vs. Supersite & SAFAR | **Scaffolded, real access confirmed, not enough data to run tonight** — Supersite's scraper access is confirmed working (same DPCC contract) but its real historical data is too sparse for a meaningful backtest; SAFAR's site is currently down (expired cert). `shared/cross_validation.py`'s comparison function is ready the moment either has enough real, overlapping data |

### 04 · Output Layer
| Component | Status |
|---|---|
| Official Dashboard | **Built this session** — `shared/dashboard.py`, static themed HTML matching the deck's mockup (slide 7), renders only real data, shows explicit "pending" badges for anything not yet live |
| Citizen/Official Alert Generator | **Built this session** — `shared/alerts.py`, templated from real computed values (matches deck slide 8) |
| API/export to MCD, DPCC, traffic police | **Not built** — no real endpoint exists to integrate with; out of scope |

## What was deliberately NOT built, and why

- **A full ARAI/CPCB emission-factor table covering every vehicle category.** The real
  emission factors now in use are official BS6 regulatory NOx/PM *limits* (petrol/diesel
  car & two-wheeler, plus electric = 0, a physical fact) — real and cited, but the
  regulatory cap, not a full real-world-measured table broken out by bus/truck/three-wheeler
  or older BS-IV+ vehicles still on Delhi's roads. Real sources for the fuller table are
  cited in `vehicle_emissions/README.md` "What's still open"; the PDF/table-extraction tools
  available this session couldn't verify the complete table with confidence, so it wasn't
  guessed at.
- **Full SAFAR/Supersite scraper integration into the live pipeline.** Access is confirmed
  for Supersite (same DPCC contract) and blocked for SAFAR (site down, expired cert) — see
  the Data Sources table above. Neither has enough real, current, overlapping data to run a
  meaningful cross-validation backtest yet.
- **The full Enforcement Zone Ranker** (hotspot + emission + land-use cross-check) — this is
  explicitly the satellite/enforcement track's Days 8-9 task per the team brief, not
  duplicated here.

## Vehicle registration data — now real, not a placeholder

Real VAHAN Tabular Summary exports (State = Delhi(16), accessed 2026-07-21) replaced the
earlier demo dataset: `vehicle_emissions/data/raw/vahan_rto_fuel_2026.csv` (RTO × fuel type)
and `vahan_rto_category_2026.csv` (RTO × vehicle class), covering all 10 RTOs the project's
zone mapping uses. VAHAN's UI doesn't expose the joint (vehicle class, fuel type)
breakdown directly, so `vehicle_emissions/src/vehicle_emissions/real_registrations.py`
combines the two real marginals via a documented, disclosed estimation method (an
independence assumption, restricted to the fuel types with a real cited emission factor:
petrol, diesel, electric) — full reasoning in that module's docstring and
`vehicle_emissions/README.md` "Real VAHAN data".

Result: genuine per-zone variation, e.g. this run — RK Puram 1.00 (highest), Anand Vihar /
Vivek Vihar 0.19 (lowest) — no longer the flat 1.00-everywhere placeholder from the earlier
demo dataset. `data_provenance` in the output now reads `"real, cited"`, and
`shared/outputs/dashboard.html` shows the green "live" badge, not amber "DEMO DATA". The
earlier `build_demo_data.py` (real Delhi-wide totals, evenly split across zones) is kept as
a documented fallback pattern for extending this to a future city before real per-RTO data
is sourced there — `pipeline.py` now prefers the real VAHAN files automatically.

## Hardcoding & overfitting — session-wide guarantees

- **No fabricated data anywhere in `vehicle_emissions` or `shared`.** Every emission factor,
  distance estimate, and vehicle count must come from a real, cited input file — the modules
  fail loudly with instructions rather than substitute a plausible-looking default. Verified
  this session with a `random|fake|dummy|mock|synthetic` grep across both new modules (clean).
- **No fitted models in `vehicle_emissions` or `shared`.** Both are deterministic formulas,
  lookups, and string templates — verified this session with a `sklearn|.fit(|.predict(` grep
  (only hit: a metric *function*, `mean_absolute_error`, in `cross_validation.py`, not a
  trained model). Zero overfitting risk in either module by construction.
- **`forecasting`'s model** (the one place in this project that does fit anything) has its
  own overfitting safeguards — CV-tuned regularization and persistence-anchored shrinkage —
  documented in `forecasting/SESSION_SUMMARY.md` §7-9.
- **Official constants that ARE hardcoded** (CPCB AQI breakpoints, GRAP stage thresholds) are
  treated the same way throughout this project: cited to a specific, verifiable source, never
  presented as if self-evident.

## Running the full pipeline, in order

```powershell
# 1. Forecasting (live CAAQMS scrape + model)
cd "C:\Users\a955032\OneDrive - ATOS\Desktop\airsentinel\forecasting"
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m airsentinel.pipeline

# 2. Vehicle emissions — real VAHAN data (see vehicle_emissions/README.md "Real VAHAN data")
cd "C:\Users\a955032\OneDrive - ATOS\Desktop\airsentinel\vehicle_emissions"
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m vehicle_emissions.build_reference_data
.\.venv\Scripts\python.exe -m vehicle_emissions.pipeline

# 3. Fusion + dashboard (works with just step 1 done; picks up step 2 automatically if present)
cd "C:\Users\a955032\OneDrive - ATOS\Desktop\airsentinel\shared"
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m shared.pipeline --horizon 24
# open shared/outputs/dashboard.html in a browser
```
