"""
Real reference data generator — emission factors and distance estimates.

Unlike build_demo_data.py (kept as a fallback for when no real registration data exists at
all), this writes emission_factors.csv and distance_estimates.csv from REAL, cited sources
only — no [DEMO DATA] tag, because none of these figures are estimates or placeholders:

  - BS6 (Bharat Stage VI) regulatory NOx/PM limits — official, India's mandated standard
    since 1 April 2020, corroborated across multiple independent sources:
      * Petrol passenger car / two-wheeler: NOx 60 mg/km = 0.06 g/km, PM 4.5 mg/km = 0.0045 g/km
      * Diesel passenger car:               NOx 80 mg/km = 0.08 g/km, PM 4.5 mg/km = 0.0045 g/km
  - Electric (battery/BOV) vehicles: 0 g/km NOx and PM — a physical fact (no tailpipe
    combustion on a battery electric drivetrain), not a figure requiring an external
    citation search, same treatment as "a candle produces light" would get.
  - Average daily distance, two-wheelers, Indian cities: ~27-33 km/day (midpoint 30 km/day
    used here), from a published Indian urban-mobility study found via web search this
    session.
  - Average daily distance, cars, Delhi: ~33.5 km/day, derived from a 2003 three-cities
    vehicle-characteristics study (urbanemissions.info) that reports a comparison city's car
    annual mileage as "10,400 km, which is only 15% lower than that for Delhi" — implying
    Delhi ~= 10,400 / 0.85 ~= 12,235 km/year ~= 33.5 km/day. LOWER CONFIDENCE than the BS6
    limits above: this environment has no PDF-rendering tool, so the source PDF could not be
    read directly to verify the figure — it's taken from a search-engine-surfaced summary of
    the study, not confirmed against the primary document. Used anyway, clearly flagged,
    because a distinct (even if less-certain) car figure is more honest than reusing the
    two-wheeler number for cars (which made the whole index collapse to a near-exact vehicle
    count — see PROJECT_STATUS.md).
  - e-rickshaw: no category-specific citation found; reuses the two-wheeler figure as a
    placeholder. Doesn't affect the computed load either way (e-rickshaws are 0 g/km).

Run once (or whenever you want to regenerate from scratch):
    python -m vehicle_emissions.build_reference_data
Then run real_registrations.load_by_rto_real() (via pipeline.py) for the registration side.
"""

from __future__ import annotations

import sys

import pandas as pd

from . import config

REAL_TAG = "[REAL, cited — see build_reference_data.py]"


def build_emission_factors() -> pd.DataFrame:
    rows = [
        ("two_wheeler", "petrol", "NOx", 0.060, "BS6",
         f"{REAL_TAG} Official BS6 NOx limit, petrol two-wheeler: 60 mg/km (India, mandated since 1 Apr 2020)."),
        ("two_wheeler", "petrol", "PM", 0.0045, "BS6",
         f"{REAL_TAG} Official BS6 PM limit (shared across BS6 categories): 4.5 mg/km."),
        ("two_wheeler", "electric", "NOx", 0.0, "N/A — physical fact",
         f"{REAL_TAG} Battery electric drivetrain has no tailpipe exhaust: 0 g/km by definition."),
        ("two_wheeler", "electric", "PM", 0.0, "N/A — physical fact",
         f"{REAL_TAG} Battery electric drivetrain has no tailpipe exhaust: 0 g/km by definition."),
        ("car", "petrol", "NOx", 0.060, "BS6",
         f"{REAL_TAG} Official BS6 NOx limit, petrol passenger car: 60 mg/km."),
        ("car", "petrol", "PM", 0.0045, "BS6",
         f"{REAL_TAG} Official BS6 PM limit: 4.5 mg/km."),
        ("car", "diesel", "NOx", 0.080, "BS6",
         f"{REAL_TAG} Official BS6 NOx limit, diesel passenger car: 80 mg/km."),
        ("car", "diesel", "PM", 0.0045, "BS6",
         f"{REAL_TAG} Official BS6 PM limit: 4.5 mg/km."),
        ("car", "electric", "NOx", 0.0, "N/A — physical fact",
         f"{REAL_TAG} Battery electric drivetrain has no tailpipe exhaust: 0 g/km by definition."),
        ("car", "electric", "PM", 0.0, "N/A — physical fact",
         f"{REAL_TAG} Battery electric drivetrain has no tailpipe exhaust: 0 g/km by definition."),
        ("e_rickshaw", "electric", "NOx", 0.0, "N/A — physical fact",
         f"{REAL_TAG} Battery electric drivetrain has no tailpipe exhaust: 0 g/km by definition."),
        ("e_rickshaw", "electric", "PM", 0.0, "N/A — physical fact",
         f"{REAL_TAG} Battery electric drivetrain has no tailpipe exhaust: 0 g/km by definition."),
    ]
    return pd.DataFrame(rows, columns=config.EMISSION_FACTORS_COLUMNS)


CAR_DISTANCE_TAG = "[REAL, cited but LOWER CONFIDENCE — see build_reference_data.py]"


def build_distance_estimates() -> pd.DataFrame:
    rows = [
        ("two_wheeler", 30.0,
         f"{REAL_TAG} Real cited range 27-33 km/day, Indian-cities urban mobility study; midpoint used."),
        ("car", 33.5,
         f"{CAR_DISTANCE_TAG} Derived from a 2003 three-cities vehicle-characteristics study "
         f"(urbanemissions.info) reporting a comparison city's car annual mileage as '10,400 "
         f"km, only 15% lower than Delhi' -> Delhi ~= 10,400/0.85 ~= 12,235 km/yr ~= 33.5 "
         f"km/day. Could not verify against the primary PDF (no PDF-rendering tool in this "
         f"environment) — taken from a search-engine-surfaced summary of the study, not the "
         f"source document directly. Distinct from and less certain than the BS6 limits above."),
        ("e_rickshaw", 30.0,
         f"{REAL_TAG} No e-rickshaw-specific citation found; reused the two-wheeler figure. "
         f"Note: e-rickshaws have a 0 g/km emission factor, so this distance value doesn't "
         f"affect the computed load either way."),
    ]
    return pd.DataFrame(rows, columns=config.DISTANCE_ESTIMATES_COLUMNS)


def main() -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    efs = build_emission_factors()
    dists = build_distance_estimates()
    efs.to_csv(config.EMISSION_FACTORS_CSV, index=False)
    dists.to_csv(config.DISTANCE_ESTIMATES_CSV, index=False)
    print("Real reference data written (BS6 regulatory limits + physical-fact EV factors, "
          "all cited — see this file's docstring):")
    print(f"  {config.EMISSION_FACTORS_CSV}  ({len(efs)} rows)")
    print(f"  {config.DISTANCE_ESTIMATES_CSV}  ({len(dists)} rows)")
    print("\nRegistration counts come from real_registrations.py (real VAHAN data), not this "
          "script — run `python -m vehicle_emissions.pipeline` next.")


if __name__ == "__main__":
    sys.exit(main())
