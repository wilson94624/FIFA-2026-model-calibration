# Dixon-Coles 與 Gamma Tuning

## 研究背景

Poisson Distribution 常被用來產生足球比分機率。做法是先估兩隊 xG，再計算 0-0、1-0、2-1 等比分的機率。

但足球比分有一個麻煩：兩隊進球不一定完全獨立，而且低比分特別敏感。0-0、1-0、0-1、1-1 這些比分對勝平負機率有很大影響。因此本研究檢查 Dixon-Coles rho 和 Gamma。

## 當時遇到的問題

純 Poisson 假設兩隊進球相對獨立，但足球比賽常有共同節奏。慢節奏比賽可能讓兩隊都少進球；開放比賽可能讓兩隊都有更多機會。

另一方面，低比分是足球模型的高風險區。只要 0-0 或 1-1 機率錯一點，draw probability 就會偏掉，進而影響 LogLoss。

## 為什麼會想到這個方法

Dixon-Coles 是足球比分建模中常見的低比分修正。它不是重做整個模型，而是在低比分區域修正 Poisson 的機率。

Gamma 則是在本 repo 的雙變量 Poisson 裡加入共同成分。白話說，它讓兩隊進球共享一點「比賽節奏」。

本研究想確認：這兩個修正是不是能用很小的改動改善 final candidate，而不是引入一個大型新模型。

## 名詞解釋

Poisson Distribution 是描述計數事件的機率分布。足球中可用來估計一隊進 0、1、2、3 球的機率。

Dixon-Coles 是一種低比分修正方法，主要調整 0-0、1-0、0-1、1-1 這些比分的機率。

rho 是 Dixon-Coles 的修正參數。不同 rho 會讓低比分機率往不同方向移動。

Gamma 在這裡是雙變量 Poisson 的共同進球成分。Gamma 越高，兩隊進球越像受到共同比賽節奏影響。

Draw probability 是平手機率。足球平手比例高，所以這個機率校準很重要。

Low-score rate 是低比分實際發生率，這裡主要觀察 0-0、1-0、0-1、1-1 等比分。

LogLoss 和 Brier Score 都是機率預測分數，越低越好。

## 實驗設計

主要結果檔案：

- `results/dixon_coles_rho_search.csv`
- `results/bivariate_gamma_search.csv`
- `results/final_worldcup_model_benchmark.json`

資料範圍是 FIFA World Cup + UEFA Euro neutral matches，共 1170 場。

固定 xG 候選後，本研究掃過不同 rho 與 gamma，觀察：

- Accuracy
- LogLoss
- Brier Score
- Top-1 正確比分
- 實際平手率 vs 預測平手機率
- 實際低比分率 vs 預測低比分機率

## Benchmark 結果

`results/dixon_coles_rho_search.csv` 顯示：

| rho | LogLoss | Brier Score | Top-1 比分 | Predicted 0-0 |
| ---: | ---: | ---: | ---: | ---: |
| -0.20 | 1.001342 | 0.595175 | 0.116239 | 0.098035 |
| -0.10 | 0.996139 | 0.592085 | 0.115385 | 0.084425 |
| 0.00 | 0.993786 | 0.590682 | 0.134188 | 0.073458 |
| 0.05 | 0.993752 | 0.590615 | 0.127350 | 0.067303 |

rho=0.05 是 LogLoss 與 Brier Score 最佳；rho=0.0 的 Top-1 正確比分較高，但整體機率校準略差。

`results/bivariate_gamma_search.csv` 顯示：

| Gamma | LogLoss | Brier Score | Predicted Draw | Actual Draw |
| ---: | ---: | ---: | ---: | ---: |
| 0.00 | 0.994138 | 0.591109 | 0.229376 | 0.241026 |
| 0.05 | 0.993805 | 0.590776 | 0.233977 | 0.241026 |
| 0.08 | 0.993752 | 0.590615 | 0.236890 | 0.241026 |
| 0.12 | 0.993915 | 0.590454 | 0.240967 | 0.241026 |
| 0.20 | 0.995802 | 0.590353 | 0.249865 | 0.241026 |

Gamma=0.08 是 LogLoss 最佳。Gamma=0.20 的 Brier Score 最低，但 LogLoss 變差，代表它可能把某些機率推得太激進。

在 `results/final_worldcup_model_benchmark.json` 中，Dixon-Coles 層從 `elo_xg_calibrated` 到 `full_calibrated_worldcup_candidate`：

- LogLoss 改善 0.000841。
- Brier Score 改善 0.000557。
- Top-1 正確比分改善 0.000855。

## 發現了什麼

這一層有效，但改善很小。真正的大改善來自 xG，Dixon-Coles 和 Gamma 比較像最後的細調。

rho=0.05 的好處是整體機率分數較好；rho=0.0 雖然 Top-1 比分較好，但本研究不能只為了最高比分命中率犧牲 LogLoss。

Gamma 的結果也提醒本研究：Brier Score 和 LogLoss 有時會選不同參數。這時更重視 LogLoss，因為它對過度自信的錯誤更敏感。

## 最終結論

Dixon-Coles rho=0.05 與 Gamma=0.08 被保留到 final_worldcup_model_v1_candidate。

保留理由不是它大幅改善模型，而是它在 final benchmark 中提供小但一致的 LogLoss 改善，而且沒有引入太大複雜度。

## 下一步研究方向

下一步可以研究：

- rho 是否應該依賽事年代或隊伍風格改變。
- Gamma 是否和總進球水位重疊，避免重複校準。
- 低比分修正是否應和淘汰賽、延長賽風險分開處理。

---

## Final Decision

最後保留 Dixon-Coles `rho = 0.05` 與 Bivariate Poisson `gamma = 0.08`。

沒有採用更複雜的低比分或共同節奏模型。

原因是 rho 和 gamma 的改善很小，但方向穩定、成本低，也沒有像其他研究層一樣造成主要指標惡化。未來除非 xG 或 score distribution 有重大改動，否則這兩個參數不需要重新大幅搜尋。
