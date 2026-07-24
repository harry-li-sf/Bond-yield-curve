#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update ChinaBond yield curve JSON files for GitHub Pages.

The site uses one JSON file per curve/measure dataset:
9 bond curves x 2 measures = 18 datasets.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

import requests


SEARCHYC_URL = "https://yield.chinabond.com.cn/cbweb-mn/yc/searchYc"
PRESET_MODEL_SOURCE_URL = "https://hh9616.github.io/preset-rate-reference-model/data/model-data.js"
SUMMARY_FILE = "summary.json"
LIFE_DISCOUNT_FILE = "life_discount.json"
PRESET_MODEL_FILE = "preset_model_data.js"
DATA_SCHEMA_VERSION = 2
LIFE_DISCOUNT_SCHEMA_VERSION = 3
START_DATE = "2020-01-02"
PREMIUM_HISTORY_START_DATE = "2013-01-01"
SUMMARY_TERMS = ["1Y", "5Y", "10Y", "20Y", "30Y"]
LIFE_TERMS = [f"{i}Y" for i in range(1, 51)]
LIFE_SPREAD_TERMS = [f"{i}Y" for i in range(1, 21)]
LIFE_MA_PERIOD = 750
LIFE_MONITOR_MA_PERIODS = [250, 750, 2500]
LIFE_MONITOR_DATASET_KEYS = ["gov_spot", "cdb_spot", "rail_spot", "corp_aaa_spot"]
LIFE_ULTIMATE_RATE = 4.5
LIFE_BENCHMARK_KEYS = ["gov_spot", "cdb_spot"]
LIFE_SHORT_SPREAD_TERM = "20Y"
LIFE_LONG_SPREAD_TERM = "50Y"
LIFE_LONG_PREMIUM_DEFAULT = "50y"
LIFE_LONG_PREMIUM_OPTIONS = [
    {"key": "40y", "name": "40年标的溢价"},
    {"key": "50y", "name": "50年标的溢价"},
    {"key": "avg_40_50", "name": "40-50年平均溢价"},
]
BJ_TZ = timezone(timedelta(hours=8))
MAX_RETRIES = 3
RETRY_DELAY = 3

SEARCHYC_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://yield.chinabond.com.cn/cbweb-mn/yield_main?locale=zh_CN",
    "Content-Type": "application/x-www-form-urlencoded",
}


@dataclass(frozen=True)
class CurveConfig:
    key: str
    display_name: str
    short_name: str
    yc_def_id: str
    max_year: int
    has_official_spot: bool = True


@dataclass(frozen=True)
class DatasetConfig:
    key: str
    curve: CurveConfig
    rate_type: str
    filename: str
    display_name: str
    source_note: str

    @property
    def terms(self) -> List[str]:
        return [f"{i}Y" for i in range(1, self.curve.max_year + 1)]

    @property
    def qxll(self) -> str:
        return "1" if self.rate_type == "spot" else "0"

    @property
    def is_bootstrapped(self) -> bool:
        return self.rate_type == "spot" and not self.curve.has_official_spot

    @property
    def meta(self) -> dict:
        return {
            "schemaVersion": DATA_SCHEMA_VERSION,
            "dataset": self.key,
            "ycDefId": self.curve.yc_def_id,
            "rateType": self.rate_type,
            "maxYear": self.curve.max_year,
        }

    @property
    def is_legacy_file(self) -> bool:
        return self.key in LEGACY_FILENAMES

    @property
    def requires_isolated_fetch(self) -> bool:
        return self.curve.key == "local_gov"


CURVES = [
    CurveConfig("gov", "中债国债", "国债", "2c9081e50a2f9606010a3068cae70001", 50),
    CurveConfig("cdb", "中债国开债", "国开债", "8a8b2ca037a7ca910137bfaa94fa5057", 50),
    CurveConfig("rail", "中债铁道债", "铁道债", "2c9081e91b55cc84011c25e7977b4dac", 30),
    CurveConfig("corp_aaa", "中债企业债(AAA)", "AAA企业债", "2c9081e50a2f9606010a309f4af50111", 30),
    CurveConfig("exim", "中债进出口行债", "进出口行债", "8a8b2ca0567e033b01567ea9c1d96af8", 20),
    CurveConfig("adbc", "中债农发行债", "农发行债", "2c9081e50a2f9606010a306abdde0003", 30),
    CurveConfig("local_gov", "中国地方政府债", "地方政府债", "998183ff8c00f640018c32d4721a0d16", 30, False),
    CurveConfig("corp_aa", "中债企业债(AA)", "AA企业债", "2c90818812b319130112c279222836c3", 30),
    CurveConfig("corp_a", "中债企业债(A)", "A企业债", "2c9081e91e6a3313011e6d438a58000d", 30),
]

