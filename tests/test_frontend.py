from pathlib import Path
import unittest


INDEX = Path("index.html")


class FrontendTests(unittest.TestCase):
    def test_life_discount_json_uses_cacheable_static_request(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("fetch('life_discount.json', { cache: 'force-cache' })", text)
        self.assertNotIn("life_discount.json?' + Date.now()", text)

    def test_base_section_defaults_to_government_spot_detail(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("async function showBaseSection(type)", text)
        self.assertIn("showBaseSection('gov_spot')", text)
        self.assertIn("else showBaseSection();", text)

    def test_section_toggle_is_pinned_in_header_actions(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('class="header-actions"', text)
        self.assertIn(".header-actions .section-toggle { order: 2; }", text)
        self.assertIn(".header-actions .bond-toggle { order: 1; }", text)

    def test_overview_back_button_is_hidden_from_base_detail(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn(".btn-back { display: none;", text)


if __name__ == "__main__":
    unittest.main()
