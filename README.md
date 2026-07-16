# 债券收益率曲线 GitHub Pages 复刻

这是一个纯静态 GitHub Pages 站点：`index.html` 在浏览器里读取仓库根目录的 JSON 数据文件并渲染利率曲线；`.github/workflows/update-data.yml` 会用 GitHub Actions 定时运行 `ci_update.py`，抓取中债网数据并更新这些 JSON。

## 文件说明

- `index.html`：网页入口，包含总览、曲线对比、预测、历史表格和导出功能。
- `assets/`：网页依赖的 ECharts 和 XLSX，本地加载，不依赖 CDN。
- `data.json`：国债即期数据。
- `data_gov_ytm.json`：国债到期数据。
- `data_cdb.json`：国开债即期数据。
- `data_cdb_ytm.json`：国开债到期数据。
- `summary.json`：总览卡片的摘要数据。
- `ci_update.py`：GitHub Actions 自动更新数据的脚本。
- `.github/workflows/update-data.yml`：定时抓取、提交数据、部署 GitHub Pages 的工作流。

## GitHub 网页操作步骤

你已经创建了 GitHub 仓库并启用了 Pages。接下来按这个做：

1. 打开你的 GitHub 仓库页面，例如 `https://github.com/你的用户名/bone-yield-curve`。
2. 进入上方的 `Code` 页面。
3. 点击 `Add file`，再点 `Upload files`。
4. 打开电脑里的 `D:\ai\my-codex\bond-yield-curve` 文件夹，把这些内容拖进去：`.github`、`assets`、`index.html`、`ci_update.py`、`.gitignore`、`.nojekyll`、`README.md`、`requirements.txt`、`data.json`、`data_gov_ytm.json`、`data_cdb.json`、`data_cdb_ytm.json`、`summary.json`。不要上传 `example`、`.git`、`.agents`、`.codex`。
5. 页面底部 `Commit changes` 区域里，标题可以填：`replicate bond yield curve site`。
6. 点击绿色的 `Commit changes`。
7. 进入仓库上方的 `Settings`。
8. 左侧点 `Pages`。
9. 在 `Build and deployment` 里，把 `Source` 改成 `GitHub Actions`。如果你继续选择 `Deploy from a branch` 的 `main`，网页本身也能打开，但老师 README 里说的 Actions 部署模式需要选择 `GitHub Actions`。
10. 左侧点 `Actions`，再点 `General`。
11. 找到 `Workflow permissions`，选择 `Read and write permissions`。
12. 勾选 `Allow GitHub Actions to create and approve pull requests` 可以不选；本项目不需要。
13. 点击 `Save`。
14. 回到仓库上方的 `Actions`。
15. 左侧点 `每日自动更新国债利率数据并部署`。
16. 点击右侧 `Run workflow`，分支选择 `main`，再点绿色 `Run workflow`。
17. 等待这一条运行记录变成绿色对勾。
18. 回到 `Settings` -> `Pages`，页面会显示访问地址，通常是 `https://你的用户名.github.io/bone-yield-curve/`。

## 本地预览

在项目目录运行：

```bash
python -m http.server 8000
```

然后打开：

```text
http://localhost:8000/
```

不要直接双击 `index.html` 打开，因为浏览器对本地文件读取 JSON 有限制。
