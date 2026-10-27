# 趋势动物 · A股趋势信号

每日浏览趋势动物 A股“温转热”买入候选与“立秋（温转平）”卖出信号的静态看板，自动更新并部署到 GitHub Pages。

- 买入候选：`温转热(A股)` 榜单，按 A股本地趋势相对强度 `trendStrengthLocalCurr` 从高到低排序。
- 卖出信号：`立秋(A股)` 榜单（右侧结束），实测成员绝大多数为温→平，也含少量热→平、沸→平；默认按当日涨跌幅升序，跌幅大的在前。
- 数据来源：趋势动物 API（`https://www.trendtrader.cn`），页面展示接口数据日期并标注估算费用。

> 趋势动物 API 中没有名为“温转平”的现成榜单；本项目的卖出页使用官方 `立秋(A股)` 榜单，并在页面逐只展示实际温度变化。

## 页面结构

```
docs/
  index.html    页面结构
  styles.css    样式（桌面表格 / 移动端卡片）
  app.js        数据渲染、搜索、表头排序
  data.json     每日抓取结果（由脚本生成）
scripts/
  fetch_data.py 抓取榜单成分与快照，生成 docs/data.json
config.json     榜单 tmId、请求字段与输出路径
.github/workflows/update.yml  定时抓取、提交数据并部署 Pages
```

## 本地运行

需要 Python 3.10+（仅标准库）。

1. 配置密钥，二选一：

```bash
export TRENDTRADER_API_KEY="你的密钥"
# 或在项目根目录放置 API_KEY 文件（已被 .gitignore 忽略）
```

2. 查询免费的数据更新状态：

```bash
python3 scripts/fetch_data.py --check
```

3. 抓取并生成数据：

```bash
python3 scripts/fetch_data.py --wait-minutes 0
```

4. 本地预览：

```bash
python3 -m http.server 8000 --directory docs
# 打开 http://localhost:8000
```

脚本会校验实时字段计费表中是否存在所请求字段，并输出当次估算费用。重复请求同一数据日、同一 tmId、同一字段通常命中服务端缓存，实际费用以账户账单为准。

## 部署到 GitHub Pages

以下命令以仓库名 `TrendAnimal` 为例，将 `OWNER` 替换为 GitHub 用户名。

```bash
git init
git add .
git commit -m "feat: Trend Animal A-share signal dashboard"
gh repo create OWNER/TrendAnimal --public --source=. --remote=origin --push

# 密钥只写入 GitHub Actions Secret，不进入仓库或前端
gh secret set TRENDTRADER_API_KEY --repo OWNER/TrendAnimal

# 启用 Actions 作为 Pages 发布源
gh api --method POST repos/OWNER/TrendAnimal/pages -f build_type=workflow

# 手动触发一次抓取与部署
gh workflow run update.yml --repo OWNER/TrendAnimal
```

工作流在交易日北京时间 16:10 运行，最多等待 30 分钟直到 A股数据日期更新；抓取成功后提交 `docs/data.json` 并部署 `docs/`。也可在 Actions 页面手动执行。

若使用私有仓库，GitHub Pages 需要账户支持私有仓库发布；公开仓库无需额外条件。

## 数据与计费

每次更新：

1. `getUpdateStatus`（免费）确认 A股数据日期。
2. `getComponentTicker` 获取两个榜单成分：0.1 元/次 + 组合榜单成分 0.005 元/行。
3. `getTickerSnapshot` 获取 8 个字段：`priceIndex`、`roc`、`isTrendRightSide`、`trendTemperatureCurr`、`trendTemperaturePrev`、`trendPhaseCurr`、`trendStrengthLocalCurr`、`trendStrengthLocalChange`。
4. 按公开的阶梯折扣估算：前 20 行原价，21–100 行 8 折，101–300 行 6 折。

以 2026-10-27 的 17 个买入 + 28 个卖出成员计算，估算约 **1.47 元/日**；实际金额以趋势动物账单为准。榜单 `tmId` 已固定，日常运行不需要重复调用 `searchTicker`。

修改 `config.json` 可切换榜单或字段。字段变更后脚本会用免费的 `getSnapshotColumnBilling` 校验，未知字段会直接报错，避免被静默忽略。

## 口径与边界

- “温转热”标签不只包含狭义温→热，还可能包含温→沸、平→热、首次进入右侧或右侧延续中的再次升温，是候选发现榜单，不是机械买入指令。
- “立秋”表示右侧结束，是卖出复核榜单，不代表必须立即清仓；页面如实展示每只标的的温度变化。
- 相对强度是 0–100 的 A股池内位次，不是涨跌幅，也不是上涨概率。
- 页面中的当日涨跌幅由接口 `roc` 小数比值乘以 100 计算；缺失字段显示“—”，不补值。
- A股数据未更新时，页面展示最近一次有效快照并标注数据日期，不生成当日新信号。

本页面仅用于个人观察与记录，指标和分析结果仅供参考，不构成投资建议。交易盈亏由用户自行承担。
