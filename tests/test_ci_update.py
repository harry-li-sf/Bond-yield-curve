import unittest
from unittest.mock import patch

import ci_update


class CurveConfigTests(unittest.TestCase):
    def test_builds_all_nine_curves_and_eighteen_datasets(self):
        curve_keys = [curve.key for curve in ci_update.CURVES]
        self.assertEqual(
            curve_keys,
            [
                "gov",
                "cdb",
                "rail",
                "corp_aaa",
                "exim",
                "adbc",
                "local_gov",
                "corp_aa",
                "corp_a",
            ],
        )

        dataset_keys = [dataset.key for dataset in ci_update.ALL_DATASETS]
        self.assertEqual(len(dataset_keys), 18)
        self.assertEqual(len(set(dataset_keys)), 18)
        self.assertIn("gov_spot", dataset_keys)
        self.assertIn("local_gov_spot", dataset_keys)
        self.assertIn("corp_a_ytm", dataset_keys)

    def test_legacy_files_are_preserved_for_existing_four_datasets(self):
        files = {dataset.key: dataset.filename for dataset in ci_update.ALL_DATASETS}
        self.assertEqual(files["gov_spot"], "data.json")
        self.assertEqual(files["cdb_spot"], "data_cdb.json")
        self.assertEqual(files["gov_ytm"], "data_gov_ytm.json")
        self.assertEqual(files["cdb_ytm"], "data_cdb_ytm.json")
        self.assertEqual(files["rail_spot"], "data_rail_spot.json")


class BootstrapTests(unittest.TestCase):
    def test_bootstraps_local_government_spot_from_ytm_curve(self):
        ytm = {"1Y": 2.0, "2Y": 3.0, "3Y": 4.0}

        spot = ci_update.bootstrap_spot_from_ytm(ytm)

        self.assertAlmostEqual(spot["1Y"], 2.0, places=8)
        self.assertGreater(spot["2Y"], ytm["2Y"])
        self.assertGreater(spot["3Y"], ytm["3Y"])
        self.assertEqual(sorted(spot.keys()), ["1Y", "2Y", "3Y"])


