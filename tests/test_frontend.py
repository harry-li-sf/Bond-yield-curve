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
        self.assertIn('<option value="yearly" selected>前20年逐年差额</option>', text)
        self.assertIn('<option value="10y">第10年溢价</option>', text)
        self.assertIn('<option value="20y">第20年溢价</option>', text)
        self.assertIn('<option value="avg_1_20">前20年平均溢价</option>', text)
        self.assertIn('<option value="40y">40年标的溢价</option>', text)
        self.assertIn('<option value="50y" selected>50年标的溢价</option>', text)
        self.assertIn('<option value="avg_40_50">40-50年平均</option>', text)
        self.assertIn('id="lifeCompareChart"', text)
        self.assertIn('id="lifeDiffBody"', text)
        self.assertNotIn('id="lifeCurveTypeSelect"', text)
        self.assertNotIn("lifeCurveType", text)
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

    def test_base_section_is_driven_by_selected_rate_basis(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="baseRateBasisSelect"', text)
        self.assertIn('<option value="spot" selected>即期</option>', text)
        self.assertIn('<option value="ma750">750日平均</option>', text)
        self.assertIn('<option value="ma20">20日平均</option>', text)
        self.assertIn('<option value="ma30">30日平均</option>', text)
        self.assertIn('<option value="ma60">60日平均</option>', text)
        self.assertIn("let baseRateBasis = 'spot';", text)
        self.assertIn("function getRatesForBasis", text)
        self.assertIn("function basisLabel()", text)
        self.assertIn("上年度末", text)
        self.assertIn("上季度末", text)
        self.assertIn("上月末", text)
        self.assertIn("上日", text)
        self.assertNotIn("10年750MA", text)

    def test_base_key_terms_and_curve_use_current_basis_only(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="historyDiffFromSelect"', text)
        self.assertIn('id="historyDiffToSelect"', text)
        self.assertIn('id="historyDiffHeader"', text)
        self.assertIn('id="historyDiffBody"', text)
        self.assertIn("populateCurveDateSelector", text)
        self.assertIn("getCurveSelectableDates", text)
        self.assertIn("renderHistoryDiffTable", text)
        self.assertIn("关键期限利率", text)
        self.assertIn("所选口径", text)
        self.assertNotIn("<th>750MA (%)</th>", text)
        self.assertNotIn("<th>750-上月 (bp)</th>", text)
        self.assertNotIn("<th>日期A (%)</th>", text)
        self.assertNotIn("<th>日期B (%)</th>", text)
        history_index = text.index('id="historyDiffBody"')
        forecast_index = text.index('id="forecastChart"')
        self.assertLess(history_index, forecast_index)

    def test_base_key_terms_support_custom_average_split_year(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="baseAverageSplitInput"', text)
        self.assertIn("let baseAverageSplitYear = 3;", text)
        self.assertIn("function baseAverageKeys()", text)
        self.assertIn("baseAverageSplitYear + 1", text)
        self.assertIn("renderKeyTermsTable();", text)

    def test_premium_section_is_premium_only_and_renamed(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("基础曲线", text)
        self.assertIn("对比曲线", text)
        self.assertIn('id="lifeCompareChart"', text)
        self.assertNotIn('id="lifeDiffFromSelect"', text)
        self.assertNotIn('id="lifeDiffToSelect"', text)
        self.assertIn('id="lifeDiffHeader"', text)
        self.assertIn('id="lifeDiffBody"', text)
        self.assertIn("renderLifeCompareChart", text)
        self.assertIn("renderLifeDiffTable", text)
        self.assertNotIn('id="lifeCurveTypeSelect"', text)
        self.assertNotIn("lifeCurveType", text)
        self.assertIn('id="legacyDiscountMetricSelect"', text)
        self.assertIn('id="newDiscountMetricSelect"', text)
        self.assertIn("即期折现率", text)
        self.assertIn("远期折现率", text)
        self.assertNotIn('id="lifeDownloadBtn"', text)

    def test_premium_section_has_monitor_and_discount_generation_panels(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="premiumMonitorToggle"', text)
        self.assertIn('id="premiumMonitorContent"', text)
        self.assertIn('id="premiumDiscountToggle"', text)
        self.assertIn('id="premiumDiscountContent"', text)
        self.assertIn("function togglePremiumSection", text)
        self.assertIn("premium-section.collapsed .premium-section-body", text)

    def test_premium_monitor_cards_follow_excel_requirement(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="premiumLiquidityCard"', text)
        self.assertIn('id="premiumCounterCycleCard"', text)
        self.assertIn('id="premiumLongSpreadCard"', text)
        self.assertIn('id="premiumLiquidityBody"', text)
        self.assertIn('id="premiumCounterCycleBody"', text)
        self.assertIn('id="premiumLongSpreadBody"', text)
        self.assertIn("PREMIUM_EXCEL_DEFAULTS", text)
        self.assertIn("function renderPremiumMonitor", text)
        self.assertIn("function defaultPremiumDates", text)
        self.assertIn("function projectLatestPremiumRow", text)

    def test_premium_monitor_observation_dates_are_selectable_and_liquidity_shows_all_curves(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="premiumLiquidityObservationDate1"', text)
        self.assertIn('id="premiumCounterObservationDate1"', text)
        self.assertIn('id="premiumLongObservationDate1"', text)
        self.assertNotIn('id="premiumLiquidityCurve"', text)
        self.assertIn("PREMIUM_LIQUIDITY_CURVES", text)
        self.assertIn("for (const curve of PREMIUM_LIQUIDITY_CURVES)", text)
        self.assertIn("铁道债-国债（旧准则）", text)
        self.assertIn("AAA企业债-国债（旧准则）", text)
        self.assertIn("国开债-国债（新准则）", text)

    def test_discount_generation_default_compare_date_is_prior_year_end(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("function defaultDiscountCompareDate", text)
        self.assertIn("lastYearTrade || evalDate", text)

    def test_discount_generation_uses_separate_legacy_and_new_cards(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="legacyDiscountParamsCard"', text)
        self.assertIn('id="newDiscountParamsCard"', text)
        self.assertIn('id="legacyDiscountChartCard"', text)
        self.assertIn('id="newDiscountChartCard"', text)
        self.assertIn('id="legacyDiscountTableCard"', text)
        self.assertIn('id="newDiscountTableCard"', text)
        self.assertIn('id="legacyDiscountChart"', text)
        self.assertIn('id="newDiscountChart"', text)
        self.assertIn('id="legacyDiscountMetricSelect"', text)
        self.assertIn('id="newDiscountMetricSelect"', text)
        self.assertIn("function buildDiscountGenerationRows", text)
        self.assertIn("function buildRuleBaseCurve", text)
        self.assertIn("function downloadDiscountGenerationExcel", text)

    def test_discount_generation_table_matches_excel_three_block_layout(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("function renderDiscountGenerationTable", text)
        self.assertIn("评估时点曲线", text)
        self.assertIn("对比时点曲线", text)
        self.assertIn("差异（评估-对比）单位bps", text)
        self.assertIn("基础曲线", text)
        self.assertIn("综合溢价", text)
        self.assertIn("即期折现率", text)
        self.assertIn("远期折现率", text)

    def test_ma_cards_are_available_under_premium_with_dual_curve_tables(self):
        text = INDEX.read_text(encoding="utf-8")
        premium_index = text.index('id="viewPremium"')
        ma_index = text.index('id="maTimeSeriesChart"')
        self.assertLess(premium_index, ma_index)
        self.assertIn('id="maTimeSeriesBody"', text)
        self.assertIn('id="maCurveBody"', text)
        self.assertIn("renderMATimeSeriesTable", text)
        self.assertIn("renderMACurveTable", text)
        self.assertIn("基础曲线", text)
        self.assertIn("对比曲线", text)

    def test_comparison_spacing_and_diff_cells_are_consistent(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="historyComparisonCard"', text)
        self.assertIn('class="card section-card"', text)
        self.assertIn(".section-card { margin-bottom: 20px;", text)
        self.assertIn("function formatDiffCell", text)
        self.assertGreaterEqual(text.count("formatDiffCell("), 5)
        self.assertIn("diff-col positive", text)
        self.assertIn("diff-col negative", text)

    def test_premium_ma_cards_are_aligned_and_compare_curve_is_full_term(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('class="premium-ma-grid"', text)
        self.assertIn('class="card premium-ma-card"', text)
        self.assertIn(".premium-ma-grid { display: grid;", text)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", text)
        self.assertIn(".premium-ma-card { width: 100%;", text)
        self.assertIn(".premium-ma-card .table-wrap { max-height:", text)
        self.assertIn("overflow: auto;", text)
        self.assertNotIn("premium-ma-stack", text)
        self.assertNotIn("premium-ma-content", text)
        self.assertIn("function lifeFullCompareValueAt", text)
        self.assertIn("benchmark + premium", text)
        self.assertIn("lifeFullCompareValueAt(dateIdx, term)", text)

    def test_premium_ma_curve_and_period_controls_drive_charts_and_tables(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="maCurveGroupA"', text)
        self.assertIn('id="maCurveGroupB"', text)
        self.assertIn('value="base" checked', text)
        self.assertIn('value="compare" checked', text)
        self.assertIn("let maSelectedCurves = ['base', 'compare'];", text)
        self.assertIn("let maActivePeriods = [60];", text)
        self.assertIn("function toggleMACurve", text)
        self.assertIn("function normalizeMASelection", text)
        self.assertIn("maSelectedCurves.length > 1 && maActivePeriods.length > 1", text)
        self.assertIn("function buildPremiumMASeries", text)
        self.assertIn("renderMATimeSeriesTable(seriesRows", text)
        self.assertIn("renderMACurveTable(seriesRows", text)

    def test_premium_ma_tables_use_ten_recent_dates_and_key_terms(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="maTimeSeriesEndDateSelect"', text)
        self.assertIn("const MA_TABLE_DATE_COUNT = 10;", text)
        self.assertIn("const MA_KEY_TERMS", text)
        self.assertIn("function maTimeSeriesTableDates", text)
        self.assertIn("endIdx - MA_TABLE_DATE_COUNT + 1", text)
        self.assertIn("maTimeSeriesEndDateSelect", text)
        self.assertIn("MA_KEY_TERMS.filter(term => terms.includes(term))", text)


if __name__ == "__main__":
    unittest.main()
