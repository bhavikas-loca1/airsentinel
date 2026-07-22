"""
Real VAHAN registration data — RTO x fuel-type and RTO x vehicle-class marginals, pulled
directly from vahan.parivahan.gov.in's Tabular Summary (State=Delhi(16)) on 2026-07-21. This
is REAL data, not demo/estimated input — see config.REAL_RTO_FUEL_CSV / REAL_RTO_CATEGORY_CSV
and the two raw files themselves for the exact citations VAHAN's export carries.

Why two files, and why they need to be combined
--------------------------------------------------
VAHAN's Tabular Summary exports two SEPARATE cross-tabs per RTO — counts by fuel type
(all vehicle classes combined) and counts by vehicle class (all fuel types combined) — not
the joint (vehicle_class, fuel_type) breakdown. To estimate the joint count for the two
categories this module has real cited BS6 emission factors for (two_wheeler, car), we assume
the RTO-wide fuel-type ratio (restricted to just the fuel types we have a cited factor for —
petrol, diesel, electric) applies equally within each vehicle class. This is a real,
disclosed statistical assumption (independence between vehicle class and fuel type,
restricted to the covered-fuel subset) — not a random guess, and not the literal joint count
VAHAN's UI doesn't expose either. It will slightly misallocate at the margins (e.g. a
diesel share estimated for two-wheelers, which are overwhelmingly not diesel in reality) —
disclosed here rather than hidden, and any (category, fuel) combination without a matching
emission factor is excluded and reported, not silently kept.

e-Rickshaws are the one exception: VAHAN's own class name ("e-Rickshaw(P)", "e-Rickshaw
with Cart (G)") is unambiguous — these are electric by definition, no estimation needed, so
they're assigned 100% electric directly rather than going through the ratio estimate.

Electric vehicles get a real emission factor of ZERO — a physical fact (no tailpipe exhaust
on a battery electric drivetrain), not something requiring an external citation search — so
they're counted, not silently dropped, and correctly contribute nothing to tailpipe load.
CNG-only and hybrid combinations are excluded from the estimate entirely: no cited
BS6-equivalent tailpipe factor was verified for them this session, and folding their mass
into the petrol/diesel/electric ratio would overstate those categories.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from . import config, rto_mapping

# VAHAN's real fuel-type labels -> the three buckets we have real cited emission factors for.
# Every other real label (CNG ONLY, all dual-fuel/hybrid combinations, FLEX-FUEL) is
# deliberately left unmapped and excluded from the ratio's denominator — see module docstring.
_FUEL_BUCKET = {
    "PETROL": "petrol",
    "PETROL(E20)": "petrol",
    "DIESEL": "diesel",
    "PURE EV": "electric",
    "ELECTRIC(BOV)": "electric",
}

# VAHAN's real vehicle-class labels -> our normalized categories. Classes not listed here
# (Adapted Vehicle, Fork Lift, Vintage Motor Vehicle, Motorised Cycle) have no cited emission
# factor and negligible counts (1-49 per RTO) — excluded, not estimated.
_TWO_WHEELER_CLASSES = {"M-Cycle/Scooter", "M-Cycle/Scooter-With Side Car", "Moped"}
_CAR_CLASSES = {"Motor Car"}
_ERICKSHAW_CLASSES = {"e-Rickshaw(P)", "e-Rickshaw with Cart (G)"}


def _load_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not config.REAL_RTO_FUEL_CSV.exists() or not config.REAL_RTO_CATEGORY_CSV.exists():
        raise FileNotFoundError(
            f"Real VAHAN exports not found at {config.REAL_RTO_FUEL_CSV} and/or "
            f"{config.REAL_RTO_CATEGORY_CSV}. These are the real per-RTO Tabular Summary "
            f"exports (RTO x Fuel, RTO x Vehicle Class) — see README.md 'Real VAHAN data'."
        )
    fuel = pd.read_csv(config.REAL_RTO_FUEL_CSV)
    category = pd.read_csv(config.REAL_RTO_CATEGORY_CSV)
    return fuel, category


def _fuel_shares_by_rto(fuel_df: pd.DataFrame) -> pd.DataFrame:
    """Per RTO, the share of (petrol, diesel, electric) among just those three real,
    cited-emission-factor buckets — CNG/hybrid/flex-fuel mass excluded from the denominator
    entirely (see module docstring)."""
    df = fuel_df.copy()
    df["bucket"] = df["fuel_type"].map(_FUEL_BUCKET)
    covered = df.dropna(subset=["bucket"])
    totals = covered.groupby(["rto_code", "bucket"])["vehicle_count"].sum().unstack(fill_value=0.0)
    for col in ("petrol", "diesel", "electric"):
        if col not in totals.columns:
            totals[col] = 0.0
    denom = totals[["petrol", "diesel", "electric"]].sum(axis=1)
    shares = totals[["petrol", "diesel", "electric"]].div(denom, axis=0).fillna(0.0)
    return shares


def _category_totals_by_rto(category_df: pd.DataFrame) -> pd.DataFrame:
    df = category_df.copy()

    def bucket(c: str) -> str | None:
        if c in _TWO_WHEELER_CLASSES:
            return "two_wheeler"
        if c in _CAR_CLASSES:
            return "car"
        if c in _ERICKSHAW_CLASSES:
            return "e_rickshaw"
        return None

    df["bucket"] = df["vehicle_category"].map(bucket)
    covered = df.dropna(subset=["bucket"])
    return covered.groupby(["rto_code", "bucket"])["vehicle_count"].sum().unstack(fill_value=0.0)


def estimate_by_rto() -> pd.DataFrame:
    """Real VAHAN counts, combined into (rto_code, vehicle_category, fuel_type, vehicle_count)
    via the documented estimation method above. Returns the same shape as
    registrations.load_by_rto() would, before zone aggregation.
    """
    fuel_df, category_df = _load_raw()
    shares = _fuel_shares_by_rto(fuel_df)
    cat_totals = _category_totals_by_rto(category_df)

    citation_fuel = fuel_df["source_citation"].iloc[0]
    citation_cat = category_df["source_citation"].iloc[0]
    period = fuel_df["data_period"].iloc[0]

    rows = []
    for rto_code in cat_totals.index:
        s = shares.loc[rto_code] if rto_code in shares.index else pd.Series({"petrol": 0.0, "diesel": 0.0, "electric": 0.0})

        for cat_col, cat_name in (("two_wheeler", "two_wheeler"), ("car", "car")):
            total = cat_totals.loc[rto_code].get(cat_col, 0.0)
            if total <= 0:
                continue
            for fuel_name, share in (("petrol", s["petrol"]), ("diesel", s["diesel"]), ("electric", s["electric"])):
                count = total * share
                if count <= 0:
                    continue
                rows.append({
                    "rto_code": rto_code, "vehicle_category": cat_name, "fuel_type": fuel_name,
                    "vehicle_count": count, "data_period": period,
                    "source_citation": (
                        f"REAL: {citation_cat} [{cat_name} total] x {citation_fuel} "
                        f"[{fuel_name} share, restricted to petrol/diesel/electric] "
                        f"— independence assumption, see real_registrations.py docstring."
                    ),
                })

        # e-Rickshaws: VAHAN's own class name is unambiguous — 100% electric, no estimation.
        erick_total = cat_totals.loc[rto_code].get("e_rickshaw", 0.0)
        if erick_total > 0:
            rows.append({
                "rto_code": rto_code, "vehicle_category": "e_rickshaw", "fuel_type": "electric",
                "vehicle_count": erick_total, "data_period": period,
                "source_citation": f"REAL: {citation_cat} — VAHAN class name is electric by definition, no estimation needed.",
            })

    return pd.DataFrame(rows)


def load_by_rto_real(known_zones: set[str] | None = None) -> pd.DataFrame:
    """Aggregate the real per-RTO estimate up to AirSentinel zones via rto_mapping.py's
    documented nearest-RTO approximation (same even-split-across-matched-zones rule as
    registrations.load_by_rto())."""
    by_rto = estimate_by_rto()
    unknown_rtos = set(by_rto["rto_code"]) - rto_mapping.known_rto_codes()
    if unknown_rtos:
        raise ValueError(f"Real VAHAN export has rto_code values not in rto_mapping.py: {sorted(unknown_rtos)}")

    rows = []
    for _, r in by_rto.iterrows():
        zones = rto_mapping.zone_for_rto_code(r["rto_code"])
        if not zones:
            continue
        split_count = r["vehicle_count"] / len(zones)
        for zone in zones:
            rows.append({
                "zone": zone, "vehicle_category": r["vehicle_category"], "fuel_type": r["fuel_type"],
                "vehicle_count": split_count, "data_period": r["data_period"],
                "source_citation": r["source_citation"] + (
                    f" [via RTO {r['rto_code']}, split across {len(zones)} zones]" if len(zones) > 1
                    else f" [via RTO {r['rto_code']}]"
                ),
            })
    out = pd.DataFrame(rows, columns=config.REGISTRATIONS_COLUMNS)
    if known_zones is not None:
        unknown = set(out["zone"]) - known_zones
        if unknown:
            raise ValueError(f"Zone mapping produced unknown zones: {sorted(unknown)}")
    return out
