"""
Real VAHAN registration data — RTO x fuel-type and RTO x vehicle-class marginals, pulled
directly from vahan.parivahan.gov.in's Tabular Summary (State=Delhi(16)) on 2026-07-21. This
is REAL data, not demo/estimated input — see config.REAL_RTO_FUEL_CSV / REAL_RTO_CATEGORY_CSV
and the two raw files themselves for the exact citations VAHAN's export carries.

Why two files, and how they're combined (revised — iterative proportional fitting)
--------------------------------------------------------------------------------------
VAHAN's Tabular Summary exports two SEPARATE cross-tabs per RTO — counts by fuel type
(all vehicle classes combined) and counts by vehicle class (all fuel types combined) — not
the joint (vehicle_class, fuel_type) breakdown. An earlier version of this module estimated
the joint via a plain independence assumption (apply the RTO-wide fuel-type ratio uniformly
to every vehicle class). That was a real bug, not just an approximation: two-wheelers are
~72% of Delhi's fleet, so ~72% of each RTO's real diesel count got assigned to
two-wheelers — where it was then EXCLUDED (no diesel two-wheeler emission factor exists,
correctly, because diesel two-wheelers are practically nonexistent in reality). Net effect:
diesel CARS — the highest per-km NOx segment this module covers (80 mg/km vs. 60 mg/km
petrol) — were undercounted by roughly 3-4x, because most of the real diesel mass was
misallocated to a category it then vanished from.

Fixed via **iterative proportional fitting (IPF / raking)** with structural zeros — the
standard technique for reconstructing a joint table from marginals when some cells are
known, not assumed, to be impossible:

    two_wheeler x diesel  = 0   (diesel two-wheelers are not a real market segment in India)
    e_rickshaw  x petrol  = 0   (VAHAN's own class name is unambiguous: electric only)
    e_rickshaw  x diesel  = 0   (same)
    e_rickshaw  x other   = 0   (same)

IPF alternately rescales rows to match the real category totals and columns to match the
real fuel-type totals until both are satisfied simultaneously (both real marginals are
matched EXACTLY at convergence — this is not new data, it's a better-justified way to
combine the two real marginals already in hand). With these structural zeros, all of an
RTO's real diesel count is correctly forced onto cars (the only category that can absorb
it), fixing the undercount. See `_ipf_joint()`.

CNG-only and dual-fuel/hybrid vehicles (grouped as "other_fuel" below) are now included as
a REAL, quantified column in the IPF — not silently dropped before they even enter the
registrations table. They still have no cited BS6-equivalent tailpipe factor, so
index.compute() still excludes them from the load calculation — but now with their real
magnitude visible in coverage_note, and the exclusion's likely DIRECTION disclosed (see
`OTHER_FUEL_BIAS_NOTE` below): this is disproportionately Delhi's commercial fleet — autos,
taxis, LCVs, the highest km/day segment — so dropping it is not a neutral omission, it likely
understates zones with more commercial traffic.

RTO -> zone allocation: when an RTO is the nearest match for more than one zone, its
estimated count is split evenly across those zones (see rto_mapping.py) — no finer-grained
official data exists to allocate a shared RTO's fleet between the zones it borders. This
was already the mechanism; it's now also disclosed inline in the final output's
coverage_note (see `zone_rto_notes()`), not just in the intermediate source_citation field.

Electric vehicles get a real emission factor of ZERO — a physical fact (no tailpipe exhaust
on a battery electric drivetrain), not something requiring an external citation search — so
they're counted, not silently dropped, and correctly contribute nothing to tailpipe load.
"""

from __future__ import annotations

import pandas as pd

from . import config, rto_mapping

# VAHAN's real fuel-type labels -> the buckets used in the joint estimate. Petrol/diesel/
# electric have real cited BS6 (or physical-fact, for electric) emission factors; every other
# real label is grouped into "other_fuel" — included as a real, quantified count, but with no
# cited tailpipe factor, so it's excluded from the load calc (see module docstring).
_FUEL_BUCKET = {
    "PETROL": "petrol",
    "PETROL(E20)": "petrol",
    "DIESEL": "diesel",
    "PURE EV": "electric",
    "ELECTRIC(BOV)": "electric",
    # everything else present in the real export (CNG ONLY, all dual-fuel/hybrid
    # combinations, FLEX-FUEL(ETHANOL), PLUG-IN HYBRID EV, STRONG HYBRID EV) maps to
    # "other_fuel" via the .get(..., "other_fuel") fallback below — not enumerated here so a
    # VAHAN label neither of us has seen yet still lands somewhere real, not silently vanishes.
}

