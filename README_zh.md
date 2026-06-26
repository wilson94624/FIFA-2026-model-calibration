# FIFA-2026-model-calibration

[English](README.md) | 繁體中文

這個 repository 是 FIFA Predictor 的 Calibration Lab。

它不是正式產品。
不是 API。
不是前端。
不是資料庫。
也不是新的研究循環。

Calibration Lab v1.0 已經收尾。最後 closure audit 的決定是：

```text
A. 可以收尾，進入 4.0 / 5.0 integration planning。
```

這份 README 是給半年後重新回來閱讀時使用：快速回到本專案做了什麼、最後相信什麼、最後放棄什麼，以及為什麼 FIFA Predictor 5.0 要從 Dynamic Team PQS 開始。

> 校準的目的，不是證明每個想法都是對的，而是找出哪些想法真正值得成為模型的一部分。

## 這個 Lab 一開始想解決什麼？

FIFA Predictor 4.0 原本是一個越做越完整的足球預測系統。

FIFA Predictor 想預測：

- 勝平負機率
- 正確比分
- 奪冠機率
- 比賽分析

所以模型裡慢慢加了很多看起來合理的足球概念：

- Elo
- xG
- Dixon-Coles
- Bivariate Poisson
- Raw PQS
- Domination Layer
- Score Tail Correction
- Injury / Availability
- Fatigue
- Style

問題是：看起來合理，不代表真的能改善模型。

Calibration Lab 的目的，就是把這些想法一個一個拆開，不靠產品敘事說服模型，而是用 benchmark 和資料切分確認：

- 哪些真的應該進模型？
- 哪些只是和 Elo 重疊？
- 哪些只在某些 split 變好？
- 哪些很有足球直覺，但目前資料不夠？

## 最後模型長什麼樣？

目前正式 World Cup candidate 是：

```text
final_worldcup_model_v1_candidate
```

保留：

| Layer | 最終設定 |
| --- | --- |
| Elo | `calibrated_elo_v3_candidate` |
| K factor | `K = 80` |
| Goal-difference shrinkage | `alpha = 0.10` |
| xG | Neutral World Cup xG |
| xG 參數 | `base = 1.35`, `c1 = 1.30`, `scale = 600` |
| Neutral World Cup Mode | 不使用 Home Advantage |
| Tournament Weight | 不採用，維持 `1` |
| Score model | Bivariate Poisson |
| Dixon-Coles | `rho = 0.05` |
| Gamma | `gamma = 0.08` |

不保留：

| 研究方向 | 最終決定 |
| --- | --- |
| Raw PQS 當球隊強度特徵 | 不採用 |
| Domination Layer | 不採用 |
| Global Tail Correction | 不採用 |
| Conditional Tail Correction | 不採用 |
| Negative Binomial 取代 Poisson | 不採用 |
| 固定 Injury Coefficient | 不採用 |
| Fatigue | 暫停 |
| Style | 暫停 |

## Final Benchmark

資料範圍：

- FIFA World Cup + UEFA Euro
- 只看中立場
- FIFA + historical national team universe

| Model | Accuracy | LogLoss | Brier |
| --- | ---: | ---: | ---: |
| `baseline_current` | 0.485470 | 1.022132 | 0.611690 |
| `full_calibrated_worldcup_candidate` | 0.532479 | 0.993752 | 0.590615 |

相對 baseline：

- Accuracy: `+0.047009`
- LogLoss: `+0.028380`
- Brier: `+0.021075`

最重要的改善來自 xG calibration。
Elo calibration 也有穩定幫助。
Dixon-Coles 和 Gamma 的改善很小，但夠穩定，所以保留。

## 本研究最後學到什麼？

### 1. Elo 是地基，但不能亂放大

`calibrated_elo_v2_candidate` 的指標很好，但 rating scale 擴太大。

本研究最後採用 `calibrated_elo_v3_candidate`：

- `K = 80`
- `goal_diff_shrinkage_alpha = 0.10`

這不是追求最漂亮的單一數字，而是比較穩的版本。

### 2. xG 是最大改善來源

Elo 告訴模型誰比較強。

xG 決定這個強弱差要變成多少進球。

World Cup / Euro 中立場不能直接沿用一般主客場公式，所以最後採用 neutral xG：

```text
base = 1.35
c1 = 1.30
scale = 600
```

這是目前 World Cup candidate 最核心的改善。

### 3. Dixon-Coles 和 Gamma 有用，但只是細調

保留：

```text
rho = 0.05
gamma = 0.08
```

它們不是模型變好的主因，但能提供小幅、穩定的校準改善。

### 4. Raw PQS 的直覺對，但方向錯

本研究一開始假設球員品質能提升模型。

後來發現 Raw PQS 與 Elo 高度重疊：

- Pearson correlation 約 `0.75`
- Sign agreement 約 `84%`

這代表 Raw PQS 常常不是提供新資訊，而是在說：

```text
強隊球員比較強。
```

但 Elo 其實已經知道強隊比較強。

所以 Raw PQS 不適合當正式模型的 Team Strength Feature。

這不是失敗。
這是很重要的研究成果。

這個結果指出：PQS 真正有價值的地方，不是描述一隊本來有多強，而是描述這隊今天和正常狀態差多少。

這就是 Dynamic Team PQS 的起點。

### 5. Domination Layer 沒有通過

本研究原本假設強隊對弱隊應該有壓制效果，可能能改善 3-0、4-0、5-0 這種比分。