LEGACY_FILENAMES = {
    "gov_spot": "data.json",
    "gov_ytm": "data_gov_ytm.json",
    "cdb_spot": "data_cdb.json",
    "cdb_ytm": "data_cdb_ytm.json",
}


def build_datasets() -> List[DatasetConfig]:
    datasets: List[DatasetConfig] = []
    for curve in CURVES:
        for rate_type, zh in [("spot", "即期"), ("ytm", "到期")]:
            key = f"{curve.key}_{rate_type}"
            filename = LEGACY_FILENAMES.get(key, f"data_{key}.json")
            if rate_type == "spot" and not curve.has_official_spot:
                source = "中债登到期收益率(qxll=0)经年付息平价债 bootstrap 推导"
            else:
                qxll = "1" if rate_type == "spot" else "0"
                source = f"中债登 searchYc 接口，ycDefIds={curve.yc_def_id}，qxll={qxll}"
            datasets.append(
                DatasetConfig(
                    key=key,
                    curve=curve,
                    rate_type=rate_type,
                    filename=filename,
                    display_name=f"{curve.display_name}{zh}",
                    source_note=source,
                )
            )
    return datasets


ALL_DATASETS = build_datasets()
DATASET_BY_KEY = {dataset.key: dataset for dataset in ALL_DATASETS}
CURVE_BY_ID = {curve.yc_def_id: curve for curve in CURVES}
LIFE_BENCHMARKS = [
    DATASET_BY_KEY[key]
    for key in LIFE_BENCHMARK_KEYS
    if key in DATASET_BY_KEY
]
LIFE_SPREAD_BONDS = [
    dataset
    for dataset in ALL_DATASETS
    if dataset.rate_type == "spot" and dataset.key not in LIFE_BENCHMARK_KEYS and dataset.curve.max_year >= 20
]


def now_beijing() -> date:
    return datetime.now(BJ_TZ).date()


def iter_weekdays(start_str: str, end_str: str) -> Iterable[str]:
    current = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_str, "%Y-%m-%d").date()
    while current <= end:
        if current.weekday() < 5:
            yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def next_fetch_date(existing: dict) -> str:
    dates = existing.get("dates") or []
    if not dates:
        return START_DATE
    return (datetime.strptime(dates[-1], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def has_current_metadata(dataset: DatasetConfig, existing: dict) -> bool:
    return existing.get("meta") == dataset.meta


def dataset_history_start(dataset: DatasetConfig) -> str:
    if dataset.key in LIFE_MONITOR_DATASET_KEYS:
        return PREMIUM_HISTORY_START_DATE
    return START_DATE


def needs_extended_history_rebuild(dataset: DatasetConfig, existing: dict) -> bool:
    dates = existing.get("dates") or []
    return dataset.key in LIFE_MONITOR_DATASET_KEYS and bool(dates) and dates[0] > PREMIUM_HISTORY_START_DATE


def next_fetch_date_for_dataset(dataset: DatasetConfig, existing: dict) -> str:
    if needs_extended_history_rebuild(dataset, existing):
        return dataset_history_start(dataset)
    if not dataset.is_legacy_file and not has_current_metadata(dataset, existing):
        return dataset_history_start(dataset)
    return next_fetch_date(existing)


def empty_dataset(dataset: DatasetConfig) -> dict:
    return {"dates": [], "terms": dataset.terms, "rows": [], "meta": dataset.meta}


def load_existing(filepath: str, terms: Optional[List[str]] = None) -> dict:
    expected_terms = terms or [f"{i}Y" for i in range(1, 51)]
    if not os.path.exists(filepath):
        return {"dates": [], "terms": expected_terms, "rows": []}
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("dates", [])
    data.setdefault("rows", [])
    data["terms"] = data.get("terms") or expected_terms
    return data


def save_json(filepath: str, data: dict):
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, filepath)


def save_text(filepath: str, text: str):
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, filepath)


