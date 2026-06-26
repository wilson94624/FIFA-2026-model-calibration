# 10. 比分分布與模型極限研究

## 為什麼會開始研究這個問題

FIFA Predictor 4.0 上線後，本研究發現一個現象。

模型在勝平負機率上的表現其實不差，但在正確比分上，常常出現：

```text
預測：
France 2-0 Iraq

實際：
France 4-0 Iraq
```

或：

```text
預測：
Portugal 2-0 弱隊

實際：
Portugal 5-0 弱隊
```

這讓此研究線開始懷疑：

> 模型是否系統性低估大比分？

尤其 2026 世界盃擴編至 48 隊後，理論上強弱差距會比過去更大。

因此，此研究線開始了一系列研究，希望找出模型是否真的存在「大比分低估」問題，以及問題究竟來自哪裡。

---

## 第一個假設：強隊其實不夠強

最直覺的想法是：

> Elo 雖然能反映強弱，但可能還不夠。

於是設計了 Domination Layer。

核心想法是：

```text
Normal Mode      70%
Domination Mode  30%
```

當 Elo 差距很大時，額外提高強隊的進攻能力。

理論上應該能增加：

```text
3-0
4-0
5-0
```

等比分的機率。

### 結果

Benchmark 結果令人意外。

Domination Layer 確實讓大比分機率增加。

但：

- LogLoss 沒有改善
- Brier 沒有改善
- Accuracy 沒有改善
- Top-3 Correct Score 幾乎沒有改善

改善幅度甚至小到只有千分位等級。

### 結論

單純把強隊變得更強，不會讓模型更準。

因此 Domination Layer 被保留在研究區，不進正式模型。

---

## 第二個假設：模型低估了大比分尾端

接著，此研究線觀察到：

實際資料中：

```text
GD >= 3
```

出現頻率高於模型預測。

Score Tail Calibration Report 顯示：

| 指標 | 實際 | 模型 |
|--------|--------|--------|
| GD ≥ 3 | 16.41% | 13.76% |

模型低估約：

```text
2.65%
```

因此產生一個假設：

> 模型的尾端太薄。

---

## 第三個假設：直接修正尾端

於是開始研究：

### Margin Tail Correction

以及：

### Conditional Tail Correction

希望把一部分：

```text
2球差
```

重新分配到：

```text
3球差以上
```

### 結果

在全部資料上：

確實有改善。

但一旦做 Split Validation：

- FIFA World Cup
- UEFA Euro
- Modern Era
- Recent Era

結果開始不穩定。

有些資料集變好。

有些資料集變差。

### 結論

Tail Correction 可能只是在擬合特定年代的大比分資料。

無法證明具有普遍性。

因此不適合進正式模型。

---

## 第四個假設：Poisson 本身就是問題

研究一路做到這裡。

開始出現新的疑問。

也許：

> 問題根本不是參數。

而是比分分布本身。

目前正式模型使用：

```text
Bivariate Poisson
```

搭配：

- Dixon-Coles
- Gamma
- Score Matrix

### Poisson 的核心假設

Poisson 家族本質上認為：

```text
每一次進球
近似獨立發生
```

因此：

```text
2-0
3-0
```

的機率會快速下降。

但真實足球中：

```text
1-0
↓
弱隊崩盤
↓
3-0
↓
4-0
```

這種現象並不少見。

因此開始研究：

### Negative Binomial

---

## 第五個假設：Negative Binomial 能解決問題

Negative Binomial 比 Poisson 有更厚的尾端。

理論上：

```text
4-0
5-0
6-0
```

機率應該更高。

因此很符合本研究最初的直覺。

### Benchmark 結果

結果再次出乎意料。

Negative Binomial：

改善：

- Top-5
- 部分 High-Mismatch LogLoss
- 部分 GD Tail

但同時：

惡化：

- Top-3
- Pooled LogLoss
- Brier

### 為什麼？

因為 Negative Binomial 並不是：

```text
只增加 5-0
```

