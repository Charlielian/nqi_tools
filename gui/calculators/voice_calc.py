# -*- coding: utf-8 -*-
"""
4G语音小区计算列模块

从 main_window.py 的 _add_4g_voice_calc_columns 提取，纯函数，与 GUI 解耦。

计算规则：
- 4G语音通话质差时长比例 = (VoLTE语音上行吞字时长+VoLTE语音上行单通时长+VoLTE语音上行断续时长+EPSFB语音上行吞字时长+EPSFB语音上行单通时长+EPSFB语音上行断续时长) / (VoLTE语音上行总时长+EPSFB语音上行总时长)
- 4G差小区 = (VoLTE语音通话质差时长比例>2% 且 VoLTE通话次数>1000) 或者 (EPSFB语音通话质差时长比例>2% 且 EPSFB通话次数>1000)

计算结果中的比例统一按百分数数值保存：2% 的阈值比较写成 ``> 2``，
而不是把已经乘过100的结果再与0.02比较。缺字段时模块保守地记录告警，
不伪造指标，最终仍返回传入的 DataFrame 对象。
"""

import numpy as np


def _detect_voice_columns(df):
    """从 DataFrame 列名中自动识别 VoLTE / EPSFB 相关字段

    先尝试中文字段名匹配，再降级到英文字段名匹配。

    Returns:
        dict: 包含所有识别的字段列名
    """
    # 先识别列名而不是假设固定模板：后端既可能返回中文展示名，也可能
    # 返回旧版英文物理字段名。识别结果只保存“实际列名”，后续计算才
    # 能在不改动源表列顺序的情况下兼容两种协议。
    # 中文匹配
    volte_ul_tunzi = None
    volte_ul_dantong = None
    volte_ul_duanxu = None
    volte_ul_sum = None
    volte_call = None
    epsfb_ul_tunzi = None
    epsfb_ul_dantong = None
    epsfb_ul_duanxu = None
    epsfb_ul_sum = None
    epsfb_call = None

    for col in df.columns:
        col_lower = col.lower()
        if 'volte' in col_lower and '上行' in col and '吞字' in col:
            volte_ul_tunzi = col
        elif 'volte' in col_lower and '上行' in col and '单通' in col:
            volte_ul_dantong = col
        elif 'volte' in col_lower and '上行' in col and '断续' in col:
            volte_ul_duanxu = col
        elif 'volte' in col_lower and '上行' in col and '总时长' in col:
            volte_ul_sum = col
        elif 'volte' in col_lower and ('通话次数' in col or '语音通话总次数' in col):
            volte_call = col
        elif 'epsfb' in col_lower and '上行' in col and '吞字' in col:
            epsfb_ul_tunzi = col
        elif 'epsfb' in col_lower and '上行' in col and '单通' in col:
            epsfb_ul_dantong = col
        elif 'epsfb' in col_lower and '上行' in col and '断续' in col:
            epsfb_ul_duanxu = col
        elif 'epsfb' in col_lower and '上行' in col and '总时长' in col:
            epsfb_ul_sum = col
        elif 'epsfb' in col_lower and ('通话次数' in col or '语音通话总次数' in col):
            epsfb_call = col

    # 降级：英文列名匹配
    if volte_ul_tunzi is None:
        for col in df.columns:
            if 'volte_ul_tunzi' in col.lower():
                volte_ul_tunzi = col
                break
    if volte_ul_dantong is None:
        for col in df.columns:
            if 'volte_ul_dantong' in col.lower():
                volte_ul_dantong = col
                break
    if volte_ul_duanxu is None:
        for col in df.columns:
            if 'volte_ul_duanxu' in col.lower():
                volte_ul_duanxu = col
                break
    if volte_ul_sum is None:
        for col in df.columns:
            if 'volte_ul_voice_sum' in col.lower():
                volte_ul_sum = col
                break
    if volte_call is None:
        for col in df.columns:
            if 'volte_ans_voice' in col.lower():
                volte_call = col
                break
    if epsfb_ul_tunzi is None:
        for col in df.columns:
            if 'epsfb_ul_tunzi' in col.lower():
                epsfb_ul_tunzi = col
                break
    if epsfb_ul_dantong is None:
        for col in df.columns:
            if 'epsfb_ul_dantong' in col.lower():
                epsfb_ul_dantong = col
                break
    if epsfb_ul_duanxu is None:
        for col in df.columns:
            if 'epsfb_ul_duanxu' in col.lower():
                epsfb_ul_duanxu = col
                break
    if epsfb_ul_sum is None:
        for col in df.columns:
            if 'epsfb_ul_voice_sum' in col.lower():
                epsfb_ul_sum = col
                break
    if epsfb_call is None:
        for col in df.columns:
            if 'epsfb_ans_voice' in col.lower():
                epsfb_call = col
                break

    return {
        'volte_ul_tunzi': volte_ul_tunzi,
        'volte_ul_dantong': volte_ul_dantong,
        'volte_ul_duanxu': volte_ul_duanxu,
        'volte_ul_sum': volte_ul_sum,
        'volte_call': volte_call,
        'epsfb_ul_tunzi': epsfb_ul_tunzi,
        'epsfb_ul_dantong': epsfb_ul_dantong,
        'epsfb_ul_duanxu': epsfb_ul_duanxu,
        'epsfb_ul_sum': epsfb_ul_sum,
        'epsfb_call': epsfb_call,
    }