def normalize_rates(series_data, max_year: int) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for point in series_data or []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        tenor, value = point[0], point[1]
        if tenor is None or value is None:
            continue
        tenor_float = float(tenor)
        if abs(tenor_float - round(tenor_float)) < 1e-6:
            year = int(round(tenor_float))
            if 1 <= year <= max_year:
                out[f"{year}Y"] = round(float(value), 8)
    return out


def bootstrap_spot_from_ytm(ytm_rates: Dict[str, float]) -> Dict[str, float]:
    spots_decimal: Dict[int, float] = {}
    years = sorted(
        int(term[:-1])
        for term, value in ytm_rates.items()
        if term.endswith("Y") and value is not None
    )

    for year in years:
        ytm_percent = ytm_rates.get(f"{year}Y")
        if ytm_percent is None:
            continue
        ytm = ytm_percent / 100.0
        coupon = 100.0 * ytm
        if year == 1:
            spots_decimal[year] = ytm
            continue

        known_coupon_pv = 0.0
        for shorter in range(1, year):
            if shorter in spots_decimal:
                known_coupon_pv += coupon / ((1.0 + spots_decimal[shorter]) ** shorter)

        final_cashflow = coupon + 100.0
        final_pv = 100.0 - known_coupon_pv
        if final_pv <= 0:
            spots_decimal[year] = ytm
        else:
            spots_decimal[year] = (final_cashflow / final_pv) ** (1.0 / year) - 1.0

    return {f"{year}Y": round(rate * 100.0, 8) for year, rate in spots_decimal.items()}


def searchyc_payload(curve_ids: List[str], qxll: str, query_date: str) -> dict:
    return {
        "xyzSelect": "txy",
        "workTimes": query_date,
        "dxbj": "0",
        "qxll": qxll,
        "yqqxN": "N",
        "yqqxK": "K",
        "ycDefIds": ",".join(curve_ids),
        "wrjxCBFlag": "0",
        "locale": "zh_CN",
    }


def fetch_searchyc_bundle(curves: List[CurveConfig], qxll: str, query_date: str) -> Dict[str, Dict[str, float]]:
    if not curves:
        return {}

    payload = searchyc_payload([curve.yc_def_id for curve in curves], qxll, query_date)
    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(SEARCHYC_URL, data=payload, headers=SEARCHYC_HEADERS, timeout=30)
            resp.raise_for_status()
            raw = resp.json()
            if not raw or not isinstance(raw, list):
                return {}

            results: Dict[str, Dict[str, float]] = {}
            requested_by_id = {curve.yc_def_id: curve for curve in curves}
            for index, item in enumerate(raw):
                returned_id = item.get("ycDefId")
                curve = requested_by_id.get(returned_id)
                if curve is None and index < len(curves):
                    curve = curves[index]
                if curve is None:
                    continue
                results[curve.key] = normalize_rates(item.get("seriesData", []), curve.max_year)
            return results
        except Exception as exc:  # pragma: no cover - exercised in GitHub Actions/network
            last_error = exc
            if attempt < MAX_RETRIES:
                print(f"  {query_date} qxll={qxll}: retry {attempt}/{MAX_RETRIES} after {exc}")
                time.sleep(RETRY_DELAY)

    print(f"  {query_date} qxll={qxll}: failed - {last_error}")
    return {}


def fetch_dataset_rates(dataset: DatasetConfig, query_date: str) -> Dict[str, float]:
    if dataset.is_bootstrapped:
        ytm = fetch_searchyc_bundle([dataset.curve], "0", query_date).get(dataset.curve.key, {})
        return bootstrap_spot_from_ytm(ytm) if ytm else {}
    return fetch_searchyc_bundle([dataset.curve], dataset.qxll, query_date).get(dataset.curve.key, {})


def row_from_rates(terms: List[str], rates: Dict[str, float]) -> List[Optional[float]]:
    return [rates.get(term) for term in terms]


