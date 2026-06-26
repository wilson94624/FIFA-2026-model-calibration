# Calibration Lab 研究總覽

## 專案起點

這個 Repo 並不是從論文研究開始的。

它的起點其實是一個產品。

2026 年世界盃即將到來，因此我開始開發 FIFA World Cup 2026 Predictor 4.0，希望建立一個能夠預測：

- 勝平負機率
- 正確比分
- 奪冠機率
- 比賽分析

的足球預測系統。

當時的想法其實很單純：

如果足球世界裡大家都認為某件事情很重要，那模型應該也要把它考慮進去。

因此模型裡逐漸加入了許多足球概念：

- Elo Rating
- Expected Goals (xG)
- Dixon-Coles
- Gamma Correlation
- Raw PQS
- Domination Layer
- Fatigue
- Style Matchup
- Market Comparison

每個想法單獨看都很合理。

但隨著功能越來越多，一個問題開始出現：

> 我們其實不知道哪些東西真的有效。

---

## 為什麼建立 Calibration Lab

Predictor 4.0 開發到中後期時，我開始發現一件事情。

很多功能是因為「感覺合理」而加入。

例如：

- 強隊應該更容易大勝
- 球員品質應該影響預測
- 傷病應該影響勝率
- 豪門球隊應該有壓制效果

這些想法都很符合足球直覺。

但足球直覺不等於模型改善。

有些功能可能真的有用。

也有些功能只是把 Elo 已經知道的事情再算一次。

甚至可能讓模型變得更差。

因此我們另外建立了 Calibration Lab。

Calibration Lab 的目標不是增加新功能。

而是驗證現有功能。

我們希望回答：

- 哪些功能真的有幫助？
- 哪些功能只是增加複雜度？
- 哪些功能應該保留？
- 哪些功能應該移除？

---

## Calibration Lab 的核心理念

這個研究最重要的原則只有一句話：

> 看起來合理，不代表應該進模型。

所有新想法都必須經過 Benchmark 驗證。

如果某個功能：

- 無法改善預測能力
- 無法改善機率校準
- 無法通過資料切分驗證
- 無法證明提供新的資訊

那麼即使足球上看起來合理，也不應該進入正式模型。

我們寧可保留一個簡單但可靠的模型。

也不要建立一個充滿補丁卻無法驗證的模型。

---

## 研究時間軸

### 第一階段：建立可信的骨架

研究項目：

- Elo Calibration
- xG Calibration
- Dixon-Coles Tuning
- Gamma Tuning

目標：

先確認模型最基本的預測能力。

如果連基礎模型都不可靠，後面所有功能都沒有意義。

結果：

保留。

這些成為目前正式模型的核心。

---

### 第二階段：驗證額外資訊是否有價值

研究項目：

- PQS Shadow Benchmark
- PQS Overlap Analysis

當時的想法：

球員能力應該能補足 Elo 的不足。

結果：

PQS 與 Elo 高度重疊。

許多效果其實只是把強隊變得更強。

目前結論：

PQS 不適合作為主模型強度來源。

保留作為未來 Dynamic Team PQS 與 Injury / Availability Information Layer 的研究方向。

---

### 第三階段：研究強隊壓制效果

研究項目：

- Domination Layer Benchmark
- Domination Layer Extended Benchmark

當時的想法：

強隊對弱隊時，應該更容易出現 3:0、4:0、5:0。

因此設計額外的強隊放大器。

結果：

比分排名有極小改善。

但 LogLoss 與 Brier Score 變差。

改善幅度遠小於預期。

目前結論：

不納入正式模型。

---

### 第四階段：研究大比分問題

研究項目：

- Score Tail Calibration
- Score Distribution Diagnostics
- Margin Tail Research
- Margin Tail Fine Search

當時的問題：

模型經常預測：

- 1:0
- 2:0
- 2:1

但真實結果卻出現：

- 4:0
- 5:0
- 6:0

因此懷疑模型是否系統性低估大比分。

結果：

確實存在部分低估。

但問題並不像原本想像的那麼簡單。

許多修正方法在歷史資料有效。

到了現代足球資料卻失效。

目前結論：

暫不修改正式模型。

繼續研究比分分布本身。

---

### 第五階段：重新思考 PQS

當 Domination 與 Tail Correction 都沒有得到理想結果後。

研究方向開始轉變。

問題變成：

如果 PQS 不是強弱評分。

那它還能做什麼？

最後得到的答案是：

PQS 最有價值的地方可能不是描述球隊有多強。

而是描述球隊今天比平常弱了多少。

因此開始規劃：

Dynamic Team PQS

也就是：

利用傷病、停賽、缺席球員來修正預測。

目前仍處於設計階段。

