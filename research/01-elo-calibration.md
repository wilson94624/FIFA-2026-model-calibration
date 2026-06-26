# Elo Calibration

## 研究背景

Elo 是整個模型的地基。它把一支國家隊的歷史強弱壓成一個數字，分數越高代表模型認為隊伍越強。足球預測裡，Elo 先用來判斷兩隊強弱差，再把這個差距轉成勝平負機率與預期進球數。

如果 Elo 沒校準好，後面再怎麼調 xG、比分分布或 PQS，都可能只是修補錯誤的地基。

## 當時遇到的問題

最初的 `standard_elo_v1` 太保守。它可以抓到大方向，但對強弱差距的反應不夠好，導致勝平負機率沒有校準到最好的位置。

另一個問題是國際賽資料很混雜：友誼賽、資格賽、洲際盃、世界盃，強度都不同。如果模型過度信任某些比賽的勝差，Elo 可能被少數大比分拉歪；但如果完全不看勝差，又會浪費資訊。

## 為什麼會想到這個方法

Elo 更新時通常有幾個可調參數：

- K factor：每場比賽後分數更新幅度。
- Goal difference multiplier：大勝是否應該比小勝提供更多訊號。
- Tournament weight：不同賽事是否要給不同權重。
- Home advantage：主場是否要先加一點分數。

本研究先不碰複雜球員資料，而是把這些基礎參數跑 benchmark，確認 Elo 本身能不能被校準好。

## 名詞解釋

Elo 是一種強弱評分系統。強隊贏球只會小幅加分，弱隊爆冷贏強隊會大幅加分。

K factor 是 Elo 的更新速度。K 越大，每場比賽造成的分數變動越大；K 越小，模型越保守。

Goal difference 是進球差，例如 3-1 的 goal difference 是 2。用勝差調整 Elo 的直覺是：大勝通常比險勝更能說明強弱差距。

LogLoss 是機率模型的錯誤分數。模型越自信但越錯，懲罰越重；越低越好。

Brier Score 是另一種機率錯誤分數，把預測機率和實際結果的差距平方後平均；越低越好。

Accuracy 是只看模型選出的最高機率結果有沒有猜中。它直覺好懂，但不如 LogLoss 能反映機率校準。

## 實驗設計

主要比較：

- `standard_elo_v1`
- `calibrated_elo_v2_candidate`
- `calibrated_elo_v3_candidate`

資料來源包含 FIFA + historical national teams universe。主要結果檔案：

- `results/elo_benchmark_report.csv`
- `results/time_split_validation.csv`
- `results/time_split_shrinkage_validation.csv`
- `results/k_factor_results.csv`
- `results/goal_diff_multiplier_results.csv`
- `results/gd_shrinkage_results.csv`
- `results/tournament_weight_grid_results.csv`
- `results/home_advantage_results.csv`

## Benchmark 結果

`results/elo_benchmark_report.csv` 顯示：

| 模型 | Accuracy | LogLoss | Brier Score |
| --- | ---: | ---: | ---: |
| standard_elo_v1 | 0.554349 | 0.980486 | 0.584209 |
| calibrated_elo_v2_candidate | 0.559041 | 0.946950 | 0.560776 |

這代表 calibrated Elo v2 相對 standard Elo：

- Accuracy 改善 0.004692。
- LogLoss 改善 0.033536。
- Brier Score 改善 0.023433。

`results/time_split_validation.csv` 顯示，在時間切分驗證中：

| 模型 | Validation Matches | Accuracy | LogLoss | Brier Score |
| --- | ---: | ---: | ---: | ---: |
| standard_elo_v1 | 2564 | 0.595944 | 0.926529 | 0.547440 |
| calibrated_elo_v2_candidate | 2564 | 0.597114 | 0.887639 | 0.523117 |

`results/time_split_shrinkage_validation.csv` 顯示，`calibrated_elo_v2_candidate` 的 LogLoss 最低，為 0.887639；但 `calibrated_elo_v3_shrinkage_alpha_0.4` 的 Accuracy 最高，為 0.598284。這提醒本研究：最高 Accuracy 不一定代表最好的機率校準。

`results/goal_diff_multiplier_results.csv` 顯示，`log_margin` 是最佳勝差更新形式，LogLoss 0.946950。

`results/tournament_weight_grid_results.csv` 顯示，賽事權重全為 1.0 時 LogLoss 最佳，為 0.958193。也就是說，這次沒有證據支持額外調高世界盃或洲際決賽權重。

`results/home_advantage_results.csv` 顯示，home_advantage 150 的 LogLoss 最佳，為 0.925380；home_advantage 125 的 Accuracy 最高，為 0.576453。這是值得後續研究的方向，但不是本次 final neutral World Cup candidate 的核心，因為 final benchmark 聚焦中立場。

## 發現了什麼

第一個發現是：Elo 確實值得校準。從 standard 到 calibrated 的改善不是小雜訊，尤其 LogLoss 和 Brier Score 都明顯下降。

第二個發現是：勝差資訊有用，但要用溫和的形式。`log_margin` 比完全不用勝差更好，表示大勝提供資訊；但模型仍然要避免讓極端比分過度放大。

第三個發現是：不是每個直覺都需要加權。賽事權重看起來合理，但 grid search 沒支持它。這是第一個提醒：足球直覺必須讓 benchmark 說話。

## 最終結論

Elo calibration 被保留。它是後續 xG 和 final candidate 的基礎。

目前 final candidate 使用的是 `calibrated_elo_v3_candidate`，其設定在 `results/final_worldcup_model_benchmark.json` 中記錄為：

- K factor：80
- goal_diff_shrinkage_alpha：0.1

這個版本不是單純追求最高 Accuracy，而是配合 World Cup neutral xG 和 Dixon-Coles 後，在 final benchmark 中形成最穩定的候選組合。

## 下一步研究方向

下一步可以補三件事：

- Host advantage benchmark：主場優勢在全量資料有效，但 final candidate 是中立賽，需要獨立研究主辦國優勢。
- Tournament context：賽事權重目前被否決，但可以改用更細的賽事階段或淘汰賽壓力資料。
- Elo uncertainty：對很少比賽的隊伍，Elo 可信度應該較低，未來可研究信心區間或 shrinkage。

---

## Final Decision

最後採用 calibrated Elo v3。

正式設定是 `K = 80`，goal-difference shrinkage `alpha = 0.10`。Neutral World Cup Mode 不使用 Home Advantage，Tournament Weight 維持 `1`。

沒有採用的是 calibrated Elo v2 的完整勝差放大、Tournament Weight，以及一般主場優勢直接套進中立場世界盃模式。

原因是 v3 在校準改善與 rating scale 穩定之間比較平衡。未來只在有新資料或要研究 host / semi-home advantage 時，才需要重新打開 Elo 相關研究。