class LifeDiscountTests(unittest.TestCase):
    def test_life_base_curve_uses_ultimate_rate_transition(self):
        ma_rates = {f"{year}Y": 2.0 for year in range(1, 51)}

        base = ci_update.build_life_base_curve(ma_rates)

        self.assertAlmostEqual(base["20Y"], 2.0, places=8)
        self.assertAlmostEqual(base["30Y"], 2.625, places=8)
        self.assertAlmostEqual(base["40Y"], 4.5, places=8)
        self.assertAlmostEqual(base["50Y"], 4.5, places=8)

    def test_accounting_premium_curve_uses_front_spread_long_spread_and_interpolation(self):
        benchmark = {f"{year}Y": 2.0 for year in range(1, 51)}
        benchmark["50Y"] = 3.2
        spread_bond = {f"{year}Y": 2.4 for year in range(1, 21)}
        spread_bond["20Y"] = 2.8

        premium = ci_update.build_accounting_premium_curve(benchmark, spread_bond)

        self.assertAlmostEqual(premium["10Y"], 0.4, places=8)
        self.assertAlmostEqual(premium["20Y"], 0.8, places=8)
        self.assertAlmostEqual(premium["30Y"], 1.0, places=8)
        self.assertAlmostEqual(premium["40Y"], 1.2, places=8)
        self.assertAlmostEqual(premium["50Y"], 1.2, places=8)

    def test_life_discount_spot_adds_accounting_premium_curve(self):
        base = {f"{year}Y": 2.0 for year in range(1, 51)}
        premium = {f"{year}Y": 0.25 for year in range(1, 51)}

        spot = ci_update.build_life_discount_spot_curve(base, premium)

        self.assertAlmostEqual(spot["10Y"], 2.25, places=8)
        self.assertAlmostEqual(spot["30Y"], 2.25, places=8)
        self.assertAlmostEqual(spot["40Y"], 2.25, places=8)

    def test_forward_rates_are_derived_from_spot_discount_rates(self):
        spot = {"1Y": 2.0, "2Y": 3.0, "3Y": 4.0}

        forward = ci_update.build_forward_curve(spot)

        expected_2y = (((1.03 ** 2) / 1.02) - 1.0) * 100.0
        self.assertAlmostEqual(forward["1Y"], 2.0, places=8)
        self.assertAlmostEqual(forward["2Y"], expected_2y, places=8)

    def test_life_discount_data_keeps_benchmark_and_spread_rows_for_accounting_rule(self):
        terms = [f"{year}Y" for year in range(1, 51)]
        spread_terms = [f"{year}Y" for year in range(1, 21)]
        gov_rows = [[2.0 for _ in terms] for _ in range(750)]
        cdb_rows = [[2.2 for _ in terms] for _ in range(750)]
        rail_rows = [[2.5 for _ in spread_terms] for _ in range(750)]
        dates = [f"2024-01-{(i % 28) + 1:02d}" for i in range(750)]
        dates[-1] = "2026-07-15"
        benchmark_data = {
            "gov_spot": {"dates": dates, "terms": terms, "rows": gov_rows},
            "cdb_spot": {"dates": dates, "terms": terms, "rows": cdb_rows},
        }
        spread_bond_data = {
            "rail_spot": {"dates": dates, "terms": spread_terms, "rows": rail_rows},
        }

        output = ci_update.build_life_discount_data(benchmark_data, spread_bond_data)

        self.assertEqual(output["dates"], ["2026-07-15"])
        self.assertEqual(output["terms"], terms)
        self.assertEqual(output["spreadTerms"], spread_terms)
        self.assertEqual([item["key"] for item in output["benchmarks"]], ["gov_spot", "cdb_spot"])
        self.assertEqual([item["key"] for item in output["spreadBonds"]], ["rail_spot"])
        self.assertNotIn("curves", output)
        self.assertAlmostEqual(output["baseRows"]["gov_spot"][0][19], 2.0, places=8)
        self.assertAlmostEqual(output["baseRows"]["gov_spot"][0][39], 4.5, places=8)
        self.assertAlmostEqual(output["benchmarkRows"]["cdb_spot"][0][0], 2.2, places=8)
        self.assertAlmostEqual(output["spreadBondRows"]["rail_spot"][0][0], 2.5, places=8)

    def test_life_discount_data_schema_is_compact(self):
        terms = [f"{year}Y" for year in range(1, 51)]
        spread_terms = [f"{year}Y" for year in range(1, 21)]
        rows = [[2.0 for _ in terms] for _ in range(750)]
        spread_rows = [[2.4 for _ in spread_terms] for _ in range(750)]
        dates = [f"2024-01-{(i % 28) + 1:02d}" for i in range(750)]

        output = ci_update.build_life_discount_data(
            {
                "gov_spot": {"dates": dates, "terms": terms, "rows": rows},
                "cdb_spot": {"dates": dates, "terms": terms, "rows": rows},
            },
            {"rail_spot": {"dates": dates, "terms": spread_terms, "rows": spread_rows}},
        )

        self.assertEqual(output["meta"]["schemaVersion"], 3)
        self.assertEqual(
            set(output.keys()),
            {"meta", "dates", "terms", "spreadTerms", "benchmarks", "spreadBonds", "baseRows", "benchmarkRows", "spreadBondRows"},
        )