def add_4g_voice_calc_columns(df, log_func=None):
    """添加4G语音小区计算列。

    语音时长字段的物理单位是秒，通话次数是次数；比例计算时分子分母
    使用相同的秒单位，单位相消后乘100得到百分数。NaN 业务上按0参与
    时长/次数求和，但当总时长为0时结果保留 NaN，避免把“没有可计算
    样本”误判为正常质量。只有比例超过2且通话次数超过1000才标记
    VoLTE/EPSFB 差小区，两个制式任一满足即可标记最终结果。

    Args:
        df: 合并后的DataFrame
        log_func: 可选的日志回调函数，签名 log_func(message, level)

    Returns:
        DataFrame: 原对象上添加计算列后的DataFrame
    """
    if log_func is None:
        log_func = lambda msg, level='INFO': None

    cols = _detect_voice_columns(df)

    # 记录找到/缺失的字段
    field_names = {
        'volte_ul_tunzi': 'VoLTE上行吞字',
        'volte_ul_dantong': 'VoLTE上行单通',
        'volte_ul_duanxu': 'VoLTE上行断续',
        'volte_ul_sum': 'VoLTE上行总时长',
        'volte_call': 'VoLTE通话次数',
        'epsfb_ul_tunzi': 'EPSFB上行吞字',
        'epsfb_ul_dantong': 'EPSFB上行单通',
        'epsfb_ul_duanxu': 'EPSFB上行断续',
        'epsfb_ul_sum': 'EPSFB上行总时长',
        'epsfb_call': 'EPSFB通话次数',
    }

    found_fields = []
    missing_fields = []
    for key, name in field_names.items():
        if cols[key]:
            found_fields.append(f"{name}={cols[key][:20]}...")
        else:
            missing_fields.append(name)

    log_func(f"[4G语音计算] 找到字段: {len(found_fields)}, 缺失: {len(missing_fields)}", "INFO")
    if missing_fields:
        log_func(f"[4G语音计算] 缺失字段: {missing_fields}", "WARNING")

    # 质差时长比例的单位是百分数：总时长大于0才有分母。这里使用
    # fillna(0) 处理缺测片段，但不把总时长为0的行写成0%，而是写成
    # NaN，供上层区分“无样本”和“确实没有质差时长”。
    if all(cols[k] is not None for k in [
        'volte_ul_tunzi', 'volte_ul_dantong', 'volte_ul_duanxu',
        'volte_ul_sum', 'epsfb_ul_tunzi', 'epsfb_ul_dantong',
        'epsfb_ul_duanxu', 'epsfb_ul_sum'
    ]):
        total_bad = (
            df[cols['volte_ul_tunzi']].fillna(0) +
            df[cols['volte_ul_dantong']].fillna(0) +
            df[cols['volte_ul_duanxu']].fillna(0) +
            df[cols['epsfb_ul_tunzi']].fillna(0) +
            df[cols['epsfb_ul_dantong']].fillna(0) +
            df[cols['epsfb_ul_duanxu']].fillna(0)
        )
        total_sum = df[cols['volte_ul_sum']].fillna(0) + df[cols['epsfb_ul_sum']].fillna(0)
        df['4G语音通话质差时长比例'] = np.where(total_sum > 0, (total_bad / total_sum * 100).round(4), np.nan)
        log_func(f"[4G语音计算] 4G语音通话质差时长比例计算完成", "SUCCESS")
    else:
        log_func(f"[4G语音计算] 缺少必要字段，无法计算4G语音通话质差时长比例", "WARNING")

    # 计算VoLTE差小区
    volte_bad_rate = None
    epsfb_bad_rate = None

    if all(cols[k] is not None for k in ['volte_ul_sum', 'volte_ul_tunzi', 'volte_ul_dantong', 'volte_ul_duanxu']):
        volte_total_bad = (
            df[cols['volte_ul_tunzi']].fillna(0) +
            df[cols['volte_ul_dantong']].fillna(0) +
            df[cols['volte_ul_duanxu']].fillna(0)
        )
        volte_total = df[cols['volte_ul_sum']].fillna(0)
        volte_bad_rate = np.where(volte_total > 0, volte_total_bad / volte_total * 100, 0)

    if all(cols[k] is not None for k in ['epsfb_ul_sum', 'epsfb_ul_tunzi', 'epsfb_ul_dantong', 'epsfb_ul_duanxu']):
        epsfb_total_bad = (
            df[cols['epsfb_ul_tunzi']].fillna(0) +
            df[cols['epsfb_ul_dantong']].fillna(0) +
            df[cols['epsfb_ul_duanxu']].fillna(0)
        )
        epsfb_total = df[cols['epsfb_ul_sum']].fillna(0)
        epsfb_bad_rate = np.where(epsfb_total > 0, epsfb_total_bad / epsfb_total * 100, 0)

    if volte_bad_rate is not None and cols['volte_call'] is not None:
        volte_is_bad = (volte_bad_rate > 2) & (df[cols['volte_call']].fillna(0) > 1000)
        bad_volte_count = volte_is_bad.sum()
        log_func(f"[4G语音计算] VoLTE差小区数量: {bad_volte_count}", "INFO")
    else:
        volte_is_bad = np.full(len(df), False, dtype=bool)
        log_func(f"[4G语音计算] 无法计算VoLTE差小区（缺少字段）", "WARNING")

    if epsfb_bad_rate is not None and cols['epsfb_call'] is not None:
        epsfb_is_bad = (epsfb_bad_rate > 2) & (df[cols['epsfb_call']].fillna(0) > 1000)
        bad_epsfb_count = epsfb_is_bad.sum()
        log_func(f"[4G语音计算] EPSFB差小区数量: {bad_epsfb_count}", "INFO")
    else:
        epsfb_is_bad = np.full(len(df), False, dtype=bool)
        log_func(f"[4G语音计算] 无法计算EPSFB差小区（缺少字段）", "WARNING")

    df['4G语音差小区'] = np.where(volte_is_bad | epsfb_is_bad, '是', '否')
    bad_cell_count = (df['4G语音差小区'] == '是').sum()
    log_func(f"[4G语音计算] 4G语音差小区总计: {bad_cell_count}", "SUCCESS")

    return df