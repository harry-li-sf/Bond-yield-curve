from pathlib import Path
import unittest


INDEX = Path("index.html")
METHODOLOGY = Path("methodology.html")


class FrontendTests(unittest.TestCase):
    def test_life_discount_json_uses_cacheable_static_request(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("fetch('life_discount.json', { cache: 'force-cache' })", text)
        self.assertNotIn("life_discount.json?' + Date.now()", text)

    def test_life_discount_premium_controls_include_terminal_spread_and_premium_curve(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="lifeBenchmarkSelect"', text)
        self.assertIn('id="lifeSpreadBondSelect"', text)
        self.assertIn('id="lifeFrontPremiumSelect"', text)
        self.assertIn('id="lifeLongPremiumSelect"', text)
        self.assertIn('id="lifeCurveTypeSelect"', text)
        self.assertIn('<option value="yearly" selected>前20年逐年差额</option>', text)
        self.assertIn('<option value="10y">第10年溢价</option>', text)
        self.assertIn('<option value="20y">第20年溢价</option>', text)
        self.assertIn('<option value="avg_1_20">前20年平均溢价</option>', text)
        self.assertIn('<option value="40y">40年标的溢价</option>', text)
        self.assertIn('<option value="50y" selected>50年标的溢价</option>', text)
        self.assertIn('<option value="avg_40_50">40-50年平均</option>', text)
        self.assertIn('<option value="premium">综合溢价</option>', text)
        self.assertIn("lifeCurveType === 'premium'", text)
        self.assertIn("lifeFrontPremiumMode = this.value", text)
        self.assertIn("function lifeFrontPremiumModeName()", text)
        self.assertIn("function lifeFrontPremiumValue", text)

    def test_base_section_defaults_to_government_spot_detail(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("async function showBaseSection(type)", text)
        self.assertIn("showBaseSection('gov_spot')", text)
        self.assertIn("else showBaseSection();", text)

    def test_section_toggle_is_parallel_with_title_and_bond_selects_are_below_title(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('class="header-actions"', text)
        self.assertIn('<div class="header-actions">', text)
        self.assertIn('<div class="bond-selector" id="bondSelector">', text)
        self.assertIn('id="bondCurveSelect"', text)
        self.assertIn('id="bondRateTypeSelect"', text)
        self.assertIn(".bond-selector { grid-column: 1; grid-row: 2;", text)
        self.assertNotIn('<button class="active" data-bond="gov_spot"', text)

    def test_overview_does_not_flash_before_default_base_detail(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('<div class="view-overview" id="viewOverview" style="display:none;">', text)

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

    def test_preset_section_matches_updated_reference_layout(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="presetDetailSummary"', text)
        self.assertIn('id="presetTriggerAsOf"', text)
        self.assertIn('id="presetTriggerCurrentGap"', text)
        self.assertIn('id="presetTriggerDistance"', text)
        self.assertIn('id="presetTriggerStatus"', text)
        self.assertIn('id="presetBacktestSummary"', text)
        self.assertIn('id="presetBacktestWrap"', text)
        self.assertIn("PRESET_ORDINARY_MAX_RATE_EVENTS", text)
        self.assertIn("PRESET_TRIGGER_THRESHOLD_BP = 25", text)
        self.assertIn("renderPresetTriggerMonitor();", text)
        self.assertIn("renderPresetBacktest();", text)
        self.assertIn("普通型预定利率上限", text)
        self.assertIn("上限 - 模型预测值", text)

    def test_preset_methodology_page_is_local_and_linked(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('href="methodology.html"', text)
        self.assertIn('数据源说明', text)
        self.assertTrue(METHODOLOGY.exists())
        page = METHODOLOGY.read_text(encoding="utf-8")
        self.assertIn("公式与数据源说明", page)
        self.assertIn("预定利率研究值 = Min", page)
        self.assertIn("中债收益率曲线", page)
        self.assertIn("中国货币网 LPR", page)
        self.assertIn("普通型预定利率上限", page)


if __name__ == "__main__":
    unittest.main()
