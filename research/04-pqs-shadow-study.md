# Raw PQS Shadow Study

## 研究背景

Raw PQS 是把球員品質整理成球隊強度修正的想法。它想補足 Elo 的盲點：Elo 看的是球隊歷史結果，但足球比賽是球員上場踢的。如果一隊多名主力受傷，歷史 Elo 可能太樂觀；如果一隊新世代球員變強，Elo 可能反應太慢。

這個想法很有足球直覺，所以本研究做了 PQS shadow benchmark。但 shadow 的意思是「影子測試」：只觀察如果加上 PQS，xG 和勝平負機率會漂移多少，不宣稱它真的提升預測。

## 當時遇到的問題

最大問題是資料時間安全。不能拿 2026 的球員資料去驗證 2024 或更早的比賽，否則就會有 look-ahead bias，也就是偷看未來。

第二個問題是 PQS 和 Elo 可能高度重疊。強隊通常球員也強，所以 PQS 很容易只是把 Elo 已經知道的事情再算一次。這叫 double-counting risk，中文可以理解成「同一個訊號算兩遍」。

## 為什麼會想到這個方法

本研究原本認為 PQS 有機會補到 Elo 補不到的地方：

- 球員受傷或禁賽。
- 替補深度不足。
- 新球員還沒完全反映在國家隊戰績。
- 強隊短期陣容崩壞。

因此本研究先不把 PQS 放進正式 Predictor，而是讓它成為 additive xG shadow layer，觀察它會把 baseline xG 推到哪裡。

## 名詞解釋

Raw PQS 是球員品質分數的直接用法。它把先發、替補或球員能力資料整理成一個可用於模型的 team-strength adjustment。

Shadow benchmark 是影子 benchmark。它不改正式模型，只記錄如果啟用某個研究層，預測會怎麼變。

Look-ahead bias 是偷看未來資料。例子是用比賽後才知道的傷病資訊去預測比賽前的結果。

Double-counting 是重複計算同一個訊號。若 Elo 已經反映強隊長期戰績，而 PQS 又因強隊球員好再加分，模型可能過度偏向強隊。

Pearson correlation 是衡量兩組數字線性關係的指標。越接近 1 代表越同向重疊。

W/D/L 是 Win / Draw / Loss，也就是勝、平、敗。

## 實驗設計

主要結果檔案：

- `results/pqs_data_readiness_report.md`
- `results/pqs_shadow_benchmark.json`
- `results/pqs_shadow_benchmark.csv`
- `results/pqs_shadow_qa_report.md`
- `results/pqs_shadow_qa_report.json`

PQS shadow benchmark 使用：

- baseline：`final_worldcup_model_v1_candidate_without_pqs`
- fixture 數：44
- rows：220
- PQS weights：0.00、0.10、0.20、0.25、0.30
- mode：shadow additive xG layer

PQS 資料 readiness 報告定義了未來需要的 schema：

- team snapshot
- player ratings
- team name mapping
- match roster
- unavailable players
- fatigue state

## Benchmark 結果

`results/pqs_shadow_benchmark.json` 的 summary 顯示：

- fixtures：44
- rows：220
- missing_pqs_matches：0
- can_claim_pqs_calibrated：false
- outputs_accuracy_claim：false

也就是說，這次 shadow benchmark 可以產生 drift 報告，但不能宣稱 PQS 已校準，也不能宣稱它改善 accuracy。

`results/pqs_shadow_qa_report.md` 顯示：

- PQS vs Elo Pearson correlation：約 0.75。
- Sign agreement：約 84%。
- `pqs_weight=0.30` 被視為對 raw squad-quality adjustment 太激進。

最大漂移案例包含：

| 比賽 | Baseline W/D/L | PQS W/D/L | 判讀 |
| --- | --- | --- | --- |
| France vs Iraq | 0.767944 / 0.164414 / 0.067642 | 0.844382 / 0.126706 / 0.028912 | 方向合理，但 double-counting risk 高 |
| Brazil vs Haiti | 0.801229 / 0.148750 / 0.050020 | 0.863538 / 0.115090 / 0.021373 | 方向合理，但像是在放大既有 mismatch |
| Jordan vs Algeria | 0.182227 / 0.226844 / 0.590929 | 0.125885 / 0.204216 / 0.669899 | 方向合理，仍需檢查過度懲罰 |
| Belgium vs Iran | 0.513382 / 0.243550 / 0.243068 | 0.600557 / 0.223509 / 0.175935 | 可能合理但偏激進 |

## 發現了什麼

PQS 的足球直覺是對的，但作為 raw squad-quality layer 風險很高。

最大失敗點是：PQS 與 Elo 高度重疊。強隊通常已有高 Elo，也有高 PQS；弱隊通常已有低 Elo，也有低 PQS。若直接加 PQS，常見結果不是補新資訊，而是把強弱差距放大。

QA 報告中特別指出 France vs Iraq、Brazil vs Haiti、Belgium vs Iran 是 suspicious / likely double-counting cases。這些案例看起來合理，但正因為太合理，反而可能只是重複計算。

## 最終結論

PQS 不進正式 Predictor。

目前結論是：

- 可以保留 PQS shadow framework。
- 不能宣稱 PQS calibration 完成。
- 不能宣稱 PQS 改善預測。
- Raw PQS weight 0.30 太激進。
- 未來方向應該是 Dynamic Team PQS 與 Injury / Availability Information Layer，而不是把球員品質當成主模型強度層。

## 下一步研究方向

下一步應該做 Dynamic Team PQS / Injury / Availability Shadow Mode：

- 只在球員不可用時修正。
- 使用 match-level unavailable player data。
- 確保 `reported_at <= prediction timestamp`，避免偷看未來。
- 設計 cap，避免單場 xG 被 PQS 拉太多。
- 分開處理先發、替補、位置、攻守影響。

---

## Final Decision

最後不採用 Raw PQS 作為正式 Team Strength Feature。

保留的是 PQS shadow framework、資料 schema、QA 報告，以及未來 Dynamic Team PQS 的基礎資料方向。

原因是 Raw PQS 與 Elo 高度重疊，容易 double counting。未來會把 PQS 改成 Dynamic Team PQS：只在 injury、availability、depth、expected role 發生變化時，作為 Shadow Mode 研究，不直接修改正式模型。
