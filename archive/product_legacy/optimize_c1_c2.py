# -*- coding: utf-8 -*-
import os
import pandas as pd
import numpy as np
from scipy.optimize import minimize

backend_dir = os.path.dirname(os.path.abspath(__file__))
archive_dir = os.path.join(backend_dir, "archive")

# 1. 隊伍名稱對齊
name_mapping = {
    # 常用映射
    'United States': 'USA',
    'Czech Republic': 'Czechia',
    'Cape Verde': 'Cabo Verde',
    'Democratic Republic of the Congo': 'Congo DR',
    'DR Congo': 'Congo DR',
    'Curaçao': 'Curacao',
    'Korea Republic': 'South Korea',
    'South Korea': 'South Korea',
    "Cote d'Ivoire": 'Ivory Coast',
    "Côte d'Ivoire": 'Ivory Coast',
    'Türkiye': 'Turkey',
    'Turkiye': 'Turkey',
    'Bosnia & Herzegovina': 'Bosnia and Herzegovina',
}

def clean_team_name(name):
    if not isinstance(name, str):
        return ""
    name = name.strip()
    return name_mapping.get(name, name)

# 2. 建立 ELO 與 PQS 對照字典
# 優先從 train (1).csv 和 test (2).csv 讀取。如果沒有，則用 default
team_stats = {}

# 預設一些常見隊伍的數值（以防萬一）
default_stats = {
    'Czechia': {'elo': 1500.0, 'rating': 76.5},
    'Bosnia and Herzegovina': {'elo': 1330.0, 'rating': 74.0},
    'Cabo Verde': {'elo': 1380.0, 'rating': 72.0},
    'Georgia': {'elo': 1400.0, 'rating': 73.0},
    'Scotland': {'elo': 1480.0, 'rating': 75.5},
    'Hungary': {'elo': 1510.0, 'rating': 76.0},
    'Albania': {'elo': 1375.0, 'rating': 72.5},
    'Slovakia': {'elo': 1460.0, 'rating': 75.0},
    'Slovenia': {'elo': 1430.0, 'rating': 74.0},
    'Romania': {'elo': 1450.0, 'rating': 74.5},
    'Ukraine': {'elo': 1560.0, 'rating': 77.0},
    'Serbia': {'elo': 1515.0, 'rating': 76.5},
    'Denmark': {'elo': 1610.0, 'rating': 79.5},
    'Jamaica': {'elo': 1400.0, 'rating': 72.0},
    'Venezuela': {'elo': 1440.0, 'rating': 73.5},
    'Bolivia': {'elo': 1300.0, 'rating': 70.0},
    'Panama': {'elo': 1410.0, 'rating': 72.5},
    'Costa Rica': {'elo': 1435.0, 'rating': 73.0},
    'Chile': {'elo': 1490.0, 'rating': 76.0},
    'Peru': {'elo': 1480.0, 'rating': 75.0},
    'Canada': {'elo': 1480.0, 'rating': 75.0},
    'Morocco': {'elo': 1660.0, 'rating': 81.0},
    'Egypt': {'elo': 1520.0, 'rating': 77.5},
    'Senegal': {'elo': 1620.0, 'rating': 80.0},
    'Nigeria': {'elo': 1500.0, 'rating': 78.0},
    'Algeria': {'elo': 1510.0, 'rating': 77.0},
    'Tunisia': {'elo': 1500.0, 'rating': 75.5},
    'Mali': {'elo': 1480.0, 'rating': 76.0},
    'South Africa': {'elo': 1410.0, 'rating': 73.5},
    'Angola': {'elo': 1360.0, 'rating': 71.5},
    'Zambia': {'elo': 1300.0, 'rating': 70.5},
    'Zimbabwe': {'elo': 1250.0, 'rating': 69.0},
    'Benin': {'elo': 1280.0, 'rating': 70.0},
    'Botswana': {'elo': 1180.0, 'rating': 66.0},
    'Tanzania': {'elo': 1200.0, 'rating': 67.5},
    'Uganda': {'elo': 1240.0, 'rating': 68.0},
    'Equatorial Guinea': {'elo': 1320.0, 'rating': 72.0},
    'Sudan': {'elo': 1210.0, 'rating': 67.0},
    'Mozambique': {'elo': 1220.0, 'rating': 68.0},
    'Gabon': {'elo': 1380.0, 'rating': 73.5},
    'Comoros': {'elo': 1200.0, 'rating': 67.0},
    'Burkina Faso': {'elo': 1400.0, 'rating': 74.0},
    'Guinea': {'elo': 1400.0, 'rating': 74.5},
    'Mauritania': {'elo': 1250.0, 'rating': 69.5},
}

