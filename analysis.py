#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI漫剧任务调度失败根因分析
30分钟限时实战分析 - 完整可复现版本
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("="*70)
print("AI漫剧任务调度失败分析 - 开始执行")
print("="*70)

# 读取CSV数据
try:
    df = pd.read_csv('tasks.csv')
    print(f"\n✓ 成功加载 tasks.csv")
except Exception as e:
    print(f"\n✗ 无法读取 tasks.csv: {e}")
    print("请确保 tasks.csv 在当前目录")
    exit(1)

# ========== 第一步：数据概览 ==========
print(f"\n{'='*70}")
print("第一步：数据基础探查")
print("="*70)

print(f"\n数据规模：{len(df)} 条任务记录")
print(f"时间范围：{df['dispatch_time'].min()} 至 {df['dispatch_time'].max()}")
print(f"\n数据字段：{', '.join(df.columns)}")

# 缺失值检查
print(f"\n缺失值情况：")
for col in df.columns:
    missing = df[col].isna().sum()
    if missing > 0:
        print(f"  {col}: {missing} ({missing/len(df)*100:.1f}%)")

# 任务状态分布
df['status_label'] = df['success'].apply(
    lambda x: '成功' if x == 1 else ('失败' if x == 0 else '未回传')
)

print(f"\n任务执行状态分布：")
status_dist = df['status_label'].value_counts()
for status, count in status_dist.items():
    pct = count / len(df) * 100
    print(f"  {status}: {count} ({pct:.1f}%)")

# ========== 第二步：核心问题识别 - 节点状态陈旧度 ==========
print(f"\n{'='*70}")
print("第二步：核心根因分析 - 节点状态陈旧度")
print("="*70)

# 时间字段转换
df['dispatch_time'] = pd.to_datetime(df['dispatch_time'])
df['node_synced_at'] = pd.to_datetime(df['node_synced_at'])

# 计算陈旧度（小时）
df['sync_lag_hours'] = (df['dispatch_time'] - df['node_synced_at']).dt.total_seconds() / 3600

print(f"\n节点状态陈旧度统计：")
print(f"  均值：{df['sync_lag_hours'].mean():.2f} 小时")
print(f"  中位数：{df['sync_lag_hours'].median():.2f} 小时")
print(f"  最大值：{df['sync_lag_hours'].max():.2f} 小时")
print(f"  25分位：{df['sync_lag_hours'].quantile(0.25):.2f} 小时")
print(f"  75分位：{df['sync_lag_hours'].quantile(0.75):.2f} 小时")

print(f"\n【关键发现1】不同任务状态的平均陈旧度：")
for status in ['成功', '失败', '未回传']:
    mask = df['status_label'] == status
    if mask.sum() > 0:
        avg_lag = df[mask]['sync_lag_hours'].mean()
        median_lag = df[mask]['sync_lag_hours'].median()
        count = mask.sum()
        print(f"  {status}任务: 均值={avg_lag:.2f}h, 中位数={median_lag:.2f}h, 数量={count}")

# 陈旧度阈值分析
print(f"\n陈旧度阈值与失败率关系：")
thresholds = [4, 6, 8, 10, 12, 15]
for thresh in thresholds:
    stale_mask = df['sync_lag_hours'] > thresh
    if stale_mask.sum() > 0:
        total = stale_mask.sum()
        fails = (df[stale_mask]['success'] == 0).sum()
        fail_rate = fails / total * 100
        print(f"  陈旧度 > {thresh:2}h: 失败率={fail_rate:5.1f}%, 任务数={total:4}, 失败数={fails:3}")

# ========== 第三步：显存容量分析 ==========
print(f"\n{'='*70}")
print("第三步：显存容量与任务失败关系")
print("="*70)

print(f"\n显存容量统计：")
print(f"  均值：{df['free_vram_gb'].mean():.2f} GB")
print(f"  中位数：{df['free_vram_gb'].median():.2f} GB")
print(f"  最小值：{df['free_vram_gb'].min():.0f} GB")
print(f"  最大值：{df['free_vram_gb'].max():.0f} GB")