OTHER_FUEL_BIAS_NOTE = (
    "The excluded 'other_fuel' count (CNG-only + dual-fuel/hybrid combinations) is "
    "disproportionately Delhi's commercial fleet (autos, taxis, LCVs) — the highest km/day "
    "segment covered by this data. Dropping it likely UNDERSTATES zones with more "
    "commercial traffic, not a neutral omission — see real_registrations.py."
)

# VAHAN's real vehicle-class labels -> our normalized categories. Classes not listed here
# (Adapted Vehicle, Fork Lift, Vintage Motor Vehicle, Motorised Cycle) have no cited emission
# factor and negligible counts (1-49 per RTO) — excluded, not estimated.
_TWO_WHEELER_CLASSES = {"M-Cycle/Scooter", "M-Cycle/Scooter-With Side Car", "Moped"}
_CAR_CLASSES = {"Motor Car"}
_ERICKSHAW_CLASSES = {"e-Rickshaw(P)", "e-Rickshaw with Cart (G)"}

_CATEGORIES = ("two_wheeler", "car", "e_rickshaw")
_FUELS = ("petrol", "diesel", "electric", "other_fuel")

# Structural zeros: cells that are impossible by real-world/regulatory definition, not
# estimated to be small — see module docstring for why each one is a certainty, not a guess.
_STRUCTURAL_ZEROS = {
    ("two_wheeler", "diesel"),
    ("e_rickshaw", "petrol"),
    ("e_rickshaw", "diesel"),
    ("e_rickshaw", "other_fuel"),
}
_ALLOWED_CELLS = [
    (cat, fuel) for cat in _CATEGORIES for fuel in _FUELS if (cat, fuel) not in _STRUCTURAL_ZEROS
]


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


def _ipf_joint(
    row_totals: dict[str, float],
    col_totals: dict[str, float],
    allowed: list[tuple[str, str]],
    max_iter: int = 200,
    tol: float = 1e-8,
) -> dict[tuple[str, str], float]:
    """Iterative proportional fitting (RAS / raking): reconstruct a joint (row, col) table
    from real row and column marginals, given a set of allowed (non-structural-zero) cells.
    Standard technique for exactly this problem — used e.g. in transportation
    origin-destination matrix estimation and emission inventory modelling, not invented for
    this module. Converges to the maximum-entropy table consistent with both real marginals
    and the structural zero constraints.
    """
    table = {cell: 1.0 for cell in allowed}
    for _ in range(max_iter):
        max_err = 0.0
        # row scaling: match each category's real total exactly
        for r in row_totals:
            cells = [c for c in allowed if c[0] == r]
            s = sum(table[c] for c in cells)
            target = row_totals[r]
            if s > 0 and target >= 0:
                factor = target / s
                for c in cells:
                    table[c] *= factor
                max_err = max(max_err, abs(factor - 1.0))
        # column scaling: match each fuel-type's real total exactly
        for col in col_totals:
            cells = [c for c in allowed if c[1] == col]
            s = sum(table[c] for c in cells)
            target = col_totals[col]
            if s > 0 and target >= 0:
                factor = target / s
                for c in cells:
                    table[c] *= factor
                max_err = max(max_err, abs(factor - 1.0))
        if max_err < tol:
            break
    return table


def _fuel_totals_by_rto(fuel_df: pd.DataFrame) -> pd.DataFrame:
    """Per RTO, real counts for all four fuel buckets (petrol, diesel, electric,
    other_fuel) — nothing dropped before this point, unlike the earlier independence
    version which discarded non-petrol/diesel/electric mass before the estimate."""
    df = fuel_df.copy()
    df["bucket"] = df["fuel_type"].map(lambda f: _FUEL_BUCKET.get(f, "other_fuel"))
    totals = df.groupby(["rto_code", "bucket"])["vehicle_count"].sum().unstack(fill_value=0.0)
    for col in _FUELS:
        if col not in totals.columns:
            totals[col] = 0.0
    return totals[list(_FUELS)]


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
    totals = covered.groupby(["rto_code", "bucket"])["vehicle_count"].sum().unstack(fill_value=0.0)
    for col in _CATEGORIES:
        if col not in totals.columns:
            totals[col] = 0.0
    return totals[list(_CATEGORIES)]


