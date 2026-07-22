# Vehicle Emission Load Model — "tailpipe pollution" (AirSentinel)

Implements the **Vehicle Emission Load Model** from the AirSentinel design plan (slides 3–4,
6, 9): a modelled estimate of tailpipe pollution per zone, calculated the same way national
emission inventories are built — not sensed, not invented.

```
vehicle count (by type & fuel, per RTO)
  x emission factor (g/km, ARAI/CPCB tables)
  x avg. distance (published transport surveys)
  = Vehicle Emission Load Index per zone
```

## Real VAHAN data (current — this is what the pipeline runs on now)

`data/raw/vahan_rto_fuel_2026.csv` and `data/raw/vahan_rto_category_2026.csv` are **real**
exports pulled directly from vahan.parivahan.gov.in's Tabular Summary (State = Delhi(16),
accessed 2026-07-21) — RTO × fuel-type and RTO × vehicle-class registration counts for all
10 RTOs this module maps to a zone. `src/vehicle_emissions/real_registrations.py` combines
the two into a per-(zone, vehicle_category, fuel_type) estimate — see its docstring for the
exact method (VAHAN doesn't expose the joint breakdown directly, so the two marginals are
combined via a documented, disclosed independence assumption, restricted to the fuel types
this module has a real cited emission factor for: petrol, diesel, electric).

`src/vehicle_emissions/build_reference_data.py` writes the matching real (non-demo) emission
factors — official BS6 regulatory NOx/PM limits, plus 0 g/km for electric (a physical fact,
not an estimate) — and the same cited urban-mobility distance figure as before.

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m vehicle_emissions.build_reference_data   # emission factors + distance
.\.venv\Scripts\python.exe -m vehicle_emissions.pipeline               # picks up the real VAHAN files automatically
```

Result: real, differentiated per-zone variation (no longer a flat placeholder) — e.g. this
run: RK Puram 1.00 (highest), Anand Vihar / Vivek Vihar 0.19 (lowest). `data_provenance` in
the output now reads `"real, cited"`, and the dashboard shows the green "live" badge, not
amber "DEMO DATA".

**Known limitation, disclosed not hidden:** the independence assumption means the estimated
(category, fuel) split can misallocate at the margins — e.g. a small "two-wheeler/diesel"
share gets estimated even though diesel two-wheelers are practically nonexistent in reality.
Since no cited two-wheeler-diesel emission factor exists, that slice is excluded from the
index automatically (visible in `coverage_note`), not silently kept.

### Earlier fallback: demo data (superseded, kept for reference)

Before the real VAHAN exports above were available, `build_demo_data.py` generated a
real-world-informed-but-explicitly-labeled placeholder (real Delhi-wide totals split evenly
across zones, since no real per-zone data existed yet). It's kept as a fallback pattern for
extending this to a future city before real per-RTO data is sourced there — see its
docstring. `pipeline.py` now prefers the real VAHAN files automatically whenever both exist.

## Why this module needs real data files, not defaults

Two of the three inputs above (emission factors, average distances) are specific numeric
facts from official technical reports. This session located real, official sources for them
(links below) but could not extract exact verified figures with the tools available — so
rather than guess plausible-looking numbers and label them "ARAI/CPCB data," **this module
requires the real tables as input files**. Every number it ever outputs is traceable to a
document you (or your teammate) can point to. See `src/vehicle_emissions/config.py` for the
full reasoning.

The same applies to vehicle registration counts: Delhi's 13 AirSentinel hotspot zones are
not the same thing as VAHAN's RTO boundaries, and no official zone↔RTO mapping is published.

## The RTO → zone mapping

Rather than leave this mapping as a manual judgment call for whoever fills in the template,
`src/vehicle_emissions/rto_mapping.py` ships a **documented, inspectable nearest-RTO
approximation** — built from the real, current list of Delhi's 13 vehicle-registering RTOs,
pulled live from vahan.parivahan.gov.in this session (State = `Delhi(16)`). Two zones happen
to share a name with their RTO (Wazirpur, Dwarka — exact matches); the rest are geographic
nearest-neighbour judgment calls, each with its reasoning written inline in that file. When
one RTO is the nearest match for more than one zone (e.g. `DL8 CENTRAL NORTH (WAZIRPUR)` is
nearest to both Wazirpur and Ashok Vihar), its registration count is **split evenly** across
those zones rather than counted in full for each — counting in full would double the same
real vehicles across nearby zones.

This is still an approximation of real RTO office locations to real zone locations — not
a survey, not verified against actual road distances — and it's meant to be corrected: if
your team has better local knowledge of the real catchment areas, edit `rto_mapping.py`
directly, it's the single place this assumption lives.

**Until you supply real data, running the pipeline fails loudly with instructions — it never
produces a fabricated chart or number.** This is intentional.

## What's still open

1. ~~Vehicle registrations per RTO~~ — **done**, see "Real VAHAN data" above.
2. **Full ARAI/CPCB emission-factor table** — tonight's real factors are the official BS6
   regulatory *limits* (petrol/diesel car & two-wheeler, plus electric = 0), which is a
   real, defensible, cited number — but it's the regulatory cap, not a full real-world
   ARAI/CPCB measured-emissions table broken out by every category (buses, trucks,
   three-wheelers, older BS-IV+ vehicles still on the road). Pull the fuller table from:
   - [CPCB emission-factor PDF](https://cpcb.nic.in/displaypdf.php?id=RW1pc3Npb25fRmFjdG9yc19WZWhpY2xlcy5wZGY=)
   - [CPCB vehicular exhaust page](https://cpcb.nic.in/vehicular-exhaust/)
   - ARAI "Emission Factors for Indian In-Use Vehicles" report
   - Lok Sabha reply, 9 Aug 2021, "Vehicle-wise Emission Factors..." (data.gov.in)
3. **Category-specific average distances** — tonight's figure (30 km/day) is a real cited
   two-wheeler study reused for cars/e-rickshaws too. Pull car-specific figures from Delhi's
   Comprehensive Mobility Plan or the Economic Survey of Delhi's transport chapter.
4. **Buses, trucks, three-wheelers, older BS-norm vehicles** — not in the current category
   set (`two_wheeler`, `car`, `e_rickshaw`); add real emission factors + distances for them
   in `emission_factors.csv`/`distance_estimates.csv` to widen coverage.

Regenerate the input templates any time with `python -m vehicle_emissions.pipeline
--write-templates`.

## Setup

```powershell
cd "C:\Users\a955032\OneDrive - ATOS\Desktop\airsentinel\vehicle_emissions"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# installs the forecasting module's zone registry in editable mode — see "Compatibility" below
.\.venv\Scripts\python.exe -m pip install -e ..\forecasting
```

## Run

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m vehicle_emissions.build_reference_data   # emission factors + distance (real, cited)
.\.venv\Scripts\python.exe -m vehicle_emissions.pipeline               # uses the real VAHAN files already in data/raw/
```