而是：

```text
把整個分布撐開
```

所以：

```text
4-0 ↑
5-0 ↑
```

同時：

```text
0-0 ↑
1-1 ↑
0-1 ↑
```

也會增加。

結果導致：

- Top-5 上升
- Top-3 不一定上升

---

## 最令人意外的發現

研究一開始的想法是：

> Poisson 太保守。

但研究最後得到的答案反而是：

> Poisson 可能沒有想像中那麼錯。

因為如果問題真的來自 Poisson。

那 Negative Binomial 應該全面碾壓。

但結果並沒有。

---

## 本研究真正學到的事情

研究做到這裡後。

研究做到這裡後，一個結論開始變得清楚：

問題可能不是模型太弱。

而是足球本身太難預測。

足球有幾個特性：

- 低得分
- 高變異
- 高偶然性

例如：

- 紅牌
- 點球
- VAR
- 門將失誤
- 傷病

都可能大幅改變結果。

因此：

```text
Correct Score
```

本來就是足球裡最難預測的市場之一。

---

## 48 隊世界盃帶來的誤導

在研究過程中，2026 世界盃擴編曾經影響問題 framing。

例如：

```text
葡萄牙 5-0
德國 7-1
```

這類比賽會讓人產生一種感覺：

> 模型是不是完全抓不到大比分？

但 Large Margin Frequency Report 顯示：

大比分確實存在。

然而：

它們主要集中在：

- World Cup Group Stage
- Elo Mismatch 極大的比賽
- 舊年代世界盃

而不是所有比賽。

如果為了這些極端案例修改整體模型，

很可能反而傷害：

- 淘汰賽
- 強強對決
- 現代足球比賽

因此：

> 不能因為少數 7-1、5-0 而重寫整個模型。

---

## 對產品的影響

這項研究也改變了產品定位。

產品定位不再追求：

> 正確比分神器

因為研究顯示：

即使改變尾端分布，也很難得到大幅提升。

因此產品價值應該放在：

- 勝平負機率
- 奪冠模擬
- 風險分析
- 模型解釋
- 不確定性呈現

而不是宣稱能精準猜中：

```text
4-0
5-0
3-1
```

等單一比分。

---

## 目前結論

截至目前研究結果：

- Domination Layer：否決
- Global Tail Correction：否決
- Conditional Tail Correction：否決
- Negative Binomial：保留研究價值，但不取代正式模型

正式模型仍維持：

```text
Calibrated Elo
↓
xG
↓
Bivariate Poisson
↓
Dixon-Coles
↓
Score Matrix
```

---

## 未來研究方向

目前最有潛力的方向已經不再是：

```text
再找一個放大器
```

而是：

```text
找新的資訊
```

例如：

- Dynamic Team PQS / Injury / Availability
- Availability Correction
- Host Advantage
- Fatigue
- Style Matchup

因為這些資訊有機會提供 Elo 看不到的新訊號。

而不是重複描述：

> 強隊比較強。

---

## 寫在最後

這一章最大的收穫，不是找到新的模型。

而是理解了一件事：

> 有些時候，模型沒有進步，不是因為模型太差，而是因為問題本身就非常困難。

對足球預測而言，

接受不確定性，

可能和提升準確率一樣重要。

而對 FIFA Predictor 來說，

這也是 Calibration Lab 研究至今最重要的一個發現。

---

## Final Decision

最後這篇的決策是：不要為了少數 rare blowouts 重寫整個正式模型。

正式維持 Bivariate Poisson、Dixon-Coles、Gamma 和目前 score matrix，不採用 Domination Layer、Global Tail Correction、Conditional Tail Correction 或 Negative Binomial replacement。

原因是 Correct Score 本來就是高變異問題。部分方法能改善某些比分排序或 high-mismatch subset，但沒有穩定改善整體 LogLoss / Brier。未來可以繼續做 score-tail monitoring，但產品定位應以勝平負機率、風險分析與不確定性呈現為主。
