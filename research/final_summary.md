# Calibration Lab v1.0 Final Summary

這份文件是 Calibration Lab 的收尾總結。

它不是新增研究，也不是重新校準。它只是把這一輪研究到底學到什麼，用比較白話的方式整理下來。

最後 closure audit 的決定是：

```text
A. 可以收尾，進入 4.0 / 5.0 integration planning。
```

## 本研究一開始想解決什麼？

FIFA Predictor 4.0 一開始不是一個純研究專案，而是一個產品模型。

產品裡有很多足球上聽起來合理的想法：

- 強隊應該比較容易贏
- 強隊打弱隊可能會壓制
- 球員品質應該影響結果
- 傷病應該影響勝率
- 大比分可能被 Poisson 低估
- 世界盃擴編後，強弱差距可能更明顯

這些想法都合理。

但合理不等於已經被證明。

Calibration Lab 一開始要解決的核心問題就是：

```text
哪些模型層真的有效？
```

如果直接在完整產品模型裡調整，很容易不知道改善來自哪裡。也很容易把資料問題、模型問題、產品敘事和直覺混在一起。

所以 Calibration Lab 把模型拆開，一層一層測。

## 本研究做了哪些研究？

這一輪研究大致分成幾條線。

第一條是模型骨架：

- Elo calibration
- xG calibration
- Dixon-Coles rho
- Bivariate Poisson gamma

這些是勝平負和比分矩陣的核心。

第二條是直覺型加成：

- Raw PQS
- Domination Layer
- Score Tail Correction
- Conditional Tail Correction
- Negative Binomial
- Tournament Weight

這些想法都來自足球直覺，但每個都需要證明自己不是只是在重複放大既有訊號。

第三條是資料型未來方向：

- Injury / Availability
- Dynamic Team PQS
- frozen prediction archive
- Host / semi-home advantage
- Fatigue
- Style

這些方向不是這輪 calibration 的正式模型內容，而是 5.0 的研究基礎。

## 哪些研究成功？

### Elo

Elo calibration 成功。

最後採用：

```text
calibrated_elo_v3_candidate
K = 80
goal_diff_shrinkage_alpha = 0.10
```

`calibrated_elo_v2_candidate` 的指標很好，但 rating scale 擴太大。v3 用 shrinkage 保留校準收益，同時避免 Elo 分數被大比分拉得太開。

Tournament Weight 測過，但不採用。

Neutral World Cup Mode 不使用一般 Home Advantage。

### xG

xG calibration 是這輪最重要的改善來源。

最後 World Cup Candidate 使用：

```text
base = 1.35
c1 = 1.30
scale = 600
min_xg = 0.20
```

這裡最大的收穫是：世界盃中立場不能直接套一般主客場 xG。中立場需要自己的轉換方式。

### Dixon-Coles / Gamma

保留：

```text
rho = 0.05
gamma = 0.08
```

它們不是大幅提升模型的主因，但有小幅、穩定的校準改善，所以保留。

### 最終 candidate

final benchmark 顯示：

| Model | Accuracy | LogLoss | Brier |
| --- | ---: | ---: | ---: |
| `baseline_current` | 0.485470 | 1.022132 | 0.611690 |
| `full_calibrated_worldcup_candidate` | 0.532479 | 0.993752 | 0.590615 |

這代表目前模型骨架有足夠理由進入 4.0 / 5.0 integration planning。

## 哪些研究最後放棄？

### Raw PQS

Raw PQS 一開始看起來很有希望。

足球是球員踢的，所以球員品質應該重要。

但 shadow benchmark 顯示 Raw PQS 和 Elo 高度重疊：

- Pearson correlation 約 `0.75`
- Sign agreement 約 `84%`

這表示 Raw PQS 很可能只是在重複說：

```text
強隊比較強，弱隊比較弱。
```

而 Elo 已經知道這件事。

所以 Raw PQS 不採用為正式 Team Strength Feature。

### Domination Layer

Domination Layer 的想法是：強隊不只比較容易贏，還可能更容易壓制弱隊。

結果它確實讓某些 correct score ranking 有一點改善，但：

- LogLoss 沒改善
- Brier 沒改善
- 整體改善太小
- 可能和 Elo/xG 重疊

所以正式不採用。

### Score Tail Correction

模型確實低估 `GD >= 3`。

但 Global Tail Correction 和 Conditional Tail Correction 都沒有通過穩定性檢查。

有些 pooled 結果看起來變好，但到了 Euro、modern era、recent era，結果就不穩。

所以不採用。

### Negative Binomial

Negative Binomial 本來看起來很合理，因為它比 Poisson 有更厚的尾端。

但 benchmark 顯示它不是只補強 5-0、6-0，而是把整個比分分布撐開。

結果 high-mismatch 子集有些改善，但 pooled LogLoss、Brier、Top-3 變差。

所以正式維持 Bivariate Poisson。

### Tournament Weight

Tournament Weight 聽起來合理，但 grid validation 沒支持它。

最後維持：