結果是：

- 某些 Correct Score 排名有一點改善
- 但 LogLoss 和 Brier 沒有改善
- 改善幅度太小
- 可能又是在重複放大 Elo/xG 已經知道的強弱差

所以不採用。

### 6. Score Tail 問題是真的，但不能硬修

模型確實低估 `GD >= 3`。

但 Global Tail Correction 和 Conditional Tail Correction 在 split validation 不穩定。

有些 pooled 結果看起來有改善，但到 modern era、recent era 或 Euro split 就不穩。

所以正式模型不做 Tail Correction。

這裡最大的教訓是：

```text
看到問題，不代表第一個修正方法就是對的。
```

### 7. Negative Binomial 沒有取代 Poisson

Negative Binomial 比 Poisson 有更厚的尾端，直覺上很適合解決大比分問題。

但 benchmark 顯示它不是只增加 5-0、6-0，而是把整個分布撐開。

結果：

- high-mismatch 有些地方變好
- pooled LogLoss / Brier / Top-3 變差

所以正式維持 Bivariate Poisson。

### 8. Injury / Availability 不是係數，是資訊層

傷停一定重要。

但目前沒有足夠資料支持：

```text
固定 Injury Coefficient
```

正確做法是：

```text
Information Layer
-> Dynamic Team PQS
-> Shadow Mode
-> 證明有效後再考慮正式模型
```

第一版只應該收集資訊、顯示資訊、做 shadow drift。
不要直接修改正式勝率。

## 為什麼 Dynamic Team PQS 變成下一階段？

因為 Raw PQS 問錯問題。

Raw PQS 問：

```text
這隊強不強？
```

但 Elo 已經很會回答這題。

Dynamic Team PQS 應該問：

```text
這隊今天和它正常狀態差多少？
```

這比較可能是 Elo 沒有的新資訊。

例如：

- 主力門將不能上
- 兩個中衛同時缺陣
- 最重要的前鋒受傷
- 替補深度不足
- 賽前臨時停賽

這些不是「強隊比較強」。
這些是「今天這隊不是平常那隊」。

所以 FIFA Predictor 5.0 的重點不是重新校準 Elo，而是建立 Dynamic Team PQS 所需的資料工程：

- frozen prediction archive
- prediction timestamp
- input snapshot
- unavailable players
- reported_at
- expected role
- player mapping
- shadow-mode QA

## 4.0 和 5.0 的分界線

### 4.0 應該做什麼？

4.0 可以整合已經校準完成的模型核心：

- calibrated Elo v3
- neutral World Cup xG
- Bivariate Poisson
- Dixon-Coles `rho = 0.05`
- Gamma `0.08`

同時不要加入：

- Raw PQS
- Domination Layer
- Tail Correction
- Negative Binomial
- fixed injury coefficient

4.0 的目標是穩定、可解釋、不要亂加東西。

### 5.0 應該做什麼？

5.0 應該處理 Calibration Lab 沒有資料證明的事情：

- Dynamic Team PQS
- Injury / Availability Information Layer
- Shadow Mode
- frozen prediction archive
- Host / semi-home advantage
- Fatigue data readiness
- Style data readiness

5.0 不是「把 4.0 變複雜」。

5.0 是先把資料和驗證方式準備好，讓下一個真正有價值的訊號有機會被證明。

## 建議閱讀順序

第一次回來看，照這樣讀：

1. [research/final_summary.md](research/final_summary.md)
2. [research/README.md](research/README.md)
3. [research/calibration_closure_audit.md](research/calibration_closure_audit.md)
4. [research/01-elo-calibration.md](research/01-elo-calibration.md)
5. [research/02-xg-calibration.md](research/02-xg-calibration.md)
6. [research/04-pqs-shadow-study.md](research/04-pqs-shadow-study.md)
7. [research/05-domination-layer-study.md](research/05-domination-layer-study.md)
8. [research/06-score-tail-calibration.md](research/06-score-tail-calibration.md)
9. [research/10-score-distribution-and-model-limits.md](research/10-score-distribution-and-model-limits.md)
10. [research/08-injury-aware-pqs-design.md](research/08-injury-aware-pqs-design.md)

## Repository 裡各資料夾的角色

```text
research/
  正式研究說明、閱讀順序、final summary、closure audit

results/
  benchmark 輸出、診斷報告、資料可用性報告

src/
  校準與 benchmark 所用程式

data/
  raw / processed / schema 資料

archive/product_legacy/
  從產品隔離出來的舊邏輯，只作為研究參考
```

## Final Conclusion

這次 Calibration Lab 最重要的成果，不是「模型一定更準」這種口號。

已經比較有證據的是：

- calibrated Elo v3 比 standard Elo 更適合作為目前候選
- neutral World Cup xG 是最大改善來源
- Dixon-Coles `rho = 0.05` 和 Gamma `0.08` 可以保留
- Raw PQS、Domination、Tail Correction、Negative Binomial 都不應直接進正式模型

仍然未知的是：

- 傷停資訊能不能穩定改善預測
- Host / semi-home advantage 要怎麼處理
- fatigue 是否有資料支撐
- style 是否能從敘事變成可靠特徵
- Dynamic Team PQS 是否能真正提供 Elo 沒有的新訊號

這些留給 FIFA Predictor 5.0。

> 校準的目的，不是證明每個想法都是對的，而是找出哪些想法真正值得成為模型的一部分。
