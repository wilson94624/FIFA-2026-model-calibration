# Injury / Availability Information Layer Design

## 研究背景

PQS shadow study 的結論不是「球員資料沒用」，而是「Raw PQS 當強弱層太容易和 Elo 重疊」。比較合理的方向是 Injury / Availability Information Layer，未來再接到 Dynamic Team PQS，也就是只在球員可用性真的改變時才調整模型。

例如一支強隊原本 Elo 很高，但比賽前主力前鋒、主力中衛、門將都不能上，這時 Elo 不會即時知道。這就是 injury-aware layer 可能有價值的地方。

## 我們當時遇到的問題

PQS 最大問題是 double-counting。強隊球員品質高，Elo 也高；弱隊球員品質低，Elo 也低。直接加 Raw PQS 常常只是在重複放大強弱差距。

但傷停和可用性比較不一樣。它不是問「這隊球員本來強不強」，而是問「今天能上場的人和正常狀態差多少」。這更可能提供 Elo 沒有的新資訊。

## 為什麼會想到這個方法

`results/pqs_data_readiness_report.md` 已經指出，未來 PQS 不應直接宣稱 calibration，而應建立時間安全資料：

- match roster
- unavailable players
- player ratings
- fatigue state

PQS QA 報告也建議：preferred future direction 是 Dynamic Team PQS / Injury / Availability adjustment，而不是 Raw PQS as main model feature。

## 名詞解釋

Injury / Availability Information Layer 是考慮傷病與可用性的資料層。它不是單純說強隊球員比較好，而是看比賽當下哪些球員不能上。

Availability correction layer 是可用性修正層。availability 指球員是否能出賽，包含傷病、禁賽、未入選、身體狀態不明。

Unavailable player 是不可用球員，例如受傷、禁賽、生病或未進入名單。

Match roster 是單場比賽的球員名單，包含先發、替補、進入大名單或未入選。

Prediction timestamp 是模型做預測的時間點。所有資料都必須在這個時間點之前已知，否則就是偷看未來。

Look-ahead bias 是使用未來資訊造成的偏誤。例如賽後才公布的傷情不能用於賽前預測。

## 實驗設計

目前此章是設計文件，尚未完成正式 benchmark。此章節暫無量化結果。

未來實驗應該這樣設計：

1. 建立 frozen team snapshot，記錄當時可用的球員能力。
2. 建立 match-level unavailable player data。
3. 確認 `reported_at <= prediction timestamp`。
4. 計算正常 PQS 與可用 PQS 的差距。
5. 只把差距轉成小幅 xG correction。
6. 和 `final_worldcup_model_v1_candidate_without_pqs` 做 shadow 比較。
7. 再做正式 historical benchmark，確認 LogLoss / Brier 是否改善。

## Benchmark 結果

此章節暫無量化結果。

目前可引用的間接結果是 PQS shadow study：

- fixtures：44
- rows：220
- can_claim_pqs_calibrated：false
- PQS vs Elo Pearson correlation：約 0.75
- Sign agreement：約 84%
- pqs_weight=0.30 太激進

這些結果支持「不要用 Raw PQS」，但尚未證明 Injury / Availability 或 Dynamic Team PQS 有效。

## 發現了什麼

目前最重要的設計原則是：PQS 只應該在提供新資訊時出手。

Raw PQS 問的是「這隊整體球員強不強」，這和 Elo 高度重疊。Dynamic Team PQS 應該問的是「今天這隊比它正常狀態少了什麼」，這比較可能是新訊號。

另一個發現是資料欄位比模型公式更重要。沒有時間安全的傷停資料，就不應做正式 benchmark。

## 最終結論

Injury / Availability 是值得研究的下一步，但目前不能進正式 Predictor。

目前應保留為設計方向：

- 不用 Raw PQS 作為主強度層。
- 只做 availability delta。
- 嚴格避免 look-ahead bias。
- 先 shadow，再 benchmark，再考慮正式整合。

## 下一步研究方向

下一步需要補資料：

- 每場比賽前的傷停名單。
- 禁賽與未入選資料。
- 預測時間點前已確認的消息來源。
- 球員位置與替代球員品質。
- 先發與替補的影響權重。
- 不同位置缺陣對 attack xG 和 defense xG 的不同影響。

---

## Final Decision

最後不採用固定 Injury Coefficient，也不把 Injury / Availability adjustment 直接放進正式 Predictor。

第一版只做 Injury / Availability Information Layer：收集、顯示、記錄傷停與可用性資訊，並在 Shadow Mode 中觀察 drift。

原因是目前沒有足夠 time-safe injury / availability data 支持正式校準。未來方向是 Dynamic Team PQS：先建立 frozen prediction、reported_at、prediction_timestamp、unavailable players 和 expected role，再證明有效後才考慮正式模型。
