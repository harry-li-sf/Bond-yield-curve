from pathlib import Path
import unittest


WORKFLOW = Path(".github/workflows/update-data.yml")
README = Path("README.md")


class WorkflowPushTests(unittest.TestCase):
    def test_rebases_before_pushing_action_commits(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("git pull --rebase origin main", text)

        first_pull = text.index("git pull --rebase origin main")
        first_push = text.index("git push")
        self.assertLess(first_pull, first_push)

    def test_life_discount_file_is_committed_by_workflow(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("life_discount.json", text)

    def test_preset_model_file_is_committed_by_workflow(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("preset_model_data.js", text)

    def test_makeup_weekend_audit_file_is_validated_and_committed(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("data_makeup_weekend_audit.json"), 2)
        self.assertIn(
            '[ "$f" != "data_makeup_weekend_audit.json" ]',
            text,
        )

    def test_frontend_only_pushes_deploy_without_data_crawl(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("id: data_mode", text)
        self.assertIn("run_data_update=true", text)
        self.assertIn("run_data_update=false", text)
        self.assertIn("steps.data_mode.outputs.run_data_update == 'true'", text)
        self.assertIn("Fetch latest yield curve data", text)

    def test_push_runs_derived_generation_without_network_fetch(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Generate derived files from existing data", text)
        self.assertIn("python ci_update.py --derived-only", text)
        derived_index = text.index("Generate derived files from existing data")
        fetch_index = text.index("Fetch latest yield curve data")
        self.assertLess(derived_index, fetch_index)

    def test_dependencies_are_installed_before_tests_on_push_runs(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        install_index = text.index("- name: Install dependencies")
        tests_index = text.index("- name: Run tests")
        install_block = text[install_index:tests_index]
        self.assertIn("pip install requests", install_block)
        self.assertNotIn("if: steps.data_mode.outputs.run_data_update", install_block)

    def test_readme_explains_independent_makeup_checks_for_all_eighteen_datasets(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("18组基础曲线分别核验", text)
        self.assertIn("data_makeup_weekend_audit.json", text)
        self.assertIn("2025-10-11", text)


if __name__ == "__main__":
    unittest.main()
