# Research Reading Guide

這個資料夾是 Calibration Lab v1.0 的正式研究文件。

如果你第一次進來，不建議照檔名從 00 一路硬讀。比較好的方式是先讀總結，再看 closure audit，最後依照你關心的研究線往下鑽。

## 建議閱讀順序

1. [final_summary.md](final_summary.md)  
   先讀這篇。它用白話整理整個 Calibration Lab：本研究想解決什麼、做了哪些研究、哪些留下、哪些放棄、為什麼 Dynamic Team PQS 變成下一階段。

2. [calibration_closure_audit.md](calibration_closure_audit.md)  
   這是正式收尾依據。最後決定是：Calibration 可以收尾，進入 4.0 / 5.0 integration planning。

3. [00-overview.md](00-overview.md)  
   這篇是研究故事的起點，說明為什麼需要 Calibration Lab，而不是一直往產品模型裡加功能。

4. [01-elo-calibration.md](01-elo-calibration.md)  
   先看 Elo。這是模型地基，也是最後 formal candidate 的第一層。

5. [02-xg-calibration.md](02-xg-calibration.md)  
   再看 xG。這是 final benchmark 中最大改善來源。

6. [03-dixon-coles-gamma.md](03-dixon-coles-gamma.md)  
   看低比分修正與共同進球項。這一層改善小，但最後保留。

7. [04-pqs-shadow-study.md](04-pqs-shadow-study.md)  
   看 Raw PQS 為什麼沒有進正式模型，以及為什麼它後來變成 Dynamic Team PQS 的起點。

8. [05-domination-layer-study.md](05-domination-layer-study.md)  
   看一個很有足球直覺、但沒有通過 LogLoss / Brier 的研究。

9. [06-score-tail-calibration.md](06-score-tail-calibration.md)  
   看大比分尾端問題為什麼存在，但不能用全域 Tail Correction 硬修。

10. [07-poisson-distribution-research.md](07-poisson-distribution-research.md)  
    看為什麼目前仍維持 Bivariate Poisson，不改用 Negative Binomial。

11. [10-score-distribution-and-model-limits.md](10-score-distribution-and-model-limits.md)  
    看 score distribution 研究最後帶來的產品觀念：正確比分本來就是高變異，不應把產品定位成正確比分神器。

12. [08-injury-aware-pqs-design.md](08-injury-aware-pqs-design.md)  
    看 Injury / Availability 為什麼只先做 Information Layer 和 Shadow Mode。

13. [frozen_prediction_availability_audit.md](frozen_prediction_availability_audit.md)  
    看為什麼目前還不能做嚴格的 absence signal calibration：缺 frozen prediction dataset 和 time-safe absence features。

14. [09-future-work.md](09-future-work.md)  
    最後看未來方向。這篇把 5.0 的研究邊界整理出來。

## 研究狀態總表

| 文件 | 目的 | 狀態 | 最終決策 |
| --- | --- | --- | --- |
| [final_summary.md](final_summary.md) | Calibration Lab v1.0 總結 | 完成 | 作為收尾總讀本 |
| [calibration_closure_audit.md](calibration_closure_audit.md) | 正式 closure audit | 完成 | 可以收尾，進入 4.0 / 5.0 planning |
| [00-overview.md](00-overview.md) | 說明 Lab 起點與研究哲學 | 完成 | 保留為研究導讀 |
| [01-elo-calibration.md](01-elo-calibration.md) | 校準 Elo | 完成 | 採用 calibrated Elo v3 |
| [02-xg-calibration.md](02-xg-calibration.md) | 校準 neutral xG | 完成 | 採用 base 1.35 / c1 1.30 / scale 600 |
| [03-dixon-coles-gamma.md](03-dixon-coles-gamma.md) | 校準 rho 與 gamma | 完成 | 保留 rho 0.05 / gamma 0.08 |
| [04-pqs-shadow-study.md](04-pqs-shadow-study.md) | 評估 Raw PQS | 完成 | Raw PQS 不進正式模型 |
| [05-domination-layer-study.md](05-domination-layer-study.md) | 評估 Domination Layer | 完成 | 不採用 |
| [06-score-tail-calibration.md](06-score-tail-calibration.md) | 評估尾端修正 | 完成 | 不採用 Global / Conditional Tail Correction |
| [07-poisson-distribution-research.md](07-poisson-distribution-research.md) | 評估 Poisson 侷限 | 完成 | 維持 Bivariate Poisson |
| [08-injury-aware-pqs-design.md](08-injury-aware-pqs-design.md) | 設計 Injury / Availability 方向 | 完成設計 | Information Layer + Shadow Mode |
| [09-future-work.md](09-future-work.md) | 整理 5.0 研究方向 | 完成 | Dynamic Team PQS 進 5.0 |
| [10-score-distribution-and-model-limits.md](10-score-distribution-and-model-limits.md) | 整理比分分布與模型極限 | 完成 | 不為 rare blowouts 重寫模型 |
| [frozen_prediction_availability_audit.md](frozen_prediction_availability_audit.md) | 檢查 frozen prediction / absence data | 完成 | 目前不能做 absence calibration |

## 快速答案

### 哪些已採用？

- calibrated Elo v3
- Neutral World Cup xG
- Bivariate Poisson
- Dixon-Coles `rho = 0.05`
- Gamma `0.08`

### 哪些已放棄？

- Raw PQS as Team Strength Feature
- Domination Layer
- Global Tail Correction
- Conditional Tail Correction
- Negative Binomial replacement
- Tournament Weight
- fixed Injury Coefficient

### 哪些不是放棄，而是留到 5.0？

- Dynamic Team PQS
- Injury / Availability Information Layer
- Host / semi-home advantage
- Fatigue
- Style
- frozen prediction archive
- score-tail monitoring for 48-team World Cup mismatch cases

## 統一術語

本 repo 統一使用：

- `Raw PQS`：直接把球員品質當作球隊強度層。
- `Dynamic Team PQS`：未來 v5 方向，用 availability / depth / role delta 描述球隊當下狀態。
- `Information Layer`：先顯示或記錄資訊，不直接改正式勝率。
- `Shadow Mode`：平行計算研究層的 drift，不影響正式模型輸出。
- `Neutral World Cup Mode`：世界盃中立場模型，不使用一般 Home Advantage。
- `Bivariate Poisson`：目前正式 score distribution baseline。

## 核心精神

> Calibration is not about proving every idea works.
> It is about discovering which ideas deserve to become part of the model.

> 校準的目的，不是證明每個想法都是對的，而是找出哪些想法真正值得成為模型的一部分。