class PresetModelTests(unittest.TestCase):
    def test_parses_external_model_data_and_rewrites_global_name(self):
        source = (
            'window.MODEL_DATA = {"updatedAt":"2026-07-17T13:50:24+08:00",'
            '"series":[{"date":"2026-07-16","liabilityAnchor":2.4,'
            '"assetBaseReturn_mean":1.914127,"modelReferenceValue":1.914127}],'
            '"actualValues":[{"quarter":"2026Q2","asOfDate":"2026-03-31","value":1.93}],'
            '"warnings":[]};'
        )

        data = ci_update.parse_preset_model_js(source)
        script = ci_update.build_preset_model_script(data)

        self.assertEqual(data["updatedAt"], "2026-07-17T13:50:24+08:00")
        self.assertEqual(data["series"][0]["date"], "2026-07-16")
        self.assertTrue(script.startswith("window.PRESET_MODEL_DATA = "))
        self.assertIn('"modelReferenceValue":1.914127', script)
        self.assertNotIn("window.MODEL_DATA", script)

    def test_generate_preset_model_data_saves_valid_local_script(self):
        source = (
            'window.MODEL_DATA = {"updatedAt":"2026-07-17T13:50:24+08:00",'
            '"series":[{"date":"2026-07-16","liabilityAnchor":2.4,'
            '"assetBaseReturn_mean":1.914127,"modelReferenceValue":1.914127}],'
            '"actualValues":[],"warnings":[]};'
        )
        saved = {}

        with patch.object(ci_update, "fetch_preset_model_source", return_value=source), \
             patch.object(ci_update, "save_text", side_effect=lambda path, text: saved.update({path: text})):
            updated = ci_update.generate_preset_model_data()

        self.assertTrue(updated)
        self.assertIn(ci_update.PRESET_MODEL_FILE, saved)
        self.assertIn("window.PRESET_MODEL_DATA", saved[ci_update.PRESET_MODEL_FILE])