def merge_rates(existing: dict, terms: List[str], rates_by_date: Dict[str, Dict[str, float]]) -> dict:
    by_date = {
        day: list(existing.get("rows", [])[index])
        for index, day in enumerate(existing.get("dates", []))
    }
    for day, rates in rates_by_date.items():
        by_date[day] = row_from_rates(terms, rates)
    dates = sorted(by_date)
    return {"dates": dates, "terms": terms, "rows": [by_date[day] for day in dates]}


def update_dataset(dataset: DatasetConfig, today_str: str) -> bool:
    existing = load_existing(dataset.filename, dataset.terms)
    start = next_fetch_date_for_dataset(dataset, existing)
    if needs_extended_history_rebuild(dataset, existing):
        existing = empty_dataset(dataset)
    if start == dataset_history_start(dataset) and not dataset.is_legacy_file and not has_current_metadata(dataset, existing):
        existing = empty_dataset(dataset)
    if start > today_str:
        return False

    fetched: Dict[str, Dict[str, float]] = {}
    for day in iter_weekdays(start, today_str):
        rates = fetch_dataset_rates(dataset, day)
        if rates:
            fetched[day] = rates
            print(f"  {dataset.display_name} {day}: {len(rates)} terms")

    if not fetched:
        return False

    output = merge_rates(existing, dataset.terms, fetched)
    output["meta"] = dataset.meta
    save_json(dataset.filename, output)
    return True


def append_dataset_day(states: Dict[str, dict], dataset: DatasetConfig, day: str, rates: Dict[str, float]):
    if not rates:
        return
    state = states[dataset.key]
    if day in state["dates"]:
        return
    state["dates"].append(day)
    state["rows"].append(row_from_rates(dataset.terms, rates))


def dataset_needs_day(state: dict, day: str) -> bool:
    dates = state.get("dates") or []
    return day not in set(dates)


def sort_dataset_state(state: dict) -> None:
    rows_by_date = {
        day: state.get("rows", [])[index]
        for index, day in enumerate(state.get("dates", []))
    }
    dates = sorted(rows_by_date)
    state["dates"] = dates
    state["rows"] = [rows_by_date[day] for day in dates]


def update_all_datasets(today_str: str) -> Dict[str, bool]:
    states = {}
    starts = []
    starts_by_key = {}
    for dataset in ALL_DATASETS:
        state = load_existing(dataset.filename, dataset.terms)
        start = next_fetch_date_for_dataset(dataset, state)
        starts_by_key[dataset.key] = start
        if start == dataset_history_start(dataset) and not dataset.is_legacy_file and not has_current_metadata(dataset, state):
            state = empty_dataset(dataset)
        states[dataset.key] = state
        if start <= today_str:
            starts.append(start)

    if not starts:
        return {dataset.key: False for dataset in ALL_DATASETS}

    changed = {dataset.key: False for dataset in ALL_DATASETS}
    start = min(starts)
    print(f"Fetch range: {start} -> {today_str}")

    for day in iter_weekdays(start, today_str):
        pending = [
            dataset
            for dataset in ALL_DATASETS
            if day >= starts_by_key[dataset.key] and dataset_needs_day(states[dataset.key], day)
        ]
        if not pending:
            continue

        spot_curves = []
        ytm_curves = []
        isolated = []
        for dataset in pending:
            if dataset.requires_isolated_fetch:
                isolated.append(dataset)
                continue
            if dataset.is_bootstrapped or dataset.rate_type == "ytm":
                if dataset.curve not in ytm_curves:
                    ytm_curves.append(dataset.curve)
            elif dataset.rate_type == "spot":
                if dataset.curve not in spot_curves:
                    spot_curves.append(dataset.curve)

        spot_results = fetch_searchyc_bundle(spot_curves, "1", day) if spot_curves else {}
        ytm_results = fetch_searchyc_bundle(ytm_curves, "0", day) if ytm_curves else {}

        for dataset in [d for d in pending if not d.requires_isolated_fetch]:
            rates: Dict[str, float] = {}
            if dataset.is_bootstrapped:
                ytm = ytm_results.get(dataset.curve.key, {})
                rates = bootstrap_spot_from_ytm(ytm) if ytm else {}
            elif dataset.rate_type == "spot":
                rates = spot_results.get(dataset.curve.key, {})
            else:
                rates = ytm_results.get(dataset.curve.key, {})

            if rates:
                append_dataset_day(states, dataset, day, rates)
                changed[dataset.key] = True
                print(f"  {day} {dataset.display_name}: {len(rates)} terms")

        isolated_cache: Dict[tuple, Dict[str, float]] = {}
        for dataset in isolated:
            cache_qxll = "0" if dataset.is_bootstrapped else dataset.qxll
            cache_key = (dataset.curve.key, cache_qxll)
            if cache_key not in isolated_cache:
                isolated_cache[cache_key] = fetch_searchyc_bundle([dataset.curve], cache_qxll, day).get(dataset.curve.key, {})
            raw_rates = isolated_cache[cache_key]
            rates = bootstrap_spot_from_ytm(raw_rates) if dataset.is_bootstrapped and raw_rates else raw_rates
            if rates:
                append_dataset_day(states, dataset, day, rates)
                changed[dataset.key] = True
                print(f"  {day} {dataset.display_name}: {len(rates)} terms")

    for dataset in ALL_DATASETS:
        state = states[dataset.key]
        sort_dataset_state(state)
        state["terms"] = dataset.terms
        state["meta"] = dataset.meta
        save_json(dataset.filename, state)

    return changed


