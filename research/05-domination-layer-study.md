# Domination Layer Study

## 研究背景

Domination Layer 的想法是：有些強隊不只比較可能贏，還可能在場面上壓制對手。這種壓制可能讓比分分布更偏向強隊小勝或大勝，也可能讓正確比分排序變好。

我們原本想測試：除了一般 xG 外，是否需要一個 domination score matrix，把強隊優勢用另一種方式混進比分分布。

## 我們當時遇到的問題

final candidate 已經用 Elo 和 xG 表達強弱差。如果再加 domination，很可能又出現和 PQS 類似的問題：同一個強弱訊號被重複放大。

但它仍值得測，因為正確比分和勝平負不完全一樣。也許 LogLoss 不一定改善，但 Top-3 或 Top-5 正確比分可能改善。

## 為什麼會想到這個方法

足球直覺上，強隊對弱隊的比賽常有兩種型態：

- 實力差距造成更高勝率。
- 場面壓制造成更多射門、更少被反擊、比分更容易往某些區域集中。

一般 xG 只給兩個平均進球數，可能不夠描述「壓制感」。Domination Layer 就是想測試這個額外形狀。

## 名詞解釋

Domination Layer 是一個研究性比分分布混合層。它不是直接改 Elo，而是把一般 score matrix 和 domination score matrix 按權重混合。

Score matrix 是比分機率表。例如 0-0、1-0、2-1 都各有一個機率。

Top-1 correct score 是模型機率最高的比分剛好命中。

Top-3 correct score 是實際比分有落在模型機率最高的前三個比分中。

Top-5 correct score 是實際比分有落在模型機率最高的前五個比分中。

LogLoss 衡量勝平負機率校準，越低越好。

Brier Score 也是勝平負機率校準指標，越低越好。

## 實驗設計

主要結果檔案：

- `results/domination_layer_benchmark.csv`
- `results/domination_layer_benchmark.json`
- `results/domination_layer_extended_benchmark.csv`
- `results/domination_layer_extended_benchmark.json`

資料範圍：

- FIFA World Cup + UEFA Euro neutral matches
- matches：1170

測試方式：

- normal_weight 從 1.0 降到 0.5
- domination_weight 從 0.0 升到 0.5
- 比較 Accuracy、LogLoss、Brier Score、Top-1、Top-3、Top-5、勝差命中、blowout detection

## Benchmark 結果

`results/domination_layer_benchmark.csv` 顯示：

| normal_weight | domination_weight | LogLoss | Brier Score | Top-1 比分 |
| ---: | ---: | ---: | ---: | ---: |
| 1.0 | 0.0 | 0.993752 | 0.590615 | 0.127350 |
| 0.9 | 0.1 | 0.993971 | 0.590638 | 0.129060 |
| 0.8 | 0.2 | 0.994205 | 0.590665 | 0.129060 |
| 0.5 | 0.5 | 0.994999 | 0.590758 | 0.130769 |

最佳 LogLoss 和 Brier Score 都是 domination_weight=0，也就是不啟用 domination。

`results/domination_layer_extended_benchmark.csv` 顯示：

- Top-3 最佳是 domination_weight=0.2，Top-3 = 0.336752。
- Baseline Top-3 是 0.335897。
- Top-5 最佳是 domination_weight=0.1 或 0.2，Top-5 = 0.485470。
- Baseline Top-5 是 0.484615。

這些 Top-3 / Top-5 改善非常小，而且 LogLoss 變差。

## 發現了什麼

Domination Layer 的失敗很有價值。它證明「比分排序稍微變好」不代表「機率模型更好」。

為什麼原本認為有效：

- 強隊壓制弱隊是合理足球直覺。
- Top-3、Top-5 正確比分可能需要比分分布形狀修正。
- 大賽中強弱差距可能比一般比賽更明顯。

最後為什麼被否決：

- LogLoss 最佳是 domination_weight=0。
- Brier Score 最佳也是 domination_weight=0。
- Top-3 / Top-5 改善很小，不足以抵銷勝平負機率校準變差。
- 它可能和 Elo/xG 重疊，變成另一種強弱放大器。

## 最終結論

Domination Layer 不進正式 Predictor。

正式模型維持：

- domination disabled
- 100% normal xG

這個結論比「加一層看起來更聰明的模型」更重要。因為 final candidate 需要的是可靠機率，不是更像足球評論的敘事。

## 下一步研究方向

Domination 不應以全域權重進正式模型，但可以改成更窄的研究：

- 只在極端 mismatch 測試。
- 只研究 Top-3 / Top-5 正確比分，不影響勝平負正式機率。
- 改用 style 或 pressing data，而不是用 Elo 差距再推一次 domination。
- 檢查 domination 是否只在早期世界盃有效，現代足球可能不穩定。

---

## Final Decision

最後不採用 Domination Layer。

正式模型維持 domination disabled，也就是 100% normal xG score matrix。

原因是 Domination 只讓部分 Correct Score ranking 有極小改善，卻傷害 LogLoss 和 Brier。未來如果還研究類似概念，只能放在 score-betting-only shadow experiment 或 style-data research，不能進正式勝平負機率模型。