train_path = os.path.join(archive_dir, "train (1).csv")
test_path = os.path.join(archive_dir, "test (2).csv")

# 讀取本地特徵數據集
for path in [train_path, test_path]:
    if os.path.exists(path):
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            team = clean_team_name(row['team_name'])
            # 優先保留先前的數據，或取平均
            team_stats[team] = {
                'elo': float(row['fifa_points']),
                'rating': float(row['avg_player_rating'])
            }

# 用預設補齊缺失
for team, stats in default_stats.items():
    cleaned_t = clean_team_name(team)
    if cleaned_t not in team_stats:
        team_stats[cleaned_t] = stats

# 將 rating 轉換為 PQS
for team in team_stats:
    # 根據前進度 PQS = (overall - 50) / 100
    r = team_stats[team]['rating']
    team_stats[team]['pqs'] = max(0.01, (r - 50.0) / 100.0)

# 3. 解析真實盃賽數據
all_matches = []

# 解析 Euro 2024 (東道主德國 Germany)
euro_path = os.path.join(archive_dir, "Euro_2024_Matches.csv")
if os.path.exists(euro_path):
    df_euro = pd.read_csv(euro_path)
    for _, row in df_euro.iterrows():
        h = clean_team_name(row['home_team'])
        a = clean_team_name(row['away_team'])
        hg = int(row['home_goals'])
        ag = int(row['away_goals'])
        # 德國是東道主
        is_home_host = (h == 'Germany')
        is_away_host = (a == 'Germany')
        all_matches.append({
            'home': h, 'away': a, 'home_goals': hg, 'away_goals': ag,
            'is_home_host': is_home_host, 'is_away_host': is_away_host,
            'source': 'Euro 2024'
        })

# 解析 Copa America 2024 (東道主美國 USA)
copa_path = os.path.join(archive_dir, "Copa_2024_Matches.csv")
if os.path.exists(copa_path):
    df_copa = pd.read_csv(copa_path)
    for _, row in df_copa.iterrows():
        h = clean_team_name(row['home_team'])
        a = clean_team_name(row['away_team'])
        hg = int(row['home_goals'])
        ag = int(row['away_goals'])
        # 美國是東道主
        is_home_host = (h == 'USA')
        is_away_host = (a == 'USA')
        all_matches.append({
            'home': h, 'away': a, 'home_goals': hg, 'away_goals': ag,
            'is_home_host': is_home_host, 'is_away_host': is_away_host,
            'source': 'Copa 2024'
        })

# 解析 AFCON 2025-26 (東道主摩洛哥 Morocco)
afcon_path = os.path.join(archive_dir, "afcon_2025_2026_dataset.csv")
if os.path.exists(afcon_path):
    df_afcon = pd.read_csv(afcon_path, on_bad_lines='skip')
    for _, row in df_afcon.iterrows():
        h = clean_team_name(row['Team1'])
        a = clean_team_name(row['Team2'])
        
        # 解析比分 "2 - 0"
        score_str = str(row['Score (Team1 - Team2)'])
        try:
            hg, ag = map(int, score_str.replace(" ", "").split("-"))
        except Exception:
            continue
            
        # 摩洛哥是東道主
        is_home_host = (h == 'Morocco')
        is_away_host = (a == 'Morocco')
        
        all_matches.append({
            'home': h, 'away': a, 'home_goals': hg, 'away_goals': ag,
            'is_home_host': is_home_host, 'is_away_host': is_away_host,
            'source': 'AFCON 2025-26'
        })

print(f"Total parsed matches: {len(all_matches)}")

# 4. 準備擬合數據
valid_matches = []
missing_teams = set()

for m in all_matches:
    h, a = m['home'], m['away']
    if h not in team_stats:
        missing_teams.add(h)
    if a not in team_stats:
        missing_teams.add(a)
        
    if h in team_stats and a in team_stats:
        m['elo_h'] = team_stats[h]['elo']
        m['elo_a'] = team_stats[a]['elo']
        m['pqs_h'] = team_stats[h]['pqs']
        m['pqs_a'] = team_stats[a]['pqs']
        valid_matches.append(m)