# ================================================================
# Life insurance liability discount rate curves
# ================================================================

def build_life_base_curve(ma_rates: Dict[str, float]) -> Dict[str, float]:
    r20 = ma_rates.get("20Y")
    if r20 is None:
        return {}

    base: Dict[str, float] = {}
    for year in range(1, 51):
        term = f"{year}Y"
        if year <= 20:
            value = ma_rates.get(term)
        elif year <= 40:
            r_star = ma_rates.get(term)
            if r_star is None:
                value = None
            else:
                weight = (year - 20) / 20.0
                first_interp = r20 + (LIFE_ULTIMATE_RATE - r20) * weight
                value = first_interp * weight + r_star * (1.0 - weight)
        else:
            value = LIFE_ULTIMATE_RATE

        if value is not None:
            base[term] = round(value, 8)
    return base


def dataset_summary(dataset: DatasetConfig) -> dict:
    return {
        "key": dataset.key,
        "name": dataset.display_name,
        "shortName": dataset.curve.short_name,
        "sourceFile": dataset.filename,
        "sourceNote": dataset.source_note,
    }


def terminal_benchmark_spread(benchmark_rates: Dict[str, float], mode: str = LIFE_LONG_PREMIUM_DEFAULT) -> Optional[float]:
    short_rate = benchmark_rates.get(LIFE_SHORT_SPREAD_TERM)
    if short_rate is None:
        return None

    if mode == "40y":
        long_rate = benchmark_rates.get("40Y")
        return None if long_rate is None else float(long_rate) - float(short_rate)

    if mode == "avg_40_50":
        values = [
            benchmark_rates.get(f"{year}Y")
            for year in range(40, 51)
        ]
        if any(value is None for value in values):
            return None
        average_long_rate = sum(float(value) for value in values) / len(values)
        return average_long_rate - float(short_rate)

    long_rate = benchmark_rates.get(LIFE_LONG_SPREAD_TERM)
    return None if long_rate is None else float(long_rate) - float(short_rate)


def build_accounting_premium_curve(
    benchmark_rates: Dict[str, float],
    spread_bond_rates: Dict[str, float],
    long_premium_mode: str = LIFE_LONG_PREMIUM_DEFAULT,
) -> Dict[str, float]:
    front_spreads: Dict[int, float] = {}
    for year in range(1, 21):
        term = f"{year}Y"
        bond = spread_bond_rates.get(term)
        benchmark = benchmark_rates.get(term)
        if bond is not None and benchmark is not None:
            front_spreads[year] = float(bond) - float(benchmark)

    spread20 = front_spreads.get(20)
    spread40 = terminal_benchmark_spread(benchmark_rates, long_premium_mode)
    if spread20 is None or spread40 is None:
        return {}

    premium: Dict[str, float] = {}
    for year in range(1, 51):
        if year <= 20:
            value = front_spreads.get(year)
        elif year < 40:
            weight = (year - 20) / 20.0
            value = spread20 + (spread40 - spread20) * weight
        else:
            value = spread40
        if value is not None:
            premium[f"{year}Y"] = round(value, 8)
    return premium