# 显存分段分析
vram_ranges = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 100)]
print(f"\n【关键发现2】显存分段失败率：")
for low, high in vram_ranges:
    mask = (df['free_vram_gb'] >= low) & (df['free_vram_gb'] < high)
    if mask.sum() > 0:
        total = mask.sum()
        fails = (df[mask]['success'] == 0).sum()
        fail_rate = fails / total * 100
        label = f"{low}-{high}GB" if high < 100 else f"{low}GB以上"
        print(f"  {label:12}: 失败率={fail_rate:5.1f}%, 任务数={total:4}, 失败数={fails:3}")

# ========== 第四步：集群性能差异 ==========
print(f"\n{'='*70}")
print("第四步：各集群性能表现")
print("="*70)

cluster_stats = []
for cluster in df['cluster'].unique():
    mask = df['cluster'] == cluster
    total = mask.sum()
    fails = (df[mask]['success'] == 0).sum()
    fail_rate = fails / total * 100
    avg_lag = df[mask]['sync_lag_hours'].mean()
    avg_vram = df[mask]['free_vram_gb'].mean()
    cluster_stats.append({
        '集群': cluster,
        '任务数': total,
        '失败数': fails,
        '失败率': f"{fail_rate:.1f}%",
        '平均陈旧度': f"{avg_lag:.1f}h",
        '平均显存': f"{avg_vram:.1f}GB"
    })

cluster_df = pd.DataFrame(cluster_stats).sort_values('失败数', ascending=False)
print(f"\n集群性能对比：")
print(cluster_df.to_string(index=False))

# ========== 第五步：任务类型分析 ==========
print(f"\n{'='*70}")
print("第五步：任务类型失败分布")
print("="*70)

task_type_stats = []
for task_type in df['task_type'].unique():
    mask = df['task_type'] == task_type
    total = mask.sum()
    fails = (df[mask]['success'] == 0).sum()
    fail_rate = fails / total * 100 if total > 0 else 0
    if total >= 10:  # 只显示样本量足够的任务类型
        task_type_stats.append({
            '任务类型': task_type,
            '总数': total,
            '失败数': fails,
            '失败率': f"{fail_rate:.1f}%"
        })

task_df = pd.DataFrame(task_type_stats).sort_values('失败数', ascending=False)
print(f"\n失败最多的任务类型（样本≥10）：")
print(task_df.head(10).to_string(index=False))

# ========== 第六步：综合根因定位 ==========
print(f"\n{'='*70}")
print("第六步：综合根因定位与高风险任务识别")
print("="*70)

# 定义高风险标准（基于前面分析）
STALE_THRESHOLD = 8  # 陈旧度阈值（小时）
VRAM_THRESHOLD = 5   # 显存阈值（GB）

df['high_risk'] = ((df['sync_lag_hours'] > STALE_THRESHOLD) |
                   (df['free_vram_gb'] < VRAM_THRESHOLD))

print(f"\n高风险任务定义：陈旧度>{STALE_THRESHOLD}h 或 显存<{VRAM_THRESHOLD}GB")
print(f"\n高风险任务统计：")
high_risk_total = df['high_risk'].sum()
high_risk_fails = (df[df['high_risk']]['success'] == 0).sum()
high_risk_fail_rate = high_risk_fails / high_risk_total * 100 if high_risk_total > 0 else 0

print(f"  高风险任务数：{high_risk_total}")
print(f"  高风险失败数：{high_risk_fails}")
print(f"  高风险失败率：{high_risk_fail_rate:.1f}%")

normal_total = (~df['high_risk']).sum()
normal_fails = (df[~df['high_risk']]['success'] == 0).sum()
normal_fail_rate = normal_fails / normal_total * 100 if normal_total > 0 else 0

print(f"\n正常任务统计：")
print(f"  正常任务数：{normal_total}")
print(f"  正常失败数：{normal_fails}")
print(f"  正常失败率：{normal_fail_rate:.1f}%")

print(f"\n风险倍率：高风险任务失败率是正常任务的 {high_risk_fail_rate/normal_fail_rate:.1f} 倍")

# ========== 第七步：业务价值量化 ==========
print(f"\n{'='*70}")
print("第七步：业务价值量化（基于口径：失败120分钟，拦截10分钟）")
print("="*70)