def estimate_by_rto() -> pd.DataFrame:
    """Real VAHAN counts, combined into (rto_code, vehicle_category, fuel_type, vehicle_count)
    via IPF with structural zeros (see module docstring). Returns the same shape
    registrations.load_by_rto() would, before zone aggregation. Includes "other_fuel" rows
    (real counts, no cited emission factor — excluded downstream in index.compute(), not
    here) so their real magnitude is visible rather than silently pre-filtered.
    """
    fuel_df, category_df = _load_raw()
    fuel_totals = _fuel_totals_by_rto(fuel_df)
    cat_totals = _category_totals_by_rto(category_df)

    citation_fuel = fuel_df["source_citation"].iloc[0]
    citation_cat = category_df["source_citation"].iloc[0]
    period = fuel_df["data_period"].iloc[0]

    rows = []
    for rto_code in cat_totals.index:
        row_totals = {cat: float(cat_totals.loc[rto_code, cat]) for cat in _CATEGORIES}
        col_totals = {fuel: float(fuel_totals.loc[rto_code, fuel]) if rto_code in fuel_totals.index else 0.0
                      for fuel in _FUELS}
        if sum(row_totals.values()) <= 0:
            continue

        joint = _ipf_joint(row_totals, col_totals, _ALLOWED_CELLS)

        for (cat, fuel), count in joint.items():
            if count <= 0.5:  # sub-half-vehicle estimates aren't meaningful, skip
                continue
            note = (
                f" {OTHER_FUEL_BIAS_NOTE}" if fuel == "other_fuel" else ""
            )
            rows.append({
                "rto_code": rto_code, "vehicle_category": cat, "fuel_type": fuel,
                "vehicle_count": count, "data_period": period,
                "source_citation": (
                    f"REAL: {citation_cat} [{cat} total] x {citation_fuel} [{fuel} total] "
                    f"— joint estimated via iterative proportional fitting (IPF/raking) with "
                    f"structural zeros for known-impossible cells; both real marginals matched "
                    f"exactly. See real_registrations.py docstring.{note}"
                ),
            })

    return pd.DataFrame(rows)


def zone_rto_notes(known_zones: set[str] | None = None) -> dict[str, str]:
    """Per-zone disclosure text for the RTO->zone even-split allocation (fix #4) and the
    other_fuel/CNG exclusion's directional bias (fix #2), keyed by zone — passed to
    index.compute()'s zone_notes so both show up in the final coverage_note, not just an
    intermediate file few people open."""
    from collections import defaultdict
    zone_to_rtos: dict[str, list[str]] = defaultdict(list)
    for r in rto_mapping.RTOS:
        zone_to_rtos[r.zone].append(r.code)

    notes = {}
    for zone, rtos in zone_to_rtos.items():
        rto = rtos[0]  # rto_mapping guarantees exactly one nearest RTO per zone entry
        siblings = [z for z, rl in zone_to_rtos.items() if z != zone and rl[0] == rto]
        if siblings:
            notes[zone] = (
                f"RTO allocation: this zone's vehicle count is RTO {rto}'s total split EVENLY "
                f"across {len(siblings) + 1} zones ({zone}, {', '.join(siblings)}) — no "
                f"finer-grained official data exists to split it more precisely."
            )
        else:
            notes[zone] = f"RTO allocation: this zone maps 1:1 to RTO {rto} (not shared with another zone)."
        notes[zone] += f" {OTHER_FUEL_BIAS_NOTE}"
    return notes


def load_by_rto_real(known_zones: set[str] | None = None) -> pd.DataFrame:
    """Aggregate the real per-RTO IPF estimate up to AirSentinel zones via rto_mapping.py's
    documented nearest-RTO approximation (even-split-across-matched-zones rule)."""
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
