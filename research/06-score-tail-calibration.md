# Score Tail Calibration

## 研究背景

Score tail 指的是比分分布的尾端，例如 4-0、5-1、0-4 這種不常見但重要的大比分。Margin tail 則是勝差尾端，例如 goal difference 大於等於 3。

足球模型很容易低估尾端。原因是 Poisson Distribution 會把大多數機率放在 0、1、2、3 球附近；但真實世界偶爾會出現大勝，而且這些大勝對正確比分和勝差研究很重要。

## 當時遇到的問題

`final_worldcup_model_v1_candidate` 在整體勝平負上已經比 baseline 好，但 score tail report 顯示它低估大勝。

最直覺的反應是加一個 tail correction，把 2 球勝差的一部分機率搬到 3 球以上。但這很危險：如果只因為看到歷史上有幾場 7-0、9-0 就全域放大尾端，可能會讓現代比賽過度偏向大勝。

## 為什麼會想到這個方法

本研究看到兩個訊號：

- 實際 GD>=3 rate 高於模型預測。
- favorite wins by 3+ 也高於模型預測。

所以本研究檢查兩類方法：

- diagnostic：先確認是不是真的低估尾端。
- correction：嘗試把比分分布往大勝方向挪一點。

## 名詞解釋

Score tail 是比分分布尾端，也就是低機率的大比分區域。

Margin tail 是勝差尾端，例如一隊贏 3 球以上。

GD 是 goal difference，進球差。GD>=3 表示勝差至少 3 球。

Fat Tail 是厚尾，意思是極端結果比模型預期更常出現。

Calibration 是校準。若模型說某類事件平均有 14% 機率，長期實際也應接近 14%。

Top-3 / Top-5 correct score 是實際比分是否落在模型最高機率的前三或前五個比分裡。

KL Drift 和 MAD Drift 是衡量新舊機率分布差異的指標。白話說，它們看 correction 把原本模型推離多遠。

## 實驗設計

主要結果檔案：

- `results/score_tail_calibration_report.md`
- `results/score_tail_calibration_report.json`
- `results/margin_tail_modeling_research.md`
- `results/margin_tail_modeling_research.csv`
- `results/margin_tail_fine_search.md`
- `results/margin_tail_fine_search.csv`

研究分三步：

1. 先做 tail calibration report，確認大勝是否系統性低估。
2. 測不同 margin tail correction 方法。
3. 做 split validation，看 pooled 改善是否能跨世界盃、歐洲盃、現代年份維持。

## Benchmark 結果

`results/score_tail_calibration_report.md` 顯示：

| 指標 | Actual | Predicted |
| --- | ---: | ---: |
| GD>=3 rate | 0.164103 | 0.137631 |
| Total goals>=4 rate | 0.282051 | 0.281544 |
| Favorite wins by 3+ rate | 0.140171 | 0.112465 |
| Avg total goals | 2.725641 | 2.657145 |

診斷結論：

- Systematically underestimates blowouts：True
- Systematically underestimates high-total-goals matches：False
- 推薦下一步：先研究 fat-tail score distribution diagnostics，再改公式。

`results/margin_tail_modeling_research.md` 顯示 baseline 與候選：

| Variant | LogLoss | Brier | Top-3 | Top-5 | GD>=3 Error | Fav 3+ Error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.993752 | 0.590615 | 0.335897 | 0.484615 | 0.026471 | 0.027706 |
| gd_tail_redistribution_alpha_0.10 | 0.993752 | 0.590615 | 0.339316 | 0.487179 | 0.004395 | 0.011955 |
| favorite_tail_boost_alpha_0.15 | 0.993752 | 0.590615 | 0.334188 | 0.487179 | 0.002846 | 0.004080 |
| conditional_blowout_calibration_favorite_win_prob>=0.75 | 0.993752 | 0.590615 | 0.335897 | 0.484615 | 0.025615 | 0.026849 |

pooled 結果看起來有希望：某些 tail redistribution 能大幅降低 GD>=3 error，Top-3 / Top-5 也小幅改善。

但 `results/margin_tail_fine_search.md` 的 split validation 顯示不穩定：

| Split | Matches | Best GD>=3 | alpha=0.10 GD Error Delta | alpha=0.10 Top-3 Delta |
| --- | ---: | --- | ---: | ---: |
| all_pooled | 1170 | gd_tail_redistribution_alpha_0.12 | 0.022076 | 0.003419 |
| fifa_world_cup_only | 881 | gd_tail_redistribution_alpha_0.14 | 0.022126 | 0.000000 |
| uefa_euro_only | 289 | baseline | -0.021924 | 0.013841 |
| modern_era_1990_plus | 784 | baseline | -0.022115 | 0.006378 |
| recent_era_2000_plus | 597 | baseline | -0.022168 | 0.011725 |

Recommendation：

- alpha=0.10 stable for GD calibration：False
- Top-3 / Top-5 gains are small：True
- Improvement mainly early World Cup：True
- Keep formal baseline unchanged：True

## 發現了什麼

這是一次典型「先看到問題，再否決全域修正」的研究。

為什麼原本認為有效：

- baseline 明確低估 GD>=3。
- pooled benchmark 中 tail redistribution 改善 GD calibration。
- Top-3 / Top-5 有小幅改善。

最後為什麼被否決：

- split validation 不穩定。
- UEFA Euro、modern era、recent era 的 Best GD>=3 都是 baseline。
- 改善主要來自早期世界盃，可能反映舊年代足球比分更極端。
- 現代足球不支持全域 Tail Correction。

## 最終結論

Score tail 的問題是真的存在，但全域 margin tail correction 不進正式 Predictor。

正式結論是：

- 記錄模型低估大勝。
- 保留 tail diagnostics。
- 不改 formal model formulas。
- 不做現代樣本也無法支持的全域尾端放大。

## 下一步研究方向

下一步應研究：

- 依年代分開的 tail model。
- 只針對 mismatch 或淘汰賽情境的 conditional tail。
- Negative Binomial subset monitoring：feasibility benchmark 已完成，目前不取代 Bivariate Poisson。
- score distribution research，不只看勝差，也看比分形狀。

---

## Final Decision

最後不採用 Global Tail Correction，也不採用 Conditional Tail Correction。

保留的是 score-tail diagnostics 和 2026 group-stage mismatch monitoring 的研究價值。

原因是模型確實低估 GD>=3，但 tail correction 在 split validation 不穩定，改善主要集中在部分 pooled 或早期世界盃資料。未來可以繼續監控 score tail，但正式模型公式不因這輪研究而改動。