def build_life_discount_spot_curve(base_curve: Dict[str, float], premium_curve: Dict[str, float]) -> Dict[str, float]:
    spot: Dict[str, float] = {}
    for year in range(1, 51):
        term = f"{year}Y"
        base = base_curve.get(term)
        premium = premium_curve.get(term)
        if base is None or premium is None:
            continue
        spot[term] = round(base + premium, 8)
    return spot


def build_forward_curve(spot_curve: Dict[str, float]) -> Dict[str, float]:
    forward: Dict[str, float] = {}
    previous_spot = None
    for year in range(1, 51):
        term = f"{year}Y"
        spot = spot_curve.get(term)
        if spot is None:
            previous_spot = None
            continue
        if year == 1 or previous_spot is None:
            value = spot
        else:
            current_discount = (1.0 + spot / 100.0) ** year
            previous_discount = (1.0 + previous_spot / 100.0) ** (year - 1)
            value = (current_discount / previous_discount - 1.0) * 100.0
        forward[term] = round(value, 8)
        previous_spot = spot
    return forward


def moving_average_rows(data: dict, period: int, terms: List[str]) -> List[tuple]:
    rows = data.get("rows", [])
    dates = data.get("dates", [])
    source_terms = data.get("terms", [])
    term_indexes = [source_terms.index(term) if term in source_terms else None for term in terms]
    sums = [0.0 for _ in terms]
    valid_counts = [0 for _ in terms]
    output = []

    for row_index, row in enumerate(rows):
        for term_index, source_index in enumerate(term_indexes):
            value = row[source_index] if source_index is not None and source_index < len(row) else None
            if value is not None:
                sums[term_index] += float(value)
                valid_counts[term_index] += 1

            old_row_index = row_index - period
            if old_row_index >= 0:
                old_row = rows[old_row_index]
                old_value = old_row[source_index] if source_index is not None and source_index < len(old_row) else None
                if old_value is not None:
                    sums[term_index] -= float(old_value)
                    valid_counts[term_index] -= 1

        if row_index >= period - 1:
            ma = {}
            for term_index, term in enumerate(terms):
                if valid_counts[term_index] == period:
                    ma[term] = round(sums[term_index] / period, 8)
            if len(ma) == len(terms):
                output.append((dates[row_index], ma))
    return output


def moving_average_map(data: dict, period: int, terms: List[str]) -> Dict[str, Dict[str, float]]:
    return {
        curve_date: ma_rates
        for curve_date, ma_rates in moving_average_rows(data, period, terms)
    }


def available_life_terms(data: dict) -> List[str]:
    source_terms = set(data.get("terms") or [])
    return [term for term in LIFE_TERMS if term in source_terms]


