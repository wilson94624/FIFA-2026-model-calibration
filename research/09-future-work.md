# Future Work

## 研究背景

目前 Calibration Lab 已經把最重要的基礎層跑完：Elo、xG、Dixon-Coles / Gamma、PQS shadow、Domination、Score Tail、Poisson diagnostics、Margin Tail fine search。

下一階段不應急著把更多補丁塞進正式 Predictor，而是補資料、補切分、補真正能避免 double-counting 的研究設計。

## 我們當時遇到的問題

很多方向都有足球直覺，但缺少可驗證資料：

- 傷停資料缺少時間戳。
- 疲勞需要逐場賽程和延長賽資訊。
- 主場優勢在中立大賽裡不等於一般主場。
- 風格資料很難量化。
- Negative Binomial 已完成 feasibility benchmark，但不足以取代 Bivariate Poisson。
- Score tail 確實有問題，但全域修正不穩定。

## 為什麼會想到這個方法

目前 final candidate 已經有穩定骨架。未來研究應該只回答兩種問題：

1. 這個新資料是否提供 Elo/xG 沒有的新訊號？
2. 這個新修正是否能跨 split 穩定改善 LogLoss 或 Brier Score？

如果答案是否定，就算足球敘事再合理，也不應進正式 Predictor。

## 名詞解釋

Dynamic Team PQS 是未來考慮傷病、可用性、陣容深度與 expected role 的球隊狀態系統。

Availability correction layer 是球員可用性修正層，處理傷病、禁賽、未入選、出賽疑慮。

Host advantage 是主辦國或接近主場的優勢，不一定等於一般主客場。

Fatigue 是疲勞，可能來自密集賽程、旅行、延長賽、短休息。

Style benchmark 是測試球隊風格是否影響比分分布，例如高壓逼搶、防守反擊、控球。

Negative Binomial 是比 Poisson 更能處理 overdispersion 的計數分布。

Overdispersion 是資料比模型假設更分散，常表現為極端比分比 Poisson 預期更多。

Score distribution research 是比分分布研究，不只看誰贏，也看 0-0、1-1、4-0、5-1 這些比分形狀。

## 實驗設計

未來所有研究都應遵守同一個流程：

1. 先寫 data readiness report。
2. 確認沒有 look-ahead bias。
3. 先做 shadow benchmark。
4. 再做 historical benchmark。
5. 至少做 World Cup、Euro、modern era、recent era 切分。
6. 只有在 LogLoss / Brier Score 穩定改善時才考慮正式整合。

## Benchmark 結果

此章節暫無量化結果。

這章整理的是尚未完成方向，而不是已完成 benchmark。可參考的既有結論是：

- PQS raw layer 尚不能宣稱 calibration。
- Domination Layer 沒有改善 LogLoss。
- Margin Tail correction 在 split validation 不穩定。
- Score Distribution Diagnostics 建議繼續研究 fat-tail，但 formal model formulas unchanged。

## 發現了什麼

未來最有價值的不是「再加一層強弱修正」，而是找到真正不和 Elo 重疊的資料。

值得研究的方向如下：

| 方向 | 為什麼值得研究 | 目前缺少什麼資料 |
| --- | --- | --- |
| Dynamic Team PQS | 傷停、可用性與陣容深度可能是 Elo 沒有的新資訊 | 時間安全傷停、球員位置、替代者品質 |
| Availability correction layer | 可用性比 raw squad strength 更少 double-counting | reported_at、status confidence、match roster |
| Host advantage benchmark | 主辦國優勢可能影響大賽 | 主辦國、場地距離、球迷比例、半主場標記 |
| Fatigue benchmark | 短休息與延長賽可能影響表現 | 目前暫停，先做資料 readiness |
| Style benchmark | 球風可能改變總進球與尾端 | 目前暫停，缺可靠 match-level style data |
| Negative Binomial subset research | 可能處理 high-mismatch overdispersion | 已完成 feasibility；不取代 Bivariate Poisson |
| Score distribution research | 目前已知 GD>=3 被低估 | 更細比分桶、年代分布、mismatch 條件 |

## 最終結論

短期內正式 Predictor 應保持克制。final_worldcup_model_v1_candidate 已經有清楚結構：

- calibrated Elo
- calibrated neutral xG
- Dixon-Coles rho=0.05
- Gamma=0.08
- no Raw PQS
- no Domination Layer
- no global Tail Correction

未來研究的目標不是讓模型看起來更複雜，而是讓每個新增訊號都能證明自己不是重複計算。

## 下一步研究方向

優先順序建議：

1. Dynamic Team PQS / Injury / Availability Information Layer：最可能提供 Elo 沒有的新資訊。
2. Host advantage benchmark：世界盃 2026 有主辦國與地理因素，實務上重要。
3. Frozen prediction archive：讓 future shadow mode 能被嚴格驗證。
4. Fatigue data readiness：目前暫停，不做係數。
5. Style data readiness：目前暫停，不做係數。
6. Score distribution monitoring：延續 diagnostics，避免直接做不穩定全域 correction。

---

## Final Decision

最後這篇作為 5.0 research roadmap 保留。

短期 4.0 不再新增未證明模型層。5.0 的核心方向是 Dynamic Team PQS、Injury / Availability Information Layer、Shadow Mode、frozen prediction archive，以及 Host Advantage 的資料研究。

Fatigue 和 Style 目前暫停。原因是缺少可靠、time-safe、match-level data。未來可以重新研究，但不能在目前階段變成正式模型係數。
