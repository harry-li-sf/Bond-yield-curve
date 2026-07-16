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
import sys
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

import requests


SEARCHYC_URL = "https://yield.chinabond.com.cn/cbweb-mn/yc/searchYc"
SUMMARY_FILE = "summary.json"
DATA_SCHEMA_VERSION = 2
START_DATE = "2020-01-02"
SUMMARY_TERMS = ["1Y", "5Y", "10Y", "20Y", "30Y"]
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


def next_fetch_date_for_dataset(dataset: DatasetConfig, existing: dict) -> str:
    if not dataset.is_legacy_file and not has_current_metadata(dataset, existing):
        return START_DATE
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
    if start == START_DATE and not dataset.is_legacy_file and not has_current_metadata(dataset, existing):
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
    return not dates or day > dates[-1]


def update_all_datasets(today_str: str) -> Dict[str, bool]:
    states = {}
    starts = []
    for dataset in ALL_DATASETS:
        state = load_existing(dataset.filename, dataset.terms)
        start = next_fetch_date_for_dataset(dataset, state)
        if start == START_DATE and not dataset.is_legacy_file and not has_current_metadata(dataset, state):
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
        pending = [dataset for dataset in ALL_DATASETS if dataset_needs_day(states[dataset.key], day)]
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
        state["terms"] = dataset.terms
        state["meta"] = dataset.meta
        save_json(dataset.filename, state)

    return changed


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


def main():
    today_str = now_beijing().strftime("%Y-%m-%d")
    print("=" * 68)
    print("ChinaBond yield curve update: 9 curves x 2 measures")
    print(f"Beijing time: {datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 68)

    changed = update_all_datasets(today_str)
    generate_summary()

    changed_count = sum(1 for ok in changed.values() if ok)
    print("=" * 68)
    print(f"Datasets updated: {changed_count}/{len(ALL_DATASETS)}")
    print("=" * 68)
    sys.exit(0)


if __name__ == "__main__":
    main()