def build_life_discount_data(benchmark_data: Dict[str, dict], spread_bond_data: Dict[str, dict]) -> dict:
    monitor_data = {
        key: data
        for key, data in {**benchmark_data, **spread_bond_data}.items()
        if key in LIFE_MONITOR_DATASET_KEYS and data.get("dates") and data.get("rows")
    }
    benchmark_ma = {
        key: moving_average_map(data, LIFE_MA_PERIOD, LIFE_TERMS)
        for key, data in benchmark_data.items()
        if data.get("dates") and data.get("rows")
    }
    spread_bond_ma = {
        key: moving_average_map(data, LIFE_MA_PERIOD, LIFE_SPREAD_TERMS)
        for key, data in spread_bond_data.items()
        if data.get("dates") and data.get("rows")
    }
    monitor_ma = {
        str(period): {
            key: moving_average_map(data, period, available_life_terms(data))
            for key, data in monitor_data.items()
        }
        for period in LIFE_MONITOR_MA_PERIODS
    }

    if not benchmark_ma or not spread_bond_ma:
        dates: List[str] = []
    else:
        common_dates = set.intersection(
            *[set(rows) for rows in [*benchmark_ma.values(), *spread_bond_ma.values()]]
        )
        dates = sorted(common_dates)

    base_rows: Dict[str, List[List[Optional[float]]]] = {key: [] for key in benchmark_ma}
    benchmark_rows: Dict[str, List[List[Optional[float]]]] = {key: [] for key in benchmark_ma}
    spread_bond_rows: Dict[str, List[List[Optional[float]]]] = {key: [] for key in spread_bond_ma}
    monitor_rows: Dict[str, Dict[str, List[List[Optional[float]]]]] = {
        period: {key: [] for key in rows_by_key}
        for period, rows_by_key in monitor_ma.items()
    }
    usable_dates = []

    for curve_date in dates:
        bases_for_date: Dict[str, Dict[str, float]] = {}
        for key, rows_by_date in benchmark_ma.items():
            base_curve = build_life_base_curve(rows_by_date[curve_date])
            if len(base_curve) != len(LIFE_TERMS):
                break
            bases_for_date[key] = base_curve
        else:
            usable_dates.append(curve_date)
            for key, rows_by_date in benchmark_ma.items():
                benchmark_rows[key].append(row_from_rates(LIFE_TERMS, rows_by_date[curve_date]))
                base_rows[key].append(row_from_rates(LIFE_TERMS, bases_for_date[key]))
            for key, rows_by_date in spread_bond_ma.items():
                spread_bond_rows[key].append(row_from_rates(LIFE_SPREAD_TERMS, rows_by_date[curve_date]))
            for period, rows_by_key in monitor_ma.items():
                for key, rows_by_date in rows_by_key.items():
                    monitor_rows[period][key].append(row_from_rates(LIFE_TERMS, rows_by_date.get(curve_date, {})))

    benchmark_keys = [dataset.key for dataset in LIFE_BENCHMARKS if dataset.key in benchmark_ma]
    spread_bond_keys = [dataset.key for dataset in LIFE_SPREAD_BONDS if dataset.key in spread_bond_ma]

    return {
        "meta": {
            "schemaVersion": LIFE_DISCOUNT_SCHEMA_VERSION,
            "source": "derived-from-local-curve-json",
            "baseRule": "750日移动平均标的即期收益率曲线 + 20-40年二次插值至4.5%终极利率",
            "premiumRule": "前20年为选中债券即期曲线与标的即期曲线的利差；40年及以后可选标的40Y-20Y、标的50Y-20Y或标的40-50Y平均利率-20Y；20-40年线性插值",
            "forwardRule": "F_t=((1+S_t)^t/(1+S_{t-1})^(t-1))-1",
            "maPeriod": LIFE_MA_PERIOD,
            "ultimateRate": LIFE_ULTIMATE_RATE,
            "shortSpreadTerm": LIFE_SHORT_SPREAD_TERM,
            "longSpreadTerm": LIFE_LONG_SPREAD_TERM,
            "longPremiumDefault": LIFE_LONG_PREMIUM_DEFAULT,
            "longPremiumOptions": LIFE_LONG_PREMIUM_OPTIONS,
            "monitorPeriods": LIFE_MONITOR_MA_PERIODS,
            "monitorDatasetKeys": LIFE_MONITOR_DATASET_KEYS,
        },
        "dates": usable_dates,
        "terms": LIFE_TERMS,
        "spreadTerms": LIFE_SPREAD_TERMS,
        "benchmarks": [dataset_summary(DATASET_BY_KEY[key]) for key in benchmark_keys],
        "spreadBonds": [dataset_summary(DATASET_BY_KEY[key]) for key in spread_bond_keys],
        "baseRows": {key: base_rows[key] for key in benchmark_keys},
        "benchmarkRows": {key: benchmark_rows[key] for key in benchmark_keys},
        "spreadBondRows": {key: spread_bond_rows[key] for key in spread_bond_keys},
        "monitorRows": monitor_rows,
    }


def generate_life_discount_curves() -> bool:
    benchmark_data = {
        dataset.key: load_existing(dataset.filename, dataset.terms)
        for dataset in LIFE_BENCHMARKS
    }
    spread_bond_data = {
        dataset.key: load_existing(dataset.filename, dataset.terms)
        for dataset in LIFE_SPREAD_BONDS
    }
    if not any(data.get("dates") and data.get("rows") for data in spread_bond_data.values()):
        return False
    output = build_life_discount_data(benchmark_data, spread_bond_data)
    if not output["dates"]:
        return False
    save_json(LIFE_DISCOUNT_FILE, output)
    print(
        f"Life discount curves generated: {len(output['dates'])} dates, "
        f"{len(output['benchmarks'])} benchmarks, {len(output['spreadBonds'])} spread bonds"
    )
    return True


