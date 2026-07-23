from pathlib import Path
import unittest


WORKFLOW = Path(".github/workflows/update-data.yml")


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

    def test_frontend_only_pushes_deploy_without_data_crawl(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("id: data_mode", text)
        self.assertIn("run_data_update=true", text)
        self.assertIn("run_data_update=false", text)
        self.assertIn("steps.data_mode.outputs.run_data_update == 'true'", text)
        self.assertIn("Fetch latest yield curve data", text)


if __name__ == "__main__":
    unittest.main()
