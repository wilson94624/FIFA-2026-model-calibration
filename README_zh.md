# FIFA-2026-model-calibration

本 repository 是 FIFA Predictor 4.0 的模型校準實驗室。它是一個研究工作區，用來驗證模型假設、檢查機率校準、執行 tuning 實驗。它不是正式產品的 API、前端、資料庫層或部署套件。

# 研究動機

FIFA Predictor 4.0 的正式模型包含多個層次：Elo、Expected Goals、Poisson、Dixon-Coles、PQS，以及參考外部資料的傷停、疲勞、市場資料與賽事情境。若直接在完整產品模型中調參，很容易不知道改善來自哪一層，也容易把資料問題、模型問題和產品整合問題混在一起。

這個 Calibration Lab 的目標是把模型拆成可驗證、可重現、可比較的研究流程。每一步只研究一個問題，先建立乾淨 baseline，再逐步加入候選改良，並用 time split、tournament split、team universe filtering 等方式確認結果不是偶然或資料污染。

# 我們為什麼做這一步

目前的研究順序刻意從最底層開始：

- 先重建 Elo，因為所有後續勝率與 xG 都依賴 pre-match Elo。
- 再做 Elo calibration，確認 K factor、goal difference multiplier、team universe 等設定是否能改善機率預測。
- 接著做 time split validation，確認模型不是只在全歷史資料上變好，而是真的能預測 2024 之後的資料。
- 再做 tournament split validation，檢查候選模型在 World Cup、Euro、Copa América、AFC Asian Cup、AFCON 等主要賽事上是否穩定。
- 現在進入 Elo-to-xG calibration，因為即使 Elo 排名合理，Elo 差距如何轉成 expected goals 仍然會直接影響 Poisson、Dixon-Coles 與最終勝平負機率。

這樣做可以避免太早調 Poisson 或 Dixon-Coles，卻其實是在補償 xG 公式本身的偏差。

# 最後學到了什麼

目前最重要的結論是：

- 標準 Elo 可以作為乾淨 baseline，但預測校準能力有限。
- `calibrated_elo_v2_candidate` 的 LogLoss / Brier 改善明顯，但 rating scale 擴張過大。
- `calibrated_elo_v3_candidate` 使用 goal-difference shrinkage，在保留多數 calibration gain 的同時，明顯改善 Elo scale。
- Team universe filtering 很重要，可以排除 regional / non-FIFA teams 對 calibration universe 的污染。
- Time split validation 顯示 calibrated Elo 對 2024 之後資料仍有效。
- Tournament split validation 顯示 v3 在多數 major tournaments 上優於 standard Elo，但不是所有賽事都全面改善。
- Elo-to-xG benchmark 顯示目前 xG 公式方向合理，但 absolute goal level 偏低，尤其 home goals 與 total goals。

因此，下一個最值得研究的不是 Poisson 或 Dixon-Coles，而是先校準 Elo-to-xG 公式中的 `base_home`、`base_away`、`c1` 與可能的 neutral/home split。

# 校準進度

已完成的研究階段：

- 從 `international_results` 重建可重現的 Elo history。
- 調整 Elo K-factor，並選出較強的 calibrated candidates 進行驗證。
- 研究 home advantage 作為 Elo points adjustment，但目前 World Cup 導向候選模型暫不啟用。
- 研究 tournament weight，保守 grid validation 後暫不啟用。
- 研究 goal-difference multiplier，並導入 shrinkage 以降低 Elo scale expansion。
- 建立 team universe filter，支援 FIFA-only 與 FIFA + historical national teams calibration。
- 執行 time split validation：訓練期到 2023，驗證期從 2024 開始。
- 執行 tournament split validation：覆蓋主要國際賽事。
- 建立 Elo-to-xG benchmark，評估不同 Elo source 轉換成 expected goals 與 W/D/L 機率後的表現。

# 目前最佳候選模型

目前候選模型：

```text
calibrated_elo_v3_candidate
```

參數：

- `K = 80`
- `goal_diff_shrinkage_alpha = 0.10`
- `home_advantage = 0`
- `tournament_weight = 1`
- PQS disabled

狀態：

- 比 standard Elo 有更好的校準表現。
- 比 `calibrated_elo_v2_candidate` 有更穩定的 rating scale。
- 尚未升級為 production default。

# 研究路線圖

已完成：

- Elo rebuild
- Elo calibration
- Validation framework

進行中：

- Elo-to-xG calibration

計畫中：

- Poisson calibration
- Dixon-Coles calibration
- PQS integration
- FIFA Predictor integration

Pipeline：

```text
international_results
    ↓
Elo Rebuild
    ↓
Elo Calibration
    ↓
xG Calibration
    ↓
Poisson
    ↓
Dixon-Coles
    ↓
PQS
    ↓
FIFA Predictor
```

## 第一階段 Baseline

目前可執行 baseline 刻意保持簡潔：

- ELO-only expected goals
- Bivariate Poisson score matrix
- Dixon-Coles low-score correction
- Accuracy、multiclass LogLoss、Brier Score

baseline 只使用以下 CSV 欄位：

```text
home_team,away_team,home_score,away_score,home_pre_match_elo,away_pre_match_elo
```

baseline CLI 讀取 CSV 時不會自動更新 Elo。每一列都必須已經包含該場比賽前的 pre-match Elo。

固定模型常數：

- `c1 = 0.75`
- `GAMMA = 0.08`
- `RHO = -0.05`
- `MAX_GOALS = 5`

## 使用方式

準備符合必要 schema 的 historical matches CSV，然後執行：

```bash
python scripts/run_elo_baseline.py \
  --input data/raw/historical_matches.csv \
  --output results/elo_baseline_predictions.csv
```

輸出的 CSV 會包含 expected goals、home/draw/away probabilities、predicted label 與 actual label。CLI 會印出：

```text
matches: N
accuracy: ...
log_loss: ...
brier_score: ...
```

header-only schema template 位於：

```text
data/schema/historical_matches_schema.csv
```

本 repo 不包含假造的 historical match data。

## Repository 結構

```text
data/
  raw/
  processed/
  external/
  schema/
src/
  model/
    elo.py
    pqs.py
    expected_goals.py
    poisson.py
    metrics.py
  tuning/
  utils/
scripts/
results/
notebooks/
archive/product_legacy/
tests/
```

## 保留的 Legacy Model Logic

Calibration modules 保留了 FIFA Predictor 4.0 中有研究價值的模型核心：

- ELO expected score 與 ELO update helper
- ELO-to-Expected-Goals formula
- Bivariate Poisson score probability formula
- Dixon-Coles correction
- Score-matrix normalization
- Score-matrix aggregation into home/draw/away probabilities
- Legacy PQS active-roster logic，已隔離供未來研究使用

## 已隔離的產品依賴

原本與產品耦合的檔案已封存於 `archive/product_legacy/`。第一階段 baseline 不會 import 這些檔案。

已隔離的產品依賴包含：

- SQLAlchemy database models
- backend/FastAPI import paths
- frontend JSON paths
- `.env` loading
- Gemini/LLM analysis 與 external API calls
- tournament bracket 與 knockout simulation
- Monte Carlo champion probability outputs
- automatic frontend JSON writes

## 下一步需要的資料

若要執行有意義的 calibration experiments，需要準備 historical match data，至少包含：

- team names
- final score
- pre-match Elo for both teams
- match date
- competition or tournament name
- neutral-site or host indicator

未來可以加入 player/PQS snapshots、injuries、rest days、travel、market odds 與 tournament context，但這些都刻意排除在第一階段 ELO-only baseline 之外。