# ================================================================
# Preset rate reference model
# ================================================================

def fetch_preset_model_source() -> str:
    resp = requests.get(PRESET_MODEL_SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_preset_model_js(source: str) -> dict:
    match = re.search(r"window\.MODEL_DATA\s*=\s*(\{.*\})\s*;?\s*$", source.strip(), re.S)
    if not match:
        raise ValueError("preset model source does not contain window.MODEL_DATA")
    data = json.loads(match.group(1))
    validate_preset_model_data(data)
    return data


def validate_preset_model_data(data: dict):
    if not isinstance(data, dict):
        raise ValueError("preset model data must be an object")
    if not data.get("updatedAt"):
        raise ValueError("preset model data missing updatedAt")
    series = data.get("series")
    if not isinstance(series, list) or not series:
        raise ValueError("preset model data missing series")
    latest = series[-1]
    required_latest_fields = ["date", "liabilityAnchor", "assetBaseReturn_mean", "modelReferenceValue"]
    missing = [field for field in required_latest_fields if field not in latest]
    if missing:
        raise ValueError(f"preset model latest row missing fields: {', '.join(missing)}")
    actual_values = data.get("actualValues")
    if actual_values is not None and not isinstance(actual_values, list):
        raise ValueError("preset model actualValues must be a list")


def build_preset_model_script(data: dict) -> str:
    validate_preset_model_data(data)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return "window.PRESET_MODEL_DATA = " + payload + ";\n"


def generate_preset_model_data() -> bool:
    try:
        source = fetch_preset_model_source()
        data = parse_preset_model_js(source)
        save_text(PRESET_MODEL_FILE, build_preset_model_script(data))
        print(f"Preset rate model data updated: {len(data.get('series', []))} rows")
        return True
    except Exception as exc:
        print(f"Preset rate model data update failed: {exc}")
        return False


def generate_summary():
    summary = {
        "date": "",
        "curves": {},
        "sources": {
            dataset.key: {
                "name": dataset.display_name,
                "file": dataset.filename,
                "source": dataset.source_note,
                "ycDefId": dataset.curve.yc_def_id,
                "maxYear": dataset.curve.max_year,
            }
            for dataset in ALL_DATASETS
        },
    }
    latest_dates = []

    for dataset in ALL_DATASETS:
        data = load_existing(dataset.filename, dataset.terms)
        if not dataset.is_legacy_file and not has_current_metadata(dataset, data):
            continue
        if not data["dates"] or not data["rows"]:
            continue
        latest_date = data["dates"][-1]
        latest_row = data["rows"][-1]
        prev_row = data["rows"][-2] if len(data["rows"]) >= 2 else None
        terms_data = {}
        for term in SUMMARY_TERMS:
            if term not in data["terms"]:
                continue
            index = data["terms"].index(term)
            value = latest_row[index] if index < len(latest_row) else None
            prev_value = prev_row[index] if prev_row and index < len(prev_row) else None
            change = round(value - prev_value, 4) if value is not None and prev_value is not None else None
            terms_data[term] = {"value": value, "change": change}

        summary["curves"][dataset.key] = {
            "name": dataset.display_name,
            "date": latest_date,
            "terms": terms_data,
        }
        latest_dates.append(latest_date)

    summary["date"] = max(latest_dates) if latest_dates else ""
    save_json(SUMMARY_FILE, summary)


def generate_derived_files() -> None:
    generate_life_discount_curves()
    generate_summary()


def main():
    if "--derived-only" in sys.argv:
        print("Generating derived files from existing local data only")
        generate_derived_files()
        sys.exit(0)

    today_str = now_beijing().strftime("%Y-%m-%d")
    print("=" * 68)
    print("ChinaBond yield curve update: 9 curves x 2 measures")
    print(f"Beijing time: {datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 68)

    changed = update_all_datasets(today_str)
    generate_life_discount_curves()
    generate_preset_model_data()
    generate_summary()

    changed_count = sum(1 for ok in changed.values() if ok)
    print("=" * 68)
    print(f"Datasets updated: {changed_count}/{len(ALL_DATASETS)}")
    print("=" * 68)
    sys.exit(0)


if __name__ == "__main__":
    main()
