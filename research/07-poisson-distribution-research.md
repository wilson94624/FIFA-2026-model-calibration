# Poisson Distribution Research

## 研究背景

Poisson Distribution 是目前比分模型的核心。給定兩隊 xG 後，它會算出每隊進 0、1、2、3 球的機率，再組合成完整比分表。

這章研究的是：現在的 Poisson score matrix 有沒有結構性問題？如果有，問題是來自 score grid 截斷、xG 水位、還是分布形狀本身？

## 當時遇到的問題

模型低估 GD>=3，但不一定代表 Poisson 完全錯了。可能只是 score matrix 最高只算到 MAX_GOALS=5，導致 6-0、7-2、9-0 這類比分被截掉。

所以本研究先問一個更小的問題：把 MAX_GOALS 提高，會不會自然修好尾端？

## 為什麼會想到這個方法

如果問題只是 grid 太小，那解法很簡單：把 MAX_GOALS 從 5 提到 8 或 10。但如果提高 MAX_GOALS 只改善很小，真正問題就不是截斷，而是 xG 差距或分布形狀。

這也是為什麼本研究先做 diagnostics，而不是直接換 Negative Binomial。

## 名詞解釋

Poisson Distribution 是用來描述計數事件的機率分布。在足球中，它估計一隊進 0 球、1 球、2 球等的機率。

MAX_GOALS 是 score matrix 算到幾球為止。如果 MAX_GOALS=5，模型會列出 0 到 5 球，但 6 球以上比分會落在表格外。

Missing tail mass 是被 score grid 截掉的機率質量。白話說，就是模型其實認為 6 球以上有一點機率，但目前表格沒有顯示。

Negative Binomial 是另一種計數分布。它比 Poisson 更能處理資料比預期更分散的情況。

Overdispersion 是資料比模型假設更分散。例如 Poisson 預期極端比分很少，但真實極端比分比較多。

Fat Tail 是厚尾，也就是極端結果比一般分布預測更常見。

LogLoss、Brier Score、Top-1、Top-3、Top-5 都是 benchmark 指標。LogLoss 與 Brier Score 越低越好；Top-k 越高越好。

## 實驗設計

主要結果檔案：

- `results/score_distribution_diagnostics.md`
- `results/score_distribution_diagnostics.json`
- `results/score_tail_calibration_report.md`
- `results/margin_tail_modeling_research.md`
- `results/margin_tail_fine_search.md`

實驗分成：

1. MAX_GOALS sensitivity：測 5、6、7、8、10。
2. Goal-difference tail：比較 GD=0、GD=1、GD=2、GD>=3。
3. Favorite margin：比較熱門方贏 1 球、2 球、3 球以上。
4. Scoreline comparison：比較模型最常預測比分與實際比分。

## Benchmark 結果

`results/score_distribution_diagnostics.md` 顯示 MAX_GOALS sensitivity：

| MAX_GOALS | LogLoss | Brier | Top-1 | Top-3 | Top-5 | GD>=3 Prob | Missing Tail Mass |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 0.993752 | 0.590615 | 0.127350 | 0.335897 | 0.484615 | 0.137631 | 0.009431 |
| 6 | 0.993691 | 0.590515 | 0.127350 | 0.335897 | 0.484615 | 0.143195 | 0.002498 |
| 7 | 0.993684 | 0.590491 | 0.127350 | 0.335897 | 0.484615 | 0.144581 | 0.000791 |
| 8 | 0.993686 | 0.590487 | 0.127350 | 0.335897 | 0.484615 | 0.144887 | 0.000410 |
| 10 | 0.993687 | 0.590486 | 0.127350 | 0.335897 | 0.484615 | 0.144960 | 0.000318 |

提高 MAX_GOALS 讓 GD>=3 probability 從 0.137631 增加到 0.144960，但實際 GD>=3 rate 是 0.164103。也就是說，截斷只解釋一部分問題。

Goal-difference tail：

| Bucket | Actual Rate | Predicted Probability | Actual - Predicted |
| --- | ---: | ---: | ---: |
| GD=0 | 0.241026 | 0.236890 | 0.004136 |
| GD=1 | 0.400855 | 0.404715 | -0.003860 |
| GD=2 | 0.194017 | 0.220764 | -0.026747 |
| GD>=3 | 0.164103 | 0.137631 | 0.026471 |

Favorite margin：

| Bucket | Actual Rate | Predicted Probability | Actual - Predicted |
| --- | ---: | ---: | ---: |
| favorite_win_by_1 | 0.250427 | 0.247150 | 0.003277 |
| favorite_win_by_2 | 0.141880 | 0.157503 | -0.015622 |
| favorite_win_by_3_plus | 0.140171 | 0.112465 | 0.027706 |

Truncation：

- 6+ goals by either team：0.027350
- 7+ goals by either team：0.012821
- 8+ goals by either team：0.005983
- Exact scores outside MAX_GOALS=5：0.027350

`results/negative_binomial_feasibility_benchmark.md` 後續補上了 Negative Binomial feasibility benchmark。結論是：Negative Binomial 對 high-mismatch 子集有研究價值，但 pooled LogLoss、Brier、Top-3 表現不足以支持取代 Bivariate Poisson。

## 發現了什麼

提高 MAX_GOALS 對 W/D/L 指標幫助很小。LogLoss 從 0.993752 到 0.993687，只改善約 0.000065；Top-1、Top-3、Top-5 都沒有變。

但提高 MAX_GOALS 對 exact-score diagnostics 有幫助，因為 MAX_GOALS=5 會讓任何一隊進 6 球以上的實際比分不可能被命中。

最重要的結論是：主要 GD>=3 低估原因不是 grid truncation，而是 xG difference / score-distribution shape。

## 最終結論

Poisson 目前仍保留為正式模型的比分分布核心。

正式公式不變。原因是：

- MAX_GOALS 提高不能完全解決 tail 問題。
- Negative Binomial 沒有在 pooled validation 上證明優於 Bivariate Poisson。
- 全域 tail correction 在 split validation 不穩定。

目前較穩妥的做法是保留 diagnostics，未來再用更嚴謹的分布研究決定是否替換 Poisson。

## 下一步研究方向

下一步應做：

- Negative Binomial subset monitoring，不取代 Bivariate Poisson。
- 分年代檢查 overdispersion。
- 分賽事檢查 fat tail 是否只在早期世界盃明顯。
- 檢查 xG 差距是否被壓縮，導致強弱懸殊比賽不夠極端。
- 若要提高 MAX_GOALS，先限定在 exact-score diagnostics，而非正式 W/D/L 指標。

---

## Final Decision

最後維持 Bivariate Poisson 作為正式 score distribution baseline。

沒有採用 Negative Binomial，也沒有因為 MAX_GOALS diagnostics 修改正式 W/D/L 模型。

原因是 MAX_GOALS 截斷只解釋一部分 tail 問題；Negative Binomial 雖然在部分 high-mismatch cases 有改善，但整體 pooled LogLoss、Brier 和 Top-3 不夠好。未來 Negative Binomial 只保留為 subset research，不取代正式模型。
