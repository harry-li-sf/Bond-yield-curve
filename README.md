# 债券收益率曲线 GitHub Pages 网页

这是一个纯静态 GitHub Pages 项目。网页入口是 `index.html`，数据文件是仓库根目录下的 JSON；`.github/workflows/update-data.yml` 会定时运行 `ci_update.py`，从中国债券信息网/中债登接口更新数据并部署网页。

## 数据范围

本项目按老师文档扩展为 9 种债券曲线、2 种收益率口径，共 18 组数据：

| 曲线 | ycDefId | 最大期限 | 即期文件 | 到期文件 |
| --- | --- | ---: | --- | --- |
| 中债国债 | `2c9081e50a2f9606010a3068cae70001` | 50Y | `data.json` | `data_gov_ytm.json` |
| 中债国开债 | `8a8b2ca037a7ca910137bfaa94fa5057` | 50Y | `data_cdb.json` | `data_cdb_ytm.json` |
| 中债铁道债 | `2c9081e91b55cc84011c25e7977b4dac` | 30Y | `data_rail_spot.json` | `data_rail_ytm.json` |
| 中债企业债(AAA) | `2c9081e50a2f9606010a309f4af50111` | 30Y | `data_corp_aaa_spot.json` | `data_corp_aaa_ytm.json` |
| 中债进出口行债 | `8a8b2ca0567e033b01567ea9c1d96af8` | 20Y | `data_exim_spot.json` | `data_exim_ytm.json` |
| 中债农发行债 | `2c9081e50a2f9606010a306abdde0003` | 30Y | `data_adbc_spot.json` | `data_adbc_ytm.json` |
| 中国地方政府债 | `998183ff8c00f640018c32d4721a0d16` | 30Y | `data_local_gov_spot.json` | `data_local_gov_ytm.json` |
| 中债企业债(AA) | `2c90818812b319130112c279222836c3` | 30Y | `data_corp_aa_spot.json` | `data_corp_aa_ytm.json` |
| 中债企业债(A) | `2c9081e91e6a3313011e6d438a58000d` | 30Y | `data_corp_a_spot.json` | `data_corp_a_ytm.json` |

## 数据来源

数据源为中国债券信息网收益率曲线接口：

- 收益率曲线主页：`https://yield.chinabond.com.cn/cbweb-mn/yield_main?locale=zh_CN`
- 核心数据接口：`POST https://yield.chinabond.com.cn/cbweb-mn/yc/searchYc`
- 请求参数中 `qxll=1` 表示即期收益率，`qxll=0` 表示到期收益率。
- 脚本只保留精确整数年限点，例如 `1Y`、`2Y`、`10Y`。

地方政府债比较特殊：中债登接口对地方政府债的 `qxll=1` 和 `qxll=0` 返回值基本相同，老师文档说明其没有独立官方即期曲线。因此本项目中：

- `data_local_gov_ytm.json` 直接来自中债登 `searchYc`，`qxll=0`。
- `data_local_gov_spot.json` 用中债登地方政府债到期收益率，通过年付息平价债 bootstrap 方法推导即期收益率。
- 该方法来自 `example/README_中债收益率曲线抓取.md` 和 `example/bootstrap_spot.py`。
- 地方政府债必须单独请求；如果把它和其他 `ycDefIds` 拼成一次批量请求，中债登可能只返回地方政府债并导致其他到期曲线缺失或错位。

## 溢价评估利率

网页新增了一个独立的 `溢价评估利率` 板块，不会重新抓取基础评估曲线数据。它只读取已经生成好的 `data.json`（中债国债即期收益率曲线），再在本地派生 `life_discount.json`。

计算规则来自 `example/寿险合同负债评估折现率曲线.pdf`：

- 基础利率曲线使用中债国债即期收益率曲线的 750 日移动平均值。
- `0 < t <= 20`：直接使用 750 日移动平均国债即期收益率。
- `20 < t <= 40`：按 PDF 中的终极利率过渡公式计算，终极利率为 4.5%。
- `t > 40`：使用 4.5% 终极利率。
- 综合溢价在 20 年以内保持不变，20-40 年线性下降，40 年及以后为 0。
- 即期折现率 = 基础利率曲线 + 综合溢价。
- 远期折现率由即期折现率推导：`F_t = ((1 + S_t)^t / (1 + S_{t-1})^(t-1)) - 1`。

目前页面按业务类型显示三组溢价评估利率：

| 业务类型 | 20 年以内综合溢价 |
| --- | ---: |
| 1999年（含）之前签发的高利率保单 | 75BP |
| 万能险、投资连结险、变额年金及中短存续期产品 | 30BP |
| 其他产品 | 45BP |

## 主要文件

- `index.html`：网页主程序，展示 18 组曲线、详情页、预测、历史表格、均线和导出。
- `ci_update.py`：GitHub Actions 自动更新脚本，生成 18 个基础曲线数据 JSON、`summary.json` 和派生的 `life_discount.json`。
- `summary.json`：首页总览卡片使用的摘要数据，同时记录每组数据来源。
- `life_discount.json`：寿险合同负债评估折现率曲线数据，由 `data.json` 派生，不单独访问外部网站。
- `requirements.txt`：Actions 安装依赖，目前只需要 `requests`。
- `.github/workflows/update-data.yml`：自动抓取、提交数据并部署 GitHub Pages。
- `assets/`：网页依赖的 ECharts 和 XLSX 本地文件。
- `tests/`：更新脚本的自动化测试。

## 本地预览

在项目目录运行：

```bash
python -m http.server 8000
```

然后打开：

```text
http://localhost:8000/
```

不要直接双击 `index.html` 打开，因为浏览器会限制本地 JSON 读取。

## GitHub 更新步骤

如果你是在 GitHub 网页上手动更新，请上传或替换这些文件：

1. 打开仓库页面，进入 `Code`。
2. 逐个更新这些已有文件：`index.html`、`ci_update.py`、`README.md`、`requirements.txt`。
3. 更新 `.github/workflows/update-data.yml`：在 GitHub 文件列表打开 `.github` -> `workflows` -> `update-data.yml`，点铅笔图标，把本地同名文件内容全部替换进去。
4. 更新测试文件：`tests/test_ci_update.py` 和 `tests/test_workflow.py`。如果 GitHub 上没有对应文件，点 `Add file` -> `Create new file`，文件名填完整路径，例如 `tests/test_ci_update.py`。
5. 上传或替换 `life_discount.json`。这个文件可以让网页立刻显示“溢价评估利率”；如果不手动上传，也可以等 GitHub Actions 跑完后自动生成。
6. 不要上传 `example`、`.git`、`.agents`、`.tmp_pdf_pages`、`__pycache__`。
7. 提交标题可以写：`add premium assessment discount curves`。
8. 提交后进入仓库上方 `Actions`。
9. 左侧选择 `每日自动更新18组中债利率数据并部署`。
10. 点右侧 `Run workflow`，分支选 `main`，再点绿色 `Run workflow`。
11. 等运行记录变成绿色对勾后，打开 GitHub Pages 网页并按 `Ctrl + F5` 强制刷新。

首次运行会为新增曲线补历史数据，时间会比日常更新久。之后每天只补最新交易日，速度会快很多。