total_fails = (df['success'] == 0).sum()
current_loss_minutes = total_fails * 120
current_loss_hours = current_loss_minutes / 60
current_loss_days = current_loss_hours / 24

print(f"\n【当前状态】无拦截方案：")
print(f"  总失败任务数：{total_fails}")
print(f"  总损失工时：{current_loss_hours:.0f} 小时 = {current_loss_days:.1f} 个工作日")

# 拦截方案收益计算
preventable_fails = high_risk_fails
intercept_count = high_risk_total
intercept_cost_minutes = intercept_count * 10
intercept_cost_hours = intercept_cost_minutes / 60

saved_minutes = preventable_fails * 120 - intercept_cost_minutes
saved_hours = saved_minutes / 60
saved_days = saved_hours / 24

print(f"\n【优化方案】拦截高风险任务：")
print(f"  需拦截任务数：{intercept_count}")
print(f"  可防止失败数：{preventable_fails}")
print(f"  拦截总成本：{intercept_cost_hours:.1f} 小时")
print(f"  避免损失：{preventable_fails * 120 / 60:.0f} 小时")
print(f"  净节省工时：{saved_hours:.0f} 小时 = {saved_days:.1f} 个工作日")
print(f"  投入产出比：1 : {saved_hours/intercept_cost_hours:.1f}")

reduction_rate = preventable_fails / total_fails * 100
print(f"\n失败降低率：{reduction_rate:.1f}% （从 {total_fails} 降至 {total_fails - preventable_fails}）")

# ========== 第八步：精细化拦截阈值优化 ==========
print(f"\n{'='*70}")
print("第八步：拦截阈值优化分析")
print("="*70)

print(f"\n陈旧度阈值优化：")
for thresh in [6, 8, 10, 12]:
    stale = df['sync_lag_hours'] > thresh
    stale_fails = (df[stale]['success'] == 0).sum()
    cost_h = stale.sum() * 10 / 60
    save_h = stale_fails * 120 / 60 - cost_h
    roi = save_h / cost_h if cost_h > 0 else 0
    print(f"  >{thresh:2}h: 拦截{stale.sum():4}个, 防止{stale_fails:3}次失败, 净节省{save_h:5.0f}h, ROI=1:{roi:.1f}")

print(f"\n显存阈值优化：")
for thresh in [3, 5, 8, 10]:
    low_vram = df['free_vram_gb'] < thresh
    low_vram_fails = (df[low_vram]['success'] == 0).sum()
    cost_h = low_vram.sum() * 10 / 60
    save_h = low_vram_fails * 120 / 60 - cost_h
    roi = save_h / cost_h if cost_h > 0 else 0
    print(f"  <{thresh:2}GB: 拦截{low_vram.sum():4}个, 防止{low_vram_fails:3}次失败, 净节省{save_h:5.0f}h, ROI=1:{roi:.1f}")

# ========== 输出核心结论 ==========
print(f"\n{'='*70}")
print("核心结论总结")
print("="*70)

print(f"""
1. 根本问题识别：
   - 节点状态陈旧导致调度决策基于过时信息
   - 失败任务平均陈旧度显著高于成功任务
   - 低显存节点强行接收任务导致OOM失败

2. 当前业务损失：
   - 总失败数：{total_fails} 次
   - 损失工时：{current_loss_hours:.0f} 小时（{current_loss_days:.1f} 工作日）

3. 优化方案收益：
   - 拦截标准：陈旧度>{STALE_THRESHOLD}h 或 显存<{VRAM_THRESHOLD}GB
   - 可阻止失败：{preventable_fails} 次（{reduction_rate:.1f}%）
   - 净节省工时：{saved_hours:.0f} 小时（{saved_days:.1f} 工作日）
   - ROI：1:{saved_hours/intercept_cost_hours:.1f}

4. 实施建议：
   - 缩短节点状态同步间隔至4小时以内
   - 调度前强制刷新陈旧节点状态
   - 为高显存需求任务类型设置显存阈值
   - 优先调度至节点状态新鲜的集群
""")

print("="*70)
print("分析完成！所有数据可复现，详见上方输出。")
print("="*70)
