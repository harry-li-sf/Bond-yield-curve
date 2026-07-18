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

    def test_section_toggle_is_parallel_with_title_and_bonds_are_below_title(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('class="header-actions"', text)
        self.assertIn('<div class="header-actions">', text)
        self.assertIn('<div class="bond-toggle" id="bondToggle">', text)
        self.assertIn(".bond-toggle { grid-column: 1; grid-row: 2;", text)

    def test_base_summary_is_above_all_detail_charts(self):
        text = INDEX.read_text(encoding="utf-8")
        summary_index = text.index('id="bondSummaryCard"')
        first_grid_index = text.index('<div class="grid-2">')
        chart_index = text.index('id="curveChart"')
        self.assertLess(summary_index, first_grid_index)
        self.assertLess(summary_index, chart_index)

    def test_overview_back_button_is_hidden_from_base_detail(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn(".btn-back { display: none;", text)

    def test_tooltips_show_on_mouse_move_not_click(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("triggerOn: 'mousemove|click'", text)
        self.assertNotIn("triggerOn: 'click'", text)


if __name__ == "__main__":
    unittest.main()