---

## 最重要的研究失敗

這個 Repo 最有價值的成果之一。

其實不是成功的研究。

而是失敗的研究。

### 失敗案例一：PQS

原本以為：

球員品質能提升模型。

後來發現：

很多資訊 Elo 已經知道了。

問題：

Double Counting。

---

### 失敗案例二：Domination Layer

原本以為：

強隊應該被放大。

後來發現：

雖然看起來合理。

但實際上沒有改善主要指標。

---

### 失敗案例三：Global Tail Correction

原本以為：

全域修正可以改善大比分問題。

後來發現：

改善主要來自舊時代世界盃。

在現代足球資料上不穩定。

---

### 失敗案例四：MAX_GOALS

原本以為：

比分矩陣只算到 5 球是問題來源。

後來發現：

就算提高到 10 球。

改善仍然非常有限。

真正問題在於比分分布形狀。

而不是矩陣大小。

---

## 目前正式模型長什麼樣

截至目前為止。

正式候選模型：

- Calibrated Elo
- Calibrated xG
- Dixon-Coles
- Gamma Correlation

刻意不包含：

- Raw PQS
- Domination Layer
- Global Tail Correction

原因不是它們沒有足球直覺。

而是目前沒有足夠證據支持它們。

---

## 一路走來最大的收穫

這個 Calibration Lab 最後教會我們的事情其實很簡單。

模型開發不是不停增加功能。

而是不停證明哪些功能不該存在。

很多看起來合理的東西：

- PQS
- Domination
- Tail Correction

最後都沒有直接進入正式模型。

真正留下來的東西很少。

但每一個留下來的東西都有數據支持。

這也是目前 final_worldcup_model_v1_candidate 存在的原因。

它不是最複雜的模型。

而是目前證據最充分的模型。

---

# 附錄：名詞解釋

## 什麼是 Benchmark？

Benchmark 可以理解成：

> 用同一份考卷比較不同模型。

例如：

有 1000 場已經踢完的比賽。

模型 A 與模型 B 都預測這 1000 場。

最後比較：

- 誰猜得比較準
- 誰的機率比較合理
- 誰的比分比較接近

這個比較過程就叫做 Benchmark。

---

## 什麼是 Elo？

Elo 是一種評分系統。

原本用於西洋棋。

後來廣泛應用於足球、籃球與電競。

簡單理解：

贏強隊加很多分。

贏弱隊加很少分。

輸給弱隊扣很多分。

---

## 什麼是 xG（Expected Goals）？

Expected Goals（預期進球）。

代表：

一支球隊平均應該進幾球。

例如：

xG = 2.0

代表長期來看平均約進兩球。

不是一定進兩球。

---

## 什麼是 LogLoss？

目前最重要的評估指標。

它會懲罰：

> 猜錯而且非常有自信

例如：

模型說：

法國勝率 90%

結果：

伊拉克贏球

就會被重罰。

LogLoss 越低越好。

---

## 什麼是 Brier Score？

衡量機率是否校準正確。

例如：

模型長期說：

70% 勝率

那麼實際勝率也應該接近 70%。

Brier 越低越好。

---

## 什麼是 Calibration？

Calibration 中文通常翻譯成：

校準。

意思是：

讓模型輸出的機率更接近現實。

例如：

模型說：

勝率 80%

那麼長期下來真的應該贏約 80%。

而不是只贏 60%。

---

## 什麼是 Double Counting？

重複計算同一份資訊。

例如：

Elo 已經知道法國很強。

PQS 又再告訴模型法國很強。

那模型可能把同樣的強度算兩次。

造成過度自信。

這就是 Double Counting。

---

## 什麼是 Shadow Mode？

Shadow Mode 可以理解成：

影子模式。

功能會參與研究。

但不影響正式預測。

例如：

PQS Shadow Benchmark。

會計算 PQS 對結果的影響。

但不會真的改變正式模型輸出的勝率。

目的是先觀察。

再決定是否值得正式採用。

---

## Final Decision

最後這篇作為 Calibration Lab 的總覽與研究哲學保留。

正式採用的是基礎模型骨架：calibrated Elo v3、Neutral World Cup xG、Bivariate Poisson、Dixon-Coles `rho = 0.05`、Gamma `0.08`。

沒有採用的是 Raw PQS、Domination Layer、Global Tail Correction、Conditional Tail Correction、Negative Binomial replacement、Tournament Weight、固定 Injury Coefficient。

原因很簡單：這些想法有足球直覺，但目前沒有穩定證據支持它們進正式模型。未來研究會轉向 Dynamic Team PQS、Injury / Availability Information Layer、Shadow Mode、Host Advantage、Fatigue 和 Style 的資料準備。