class UpdateTests(unittest.TestCase):
    def test_new_dataset_without_metadata_rebuilds_from_start_date(self):
        dataset = next(d for d in ci_update.ALL_DATASETS if d.key == "rail_ytm")
        old_wrong_data = {
            "dates": ["2026-07-15"],
            "terms": dataset.terms,
            "rows": [[1.224232] + [None] * (len(dataset.terms) - 1)],
        }

        fetch_start = ci_update.next_fetch_date_for_dataset(dataset, old_wrong_data)

        self.assertEqual(fetch_start, ci_update.START_DATE)

    def test_legacy_dataset_without_metadata_keeps_incremental_update(self):
        dataset = next(d for d in ci_update.ALL_DATASETS if d.key == "gov_spot")
        legacy_data = {
            "dates": ["2026-07-15"],
            "terms": dataset.terms,
            "rows": [[1.0] + [None] * (len(dataset.terms) - 1)],
        }

        fetch_start = ci_update.next_fetch_date_for_dataset(dataset, legacy_data)

        self.assertEqual(fetch_start, "2026-07-16")

    def test_update_all_fetches_local_government_separately_from_bundles(self):
        datasets = [
            next(d for d in ci_update.ALL_DATASETS if d.key == "rail_ytm"),
            next(d for d in ci_update.ALL_DATASETS if d.key == "local_gov_ytm"),
        ]
        states = {
            dataset.filename: {"dates": [], "terms": dataset.terms, "rows": [], "meta": dataset.meta}
            for dataset in datasets
        }
        calls = []
        saved = {}

        def fake_load_existing(filepath, terms=None):
            return states[filepath]

        def fake_fetch_searchyc_bundle(curves, qxll, day):
            calls.append([curve.key for curve in curves])
            return {curve.key: {"1Y": 1.0} for curve in curves}

        with patch.object(ci_update, "ALL_DATASETS", datasets), \
             patch.object(ci_update, "load_existing", side_effect=fake_load_existing), \
             patch.object(ci_update, "save_json", side_effect=lambda path, data: saved.update({path: data})), \
             patch.object(ci_update, "iter_weekdays", return_value=["2026-07-15"]), \
             patch.object(ci_update, "fetch_searchyc_bundle", side_effect=fake_fetch_searchyc_bundle):
            changed = ci_update.update_all_datasets("2026-07-15")

        self.assertIn(["rail"], calls)
        self.assertIn(["local_gov"], calls)
        self.assertNotIn(["rail", "local_gov"], calls)
        self.assertTrue(changed["rail_ytm"])
        self.assertTrue(changed["local_gov_ytm"])

    def test_update_all_bootstraps_local_government_spot_from_isolated_ytm_request(self):
        dataset = next(d for d in ci_update.ALL_DATASETS if d.key == "local_gov_spot")
        states = {
            dataset.filename: {"dates": [], "terms": dataset.terms, "rows": [], "meta": dataset.meta}
        }
        calls = []
        saved = {}

        def fake_load_existing(filepath, terms=None):
            return states[filepath]

        def fake_fetch_searchyc_bundle(curves, qxll, day):
            calls.append(([curve.key for curve in curves], qxll))
            return {"local_gov": {"1Y": 2.0, "2Y": 3.0}}

        with patch.object(ci_update, "ALL_DATASETS", [dataset]), \
             patch.object(ci_update, "load_existing", side_effect=fake_load_existing), \
             patch.object(ci_update, "save_json", side_effect=lambda path, data: saved.update({path: data})), \
             patch.object(ci_update, "iter_weekdays", return_value=["2026-07-15"]), \
             patch.object(ci_update, "fetch_searchyc_bundle", side_effect=fake_fetch_searchyc_bundle):
            changed = ci_update.update_all_datasets("2026-07-15")

        self.assertEqual(calls, [(["local_gov"], "0")])
        self.assertTrue(changed["local_gov_spot"])
        self.assertGreater(saved[dataset.filename]["rows"][0][1], 3.0)

    def test_update_all_reuses_local_government_ytm_for_spot_and_ytm(self):
        spot = next(d for d in ci_update.ALL_DATASETS if d.key == "local_gov_spot")
        ytm = next(d for d in ci_update.ALL_DATASETS if d.key == "local_gov_ytm")
        states = {
            dataset.filename: {"dates": [], "terms": dataset.terms, "rows": [], "meta": dataset.meta}
            for dataset in [spot, ytm]
        }
        calls = []

        def fake_load_existing(filepath, terms=None):
            return states[filepath]

        def fake_fetch_searchyc_bundle(curves, qxll, day):
            calls.append(([curve.key for curve in curves], qxll))
            return {"local_gov": {"1Y": 2.0, "2Y": 3.0}}

        with patch.object(ci_update, "ALL_DATASETS", [spot, ytm]), \
             patch.object(ci_update, "load_existing", side_effect=fake_load_existing), \
             patch.object(ci_update, "save_json"), \
             patch.object(ci_update, "iter_weekdays", return_value=["2026-07-15"]), \
             patch.object(ci_update, "fetch_searchyc_bundle", side_effect=fake_fetch_searchyc_bundle):
            changed = ci_update.update_all_datasets("2026-07-15")

        self.assertEqual(calls, [(["local_gov"], "0")])
        self.assertTrue(changed["local_gov_spot"])
        self.assertTrue(changed["local_gov_ytm"])

    def test_update_dataset_writes_bootstrapped_local_government_spot(self):
        dataset = next(d for d in ci_update.ALL_DATASETS if d.key == "local_gov_spot")
        existing = {"dates": [], "terms": dataset.terms, "rows": [], "meta": dataset.meta}
        fetched_ytm = {"1Y": 2.0, "2Y": 3.0, "3Y": 4.0}
        saved = {}

        with patch.object(ci_update, "load_existing", return_value=existing), \
             patch.object(ci_update, "save_json", side_effect=lambda path, data: saved.update({path: data})), \
             patch.object(ci_update, "iter_weekdays", return_value=["2026-07-15"]), \
             patch.object(ci_update, "fetch_searchyc_bundle", return_value={"local_gov": fetched_ytm}):
            updated = ci_update.update_dataset(dataset, "2026-07-15")

        self.assertTrue(updated)
        self.assertIn(dataset.filename, saved)
        output = saved[dataset.filename]
        self.assertEqual(output["dates"], ["2026-07-15"])
        self.assertEqual(output["terms"][:3], ["1Y", "2Y", "3Y"])
        self.assertEqual(output["rows"][0][0], 2.0)
        self.assertGreater(output["rows"][0][1], 3.0)


if __name__ == "__main__":
    unittest.main()
