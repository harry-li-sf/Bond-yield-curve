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

    def test_life_discount_spot_adds_named_product_premium(self):
        base = {f"{year}Y": 2.0 for year in range(1, 51)}
        tier = next(t for t in ci_update.LIFE_PREMIUM_TIERS if t["key"] == "high_rate_legacy")

        spot = ci_update.build_life_discount_spot_curve(base, tier)

        self.assertEqual(tier["name"], "1999年（含）之前签发的高利率保单")
        self.assertAlmostEqual(spot["10Y"], 2.75, places=8)
        self.assertAlmostEqual(spot["30Y"], 2.375, places=8)
        self.assertAlmostEqual(spot["40Y"], 2.0, places=8)

    def test_forward_rates_are_derived_from_spot_discount_rates(self):
        spot = {"1Y": 2.0, "2Y": 3.0, "3Y": 4.0}

        forward = ci_update.build_forward_curve(spot)

        expected_2y = (((1.03 ** 2) / 1.02) - 1.0) * 100.0
        self.assertAlmostEqual(forward["1Y"], 2.0, places=8)
        self.assertAlmostEqual(forward["2Y"], expected_2y, places=8)

    def test_life_discount_data_uses_existing_gov_spot_rows_only(self):
        terms = [f"{year}Y" for year in range(1, 51)]
        rows = [[2.0 for _ in terms] for _ in range(750)]
        dates = [f"2024-01-{(i % 28) + 1:02d}" for i in range(750)]
        dates[-1] = "2026-07-15"
        gov_data = {"dates": dates, "terms": terms, "rows": rows}

        output = ci_update.build_life_discount_data(gov_data)

        self.assertEqual(output["dates"], ["2026-07-15"])
        self.assertEqual(output["terms"], terms)
        self.assertEqual(len(output["tiers"]), 3)
        self.assertIn("other_products", output["curves"])
        self.assertAlmostEqual(output["baseRows"][0][19], 2.0, places=8)
        self.assertAlmostEqual(output["baseRows"][0][39], 4.5, places=8)
        self.assertAlmostEqual(output["curves"]["other_products"]["spotRows"][0][0], 2.45, places=8)


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
