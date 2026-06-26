# xG Calibration

## 研究背景

Expected Goals，簡稱 xG，可以翻成「預期進球數」。在這個 repo 中，xG 不是從射門資料算出來，而是從 Elo 差距轉換出來。也就是說，本研究用兩隊強弱差去估計兩隊平均會進幾球。

比分模型的核心是 xG。只要 xG 太低，模型就會低估高比分；xG 太高，模型就會高估大比分。xG 的校準會直接影響勝平負、正確比分、大小分、勝差尾端。

## 當時遇到的問題

原始 xG 公式偏一般國際賽情境，未必適合世界盃和歐洲盃的中立場比賽。尤其 final candidate 的目標不是全世界所有比賽，而是 World Cup / Euro neutral matches。

本研究也發現 baseline_current 的平均總進球預測偏低。`results/final_worldcup_model_benchmark.json` 顯示 baseline_current 預測平均總進球是 2.560094，但實際是 2.725641。

## 為什麼會想到這個方法

如果 Elo 是「誰比較強」，xG 就是「強多少會轉成幾球」。同樣 Elo 差 200 分，可以被轉成很保守的 1.5 vs 1.0，也可以轉成更激烈的 1.8 vs 0.7。

所以本研究搜尋三個核心參數：

- base：兩隊總進球水位。
- c1：Elo 差距對 xG 差距的影響幅度。
- scale：Elo 差距被換算成 xG 時的尺度。

## 名詞解釋

Expected Goals，簡稱 xG，是模型估計一隊平均會進幾球。xG 不是保證值，而是長期平均。

Neutral match 是中立場比賽。世界盃和歐洲盃常有中立場，但主辦國、地理距離、球迷數量仍可能造成例外。

MAE 是 Mean Absolute Error，平均絕對誤差。若預測 2 球、實際 1 球，誤差是 1；把很多場平均起來就是 MAE。越低越好。

Poisson LogLoss 是用 Poisson 比分分布算出的 LogLoss。它衡量模型給實際勝平負結果的機率是否合理。

Brier Score 是機率預測的平方誤差，越低代表機率越接近實際結果。

## 實驗設計

主要分兩層：

1. 全量國際賽 xG 搜尋：看一般公式是否能改善。
2. World Cup / Euro neutral xG 搜尋：針對 final candidate 的目標場景校準。

主要結果檔案：

- `results/xg_parameter_search.csv`
- `results/elo_to_xg_benchmark.csv`
- `results/worldcup_xg_parameter_search.csv`
- `results/worldcup_xg_fine_search.csv`
- `results/worldcup_euro_xg_split_validation.csv`
- `results/neutral_xg_benchmark.csv`
- `results/final_worldcup_model_benchmark.json`

## Benchmark 結果

`results/xg_parameter_search.csv` 顯示，全量資料上最佳 Poisson LogLoss 與 Brier Score 來自：

- base_home：1.5
- base_away：1.1
- c1：1.0
- matches：48175
- Poisson LogLoss：0.921528
- Brier Score：0.544073

`results/elo_to_xg_benchmark.csv` 顯示 calibrated Elo v2 轉成 xG 後優於 standard Elo：

| 模型 | Matches | Poisson LogLoss | Brier Score | Goal Difference MAE |
| --- | ---: | ---: | ---: | ---: |
| standard_elo_v1 | 48175 | 0.980096 | 0.583968 | 1.556968 |
| calibrated_elo_v2_candidate | 48175 | 0.947134 | 0.561035 | 1.491936 |
| calibrated_elo_v3_candidate | 48175 | 0.956753 | 0.567897 | 1.512387 |

`results/worldcup_xg_fine_search.csv` 顯示，在 World Cup / Euro neutral pooled 資料上，最佳 pooled LogLoss 來自：

- base：1.5
- c1：1.3
- scale：550
- pooled LogLoss：0.993462

但 final candidate 的 xG 設定在 `results/final_worldcup_model_benchmark.json` 中是：

- base：1.35
- c1：1.3
- scale：600
- min_xg：0.2

這組在 final 組合中搭配 rho=0.05、Gamma=0.08，得到 full candidate LogLoss 0.993752。它不是單看 fine search 最低的一列，而是整體 final model benchmark 的穩定候選。

`results/final_worldcup_model_benchmark.json` 顯示 xG 層貢獻最大：

- 從 elo_only_calibrated 到 elo_xg_calibrated，LogLoss 改善 0.022159。
- Brier Score 改善 0.012736。
- Accuracy 改善 0.017094。

## 發現了什麼

xG 是 final candidate 最大的改善來源。Elo 校準讓模型知道誰比較強，但 xG 校準決定這個強弱差會怎麼映射到比分世界。

本研究也發現世界盃中立場需要自己的校準。全量國際賽最佳公式不一定直接等於 World Cup / Euro neutral 的最佳公式。

另一個重要發現是：平均總進球水位不能只看 pooled 最佳，也要看分 split 的穩定性。世界盃和歐洲盃的進球環境不完全一樣，過度追求單一 pooled 最佳可能會犧牲泛化。

## 最終結論

xG calibration 被保留，而且是 final model 最重要的改善層。

目前 final_worldcup_model_v1_candidate 採用：

- neutral xG
- base 1.35
- c1 1.3
- scale 600
- min_xg 0.2

這個設定代表：本研究不再把世界盃中立場當成一般主客場國際賽，而是用專門的中立場 xG 公式。

## 下一步研究方向

下一步應補：

- Host adjustment：主辦國或半主場是否要在 neutral xG 上另外處理。
- Tournament era split：早期世界盃和現代足球的進球環境不同，應避免一個 base 吃全部年代。
- Style-aware xG：不同球風可能改變總進球與勝差，不應只由 Elo 差距決定。

---

## Final Decision

最後採用 Neutral World Cup xG。

正式設定是 `base = 1.35`、`c1 = 1.30`、`scale = 600`、`min_xg = 0.20`。

沒有採用的是一般主客場 asymmetric xG 直接套進 World Cup neutral matches，也沒有繼續微調新的 xG 參數。

原因是這組設定在 final model benchmark 中是最大改善來源，而且目前沒有證據顯示繼續微調能帶來更穩定的結果。未來只在 host advantage、era split 或可靠 style data 出現後，再重新研究 xG extensions。