The real VAHAN exports (`vahan_rto_fuel_2026.csv`, `vahan_rto_category_2026.csv`) are
already committed in `data/raw/` — if you're re-sourcing them yourself later, the same
Tabular Summary export steps are in "Real VAHAN data" above.

Output: `outputs/vehicle_emission_index.csv` —
`zone, vehicle_emission_load_raw_g_per_day, vehicle_emission_load_index, n_vehicle_categories_included, data_asof, coverage_note, data_provenance`.
`data_provenance` reads `"real, cited"` when the run used the real VAHAN files, or
`"demo — real-world-informed, not verified precision"` if it fell back to `build_demo_data.py`
— computed automatically from the input `source_citation` values, not something you set by hand.
`vehicle_emission_load_index` is relative (0–1, current zone's load ÷ the highest zone's
load), matching the design plan's dashboard mockup (slide 7: "Vehicle Emission Load Index:
0.81").

## Compatibility with the forecasting track

The `../forecasting` module (Python package still importable as `airsentinel`, per the
overall project brand) is installed in editable mode as this module's only project-specific
dependency — the 13-zone list is imported directly from `airsentinel.stations.ZONES`
(`pipeline.py::_known_zones`) rather than retyped, so the two modules cannot drift out of
sync on zone spelling. Output is keyed on `zone` alone (not `zone, date`, since registration
data doesn't change daily) so it joins trivially onto the forecasting module's
`zone, date, ...` output — see `../shared/README.md` for how the two are combined.

## What this module is not claiming

Carried verbatim from the design plan (slide 9): **the Vehicle Emission Load Index is a
modelled estimate from registration data, not a live sensor reading** — a legitimate,
standard methodology (the same one national emission inventories use), but not the same
claim as "we measured a tailpipe." No overfitting risk: this is a deterministic formula
(sum + relative normalization) over real inputs, with no fitted parameters at all.