```text
tournament_weight = 1
```

## 為什麼放棄不是失敗？

這是這輪研究最重要的心態。

Raw PQS、Domination、Tail Correction 都不是「沒用所以浪費時間」。

它們的價值是讓本研究確認：

- 哪些直覺和 Elo 重疊
- 哪些修正只在 pooled data 好看
- 哪些東西會傷害 LogLoss / Brier
- 哪些功能應該停在 Shadow Mode
- 哪些問題其實需要新資料，而不是新公式

這些結論讓正式模型更乾淨。

模型不是越複雜越好。

模型應該只保留已經證明值得留下的東西。

## Calibration 最大收穫是什麼？

最大的收穫是：

```text
不要把足球敘事直接翻成模型係數。
```

「強隊會壓制弱隊」可能是真的。

「球員品質很重要」也可能是真的。

「傷病會影響比賽」更幾乎一定是真的。

但模型問題不是問它們在足球上合不合理。

模型問題是問：

- 這個訊號是不是 Elo / xG 還不知道？
- 它能不能在 time split、tournament split、modern split 裡穩定改善？
- 它會不會讓模型過度自信？
- 它有沒有 time-safe data？

Calibration Lab 最後留下的不是一堆新功能，而是一套判斷功能該不該進模型的標準。

## 為什麼 Dynamic Team PQS 變成下一階段？

Raw PQS 被否決後，本研究沒有得到「球員資料沒用」這個結論。

本研究得到的是：

```text
球員資料不能直接當作另一個球隊強度層。
```

因為 Raw PQS 問的是：

```text
這隊強不強？
```

Elo 已經很會回答這題。

Dynamic Team PQS 應該問的是：

```text
這隊今天和它正常狀態差多少？
```

這才可能是新的資訊。

例如：

- 預期先發門將缺陣
- 兩名主力中衛同時不能上
- 核心前鋒受傷
- 替補深度不足
- 賽前突然停賽

這些不是長期球隊強度，而是 match-day availability shock。

所以 Dynamic Team PQS 變成 5.0 的核心方向。

但它不能直接進正式模型。

它必須先走：

```text
Information Layer
-> Shadow Mode
-> frozen prediction archive
-> time-safe validation
-> 才能考慮正式模型
```

## 4.0 與 5.0 的分界線是什麼？

### 4.0

4.0 應該整合已經被 Calibration Lab 支持的模型核心：

- calibrated Elo v3
- neutral World Cup xG
- Bivariate Poisson
- Dixon-Coles `rho = 0.05`
- Gamma `0.08`

4.0 不應該把研究中被否決或未證明的東西塞進正式機率：

- Raw PQS
- Domination Layer
- Tail Correction
- Negative Binomial
- fixed Injury Coefficient
- Fatigue
- Style

### 5.0

5.0 應該處理資料和驗證問題：

- Dynamic Team PQS
- Injury / Availability Information Layer
- Shadow Mode
- frozen prediction archive
- input snapshots
- prediction timestamps
- Host / semi-home advantage
- Fatigue data readiness
- Style data readiness

簡單說：

```text
4.0 = 用已證明的核心收斂。
5.0 = 建立下一個新訊號的資料與驗證基礎。
```

## 本研究學到了什麼？

本研究得到的收穫是：校準不是一直往模型加東西。

校準更像是刪東西。

把不穩定的刪掉。
把重複計算的刪掉。
把資料不夠的延後。
把只改善漂亮指標但傷害核心指標的留下研究區。

最後模型不一定會變得很華麗。

但會更誠實。

## Final Conclusion

目前已經比較有證據支持的是：

- calibrated Elo v3 可以作為目前 World Cup candidate 的 Elo 基礎
- neutral World Cup xG 是本輪最大改善來源
- Dixon-Coles `rho = 0.05` 和 Gamma `0.08` 值得保留
- Bivariate Poisson 仍是正式比分分布 baseline

目前沒有足夠證據支持的是：

- Raw PQS 當正式 Team Strength Feature
- Domination Layer
- Global Tail Correction
- Conditional Tail Correction
- Negative Binomial 取代 Bivariate Poisson
- fixed Injury Coefficient
- Fatigue coefficient
- Style coefficient

仍然未知、留到 v5 的是：

- Injury / Availability 是否能穩定提升預測
- Dynamic Team PQS 是否能提供 Elo 沒有的新訊號
- Host / semi-home advantage 是否需要正式建模
- Fatigue 是否有可驗證資料
- Style 是否能從描述性標籤變成可靠特徵

所以最後不能說：

```text
模型一定更準。
```

更誠實的說法是：

```text
本研究已經知道哪些核心層值得留下。
也知道哪些直覺目前不值得進正式模型。
下一階段要做的，是為 Dynamic Team PQS 和 availability signal 建立可信資料。
```

> Calibration is not about proving every idea works.
> It is about discovering which ideas deserve to become part of the model.

> 校準的目的，不是證明每個想法都是對的，而是找出哪些想法真正值得成為模型的一部分。