print(f"Valid matches with team stats: {len(valid_matches)}")
if missing_teams:
    print(f"Missing team stats for: {list(missing_teams)}")

# 5. 極大似然估計擬合 c1, c2
# 泊松分佈概率函數
def poisson_prob(k, lamb):
    return (lamb**k * np.exp(-lamb)) / np.math.factorial(k) if lamb > 0 else 0.0

def loss_func(params):
    c1, c2 = params
    neg_log_lik = 0.0
    
    for m in valid_matches:
        # 決定基礎值
        base_h = 1.2
        base_a = 1.2
        if m['is_home_host']:
            base_h, base_a = 1.3, 1.1
        elif m['is_away_host']:
            base_h, base_a = 1.1, 1.3
            
        # 計算 lambda_h 和 lambda_a (依照 ELO 與 PQS 解耦期望值公式)
        lamb_h = max(0.1, base_h + c1 * (m['elo_h'] - m['elo_a']) / 450.0 + c2 * (m['pqs_h'] - m['pqs_a']) / 0.3)
        lamb_a = max(0.1, base_a - c1 * (m['elo_h'] - m['elo_a']) / 450.0 + c2 * (m['pqs_a'] - m['pqs_h']) / 0.3)
        
        prob_h = poisson_prob(m['home_goals'], lamb_h)
        prob_a = poisson_prob(m['away_goals'], lamb_a)
        
        # 加上微小值防止 log(0)
        p = max(1e-9, prob_h * prob_a)
        neg_log_lik -= np.log(p)
        
    return neg_log_lik

# 敏感度分析：測試不同 c2 (PQS) 最小約束下的最佳 c1
c2_min_constraints = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]

print("\n=== Sensitivity Analysis (c2_min vs optimal c1) ===")
print(f"{'c2_min':<10} | {'Optimal c1':<12} | {'Optimal c2':<12} | {'Negative Log-Likelihood Loss':<30}")
print("-" * 75)

best_configs = {}

for c2_min in c2_min_constraints:
    initial_guess = [0.60, max(0.40, c2_min)]
    # 約束 c2 >= c2_min
    bounds = ((0.0, 2.0), (c2_min, 2.0))
    
    result = minimize(loss_func, initial_guess, bounds=bounds, method='L-BFGS-B')
    if result.success:
        opt_c1, opt_c2 = result.x
        print(f"{c2_min:<10.2f} | {opt_c1:<12.4f} | {opt_c2:<12.4f} | {result.fun:<30.4f}")
        best_configs[c2_min] = (opt_c1, opt_c2, result.fun)
    else:
        print(f"{c2_min:<10.2f} | Optimization Failed")

# 以無約束最優為基準，展示擬合誤差
print("\n=== Detailed Summary of Selected Configs ===")
for c2_min, (opt_c1, opt_c2, loss) in best_configs.items():
    pred_h_sum, pred_a_sum = 0.0, 0.0
    for m in valid_matches:
        base_h = 1.3 if m['is_home_host'] else (1.1 if m['is_away_host'] else 1.2)
        base_a = 1.1 if m['is_home_host'] else (1.3 if m['is_away_host'] else 1.2)
        pred_h_sum += max(0.1, base_h + opt_c1 * (m['elo_h'] - m['elo_a']) / 450.0 + opt_c2 * (m['pqs_h'] - m['pqs_a']) / 0.3)
        pred_a_sum += max(0.1, base_a - opt_c1 * (m['elo_h'] - m['elo_a']) / 450.0 + opt_c2 * (m['pqs_a'] - m['pqs_h']) / 0.3)
    
    total_real_home_goals = sum(m['home_goals'] for m in valid_matches)
    total_real_away_goals = sum(m['away_goals'] for m in valid_matches)
    
    print(f"Constraint c2 >= {c2_min:.2f}:")
    print(f"  c1={opt_c1:.4f}, c2={opt_c2:.4f} | Loss={loss:.3f}")
    print(f"  Real Goals: Home={total_real_home_goals}, Away={total_real_away_goals}")
    print(f"  Pred Goals: Home={pred_h_sum:.2f}, Away={pred_a_sum:.2f}")
    print(f"  Goal Diff Bias: Home={pred_h_sum - total_real_home_goals:+.2f}, Away={pred_a_sum - total_real_away_goals:+.2f}\n")

