# -*- coding: utf-8 -*-
"""
4G/5G 全程完好率计算列模块

从 main_window.py 的 _add_4g_wanchenglv_calc_columns / _add_5g_wanchenglv_calc_columns 提取，
纯函数，与 GUI 解耦。

计算规则（4G）:
- 4G无线接通率(%) = (RRC连接建立成功次数/RRC连接建立请求次数) * (E-RAB建立成功数/E-RAB建立请求数)
- 4G切换成功率(%) = 切换成功次数/切换请求次数
- 4G E-RAB掉线率(%) = (切出失败的E-RAB数 - 正常的eNB请求释放的E-RAB数 + eNB请求释放的E-RAB数)
                           / (遗留上下文个数 + E-RAB建立成功数 + 切换入E-RAB数)
- 4G全程完好率(%) = 4G无线接通率(%) * 4G切换成功率(%) * (100 - 4G E-RAB掉线率(%))
- 4G是否差小区 = 全程完好率 < 85% 时为"是"

计算规则（5G）:
- SA无线接通率(%) = (RRC连接建立成功次数/RRC连接建立请求次数) * (Flow建立成功数/Flow建立请求数)
                    * (NG接口UE相关逻辑信令连接建立成功次数/NG接口UE相关逻辑信令连接建立请求次数)
- SA无线掉线率(%) = (gNB请求释放上下文数 - 正常的gNB请求释放上下文数)
                   / (初始上下文建立成功次数 + 遗留上下文个数 + 切换入成功次数 + RRC连接重建成功次数(非源侧小区))
- SA切换成功率(%) = (gNB间NG切换出成功次数 + gNB间Xn切换出成功次数 + CU内DU间切换出执行成功次数 + CU内DU内切换出成功次数)
                    / (gNB间NG切换出准备请求次数 + gNB间Xn切换出准备请求次数 + CU内DU间切换出执行请求次数 + CU内DU内切换出执行请求次数)
- 5G全程完好率(%) = SA无线接通率(%) * SA切换成功率(%) * (100 - SA无线掉线率(%))
- 5G是否差小区 = 全程完好率 < 85% 时为"是"

所有百分比列都保存为百分数数值而非0到1的小数；因此最终完好率的乘法
仍按百分数业务公式执行，85是85%的阈值。分母为0时返回 NaN，避免
用无效样本制造虚假的高完好率。
"""

import numpy as np


# 4G 字段名映射（英文 -> 标准 key）
_4G_FIELD_MAP = {
    ('succconnestab', 'rrc连接建立成功次数'): 'rrc_succ',
    ('attconnestab', 'rrc连接建立请求次数'): 'rrc_att',
    ('nbrsuccestab', 'e-rab建立成功数'): 'erab_succ',
    ('nbrattestab', 'e-rab建立请求数'): 'erab_att',
    ('ho_succ_out', '切换成功次数'): 'ho_succ',
    ('ho_att__out', '切换请求次数'): 'ho_att',
    ('hofail', '切出失败的e-rab数'): 'ho_fail',
    ('nbrreqrelenb_normal', '正常的enb请求释放的e-rab数'): 'erab_normal_rel',
    ('nbrreqrelenb', 'enb请求释放的e-rab数'): 'erab_rel',
    ('nbrleft', '遗留上下文个数'): 'context_left',
    ('nbrhoinc', '切换入e-rab数'): 'ho_inc',
}

# 5G 字段名映射（英文 -> 标准 key）
_5G_FIELD_MAP = {
    ('rrc_succconnestab', 'rrc连接建立成功次数'): 'rrc_succ',
    ('rrc_attconnestab', 'rrc连接建立请求次数'): 'rrc_att',
    ('flow_nbrsuccestab', 'flow建立成功数'): 'flow_succ',
    ('flow_nbrattestab', 'flow建立请求数'): 'flow_att',
    ('ngsig_connestabsucc', 'ng接口ue相关逻辑信令连接建立成功次数'): 'ngsig_succ',
    ('ngsig_connestabatt', 'ng接口ue相关逻辑信令连接建立请求次数'): 'ngsig_att',
    ('context_attrelgnb', 'gnb请求释放上下文数'): 'context_rel',
    ('context_attrelgnb_normal', '正常的gnb请求释放上下文数'): 'context_rel_normal',
    ('context_succinitalsetup', '初始上下文建立成功次数'): 'context_init_succ',
    ('context_nbrleft', '遗留上下文个数'): 'context_left',
    ('ho_succexecinc', '切换入成功次数'): 'ho_inc_succ',
    ('rrc_succconnreestab_nonsrccell', 'rrc连接重建成功次数(非源侧小区)'): 'rrc_reestab_succ',
    ('ho_succoutintercung', 'gnb间ng切换出成功次数'): 'ho_ng_succ',
    ('ho_succoutintercuxn', 'gnb间xn切换出成功次数'): 'ho_xn_succ',
    ('ho_succoutintracuinterdu', 'cu内du间切换出执行成功次数'): 'ho_cu_du_succ',
    ('ho_succoutintradu', 'cu内du内切换出成功次数'): 'ho_cu_intra_succ',
    ('ho_attoutintercung', 'gnb间ng切换出准备请求次数'): 'ho_ng_att',
    ('ho_attoutintercuxn', 'gnb间xn切换出准备请求次数'): 'ho_xn_att',
    ('ho_attoutintracuinterdu', 'cu内du间切换出执行请求次数'): 'ho_cu_du_att',
    ('ho_attoutcuintradu', 'cu内du内切换出执行请求次数'): 'ho_cu_intra_att',
}


def _build_field_map(df, mapping_table):
    """根据列名别名构建标准 key 到实际列名的映射。

    后端字段可能使用英文物理名或中文展示名；映射只解决协议命名差异，
    不转换原始计数的单位，也不改变 DataFrame。后续公式统一引用标准 key，
    这样计算规则不必为每一种报表模板复制一份。
    """
    field_map = {}
    for col in df.columns:
        col_lower = col.lower() if isinstance(col, str) else ''
        for aliases, key in mapping_table.items():
            if col_lower in aliases:
                field_map[key] = col
                break
    return field_map


def _calc_ratio(df, num_cols, denom_cols, precision=4):
    """计算百分数比率。

    分子和分母都是次数型计数，先把缺测当作0参与汇总，再以分母大于0
    作为有效性门槛，最后乘100得到百分数。precision 参数保留在接口中
    以兼容调用方；具体结果列由调用处统一 round。
    """
    numerator = sum(df[c].fillna(0).astype(float) for c in num_cols)
    denominator = sum(df[c].fillna(0).astype(float) for c in denom_cols)
    return np.where(denominator > 0, numerator / denominator * 100, np.nan)


def add_4g_wanchenglv_calc_columns(df, log_func=None):
    """添加4G全程完好率计算列。

    各项接通/切换/掉线指标先按计数比率转换为百分数，再按业务公式
    计算全程完好率。由于中间指标是百分数，最终公式中的 ``100 - 掉线率``
    表示剩余可用百分点评分；低于85才标记差小区。缺失前置列时只记录
    警告并跳过对应派生列，返回原 DataFrame，便于不完整源表继续导出。

    Args:
        df: 4G全程完好率报表的DataFrame
        log_func: 可选的日志回调函数，签名 log_func(message, level)

    Returns:
        DataFrame: 原对象上添加计算列后的DataFrame
    """
    if log_func is None:
        log_func = lambda msg, level='INFO': None

    field_map = _build_field_map(df, _4G_FIELD_MAP)
    log_func(f"[4G全程完好率] 字段映射: {list(field_map.keys())}", "INFO")

    # 4G 无线接通率是 RRC 接通率与 E-RAB 接通率的乘积；两者本身
    # 都是百分数，乘积后仍按现有业务口径保留数值，不转回0到1。
    # 分母为0的行保留 NaN，避免“没有请求”被误算为100%。
    if all(k in field_map for k in ['rrc_succ', 'rrc_att', 'erab_succ', 'erab_att']):
        rrc_succ = df[field_map['rrc_succ']].fillna(0).astype(float)
        rrc_att = df[field_map['rrc_att']].fillna(0).astype(float)
        erab_succ = df[field_map['erab_succ']].fillna(0).astype(float)
        erab_att = df[field_map['erab_att']].fillna(0).astype(float)

        rrc_rate = np.where(rrc_att > 0, rrc_succ / rrc_att * 100, np.nan)
        erab_rate = np.where(erab_att > 0, erab_succ / erab_att * 100, np.nan)
        df['4G无线接通率(%)'] = np.where(
            (rrc_att > 0) & (erab_att > 0),
            rrc_rate * erab_rate,
            np.nan
        )
        df['4G无线接通率(%)'] = df['4G无线接通率(%)'].round(4)
        valid_count = df['4G无线接通率(%)'].notna().sum()
        log_func(f"[4G全程完好率] 4G无线接通率计算完成, 有效数据: {valid_count}", "SUCCESS")
    else:
        missing = [k for k in ['rrc_succ', 'rrc_att', 'erab_succ', 'erab_att'] if k not in field_map]
        log_func(f"[4G全程完好率] 缺少字段无法计算4G无线接通率: {missing}", "WARNING")

    # ========== 2. 计算4G切换成功率(%) ==========
    if all(k in field_map for k in ['ho_succ', 'ho_att']):
        ho_succ = df[field_map['ho_succ']].fillna(0).astype(float)
        ho_att = df[field_map['ho_att']].fillna(0).astype(float)
        df['4G切换成功率(%)'] = np.where(ho_att > 0, ho_succ / ho_att * 100, np.nan)
        df['4G切换成功率(%)'] = df['4G切换成功率(%)'].round(4)
        valid_count = df['4G切换成功率(%)'].notna().sum()
        log_func(f"[4G全程完好率] 4G切换成功率计算完成, 有效数据: {valid_count}", "SUCCESS")
    else:
        missing = [k for k in ['ho_succ', 'ho_att'] if k not in field_map]
        log_func(f"[4G全程完好率] 缺少字段无法计算4G切换成功率: {missing}", "WARNING")

    # ========== 3. 计算4G E-RAB掉线率(%) ==========
    if all(k in field_map for k in ['ho_fail', 'erab_normal_rel', 'erab_rel', 'context_left', 'erab_succ', 'ho_inc']):
        ho_fail = df[field_map['ho_fail']].fillna(0).astype(float)
        erab_normal_rel = df[field_map['erab_normal_rel']].fillna(0).astype(float)
        erab_rel = df[field_map['erab_rel']].fillna(0).astype(float)
        context_left = df[field_map['context_left']].fillna(0).astype(float)
        erab_succ = df[field_map['erab_succ']].fillna(0).astype(float)
        ho_inc = df[field_map['ho_inc']].fillna(0).astype(float)

        numerator = ho_fail - erab_normal_rel + erab_rel
        denominator = context_left + erab_succ + ho_inc
        df['4G_E-RAB掉线率(%)'] = np.where(denominator > 0, numerator / denominator * 100, np.nan)
        df['4G_E-RAB掉线率(%)'] = df['4G_E-RAB掉线率(%)'].round(4)
        valid_count = df['4G_E-RAB掉线率(%)'].notna().sum()
        log_func(f"[4G全程完好率] 4G E-RAB掉线率计算完成, 有效数据: {valid_count}", "SUCCESS")
    else:
        missing = [k for k in ['ho_fail', 'erab_normal_rel', 'erab_rel', 'context_left', 'erab_succ', 'ho_inc'] if k not in field_map]
        log_func(f"[4G全程完好率] 缺少字段无法计算4G E-RAB掉线率: {missing}", "WARNING")

    # ========== 4. 计算4G全程完好率(%) ==========
    if all(c in df.columns for c in ['4G无线接通率(%)', '4G切换成功率(%)', '4G_E-RAB掉线率(%)']):
        df['4G全程完好率(%)'] = (
            df['4G无线接通率(%)'] *
            df['4G切换成功率(%)'] *
            (100 - df['4G_E-RAB掉线率(%)'])
        ).round(4)
        valid_count = df['4G全程完好率(%)'].notna().sum()
        log_func(f"[4G全程完好率] 4G全程完好率计算完成, 有效数据: {valid_count}", "SUCCESS")
    else:
        log_func(f"[4G全程完好率] 无法计算4G全程完好率(缺少前置指标)", "WARNING")

    # ========== 5. 判断4G是否差小区 ==========
    if '4G全程完好率(%)' in df.columns:
        df['4G是否差小区'] = np.where(df['4G全程完好率(%)'] < 85, '是', '否')
        bad_count = (df['4G是否差小区'] == '是').sum()
        log_func(f"[4G全程完好率] 4G是否差小区计算完成, 差小区数量: {bad_count}", "SUCCESS")

    return df


def add_5g_wanchenglv_calc_columns(df, log_func=None):
    """添加5G全程完好率计算列。

    SA 接通率由 RRC、Flow 和 NG 信令三段成功率相乘；掉线率和切换
    成功率分别使用对应的上下文/切换计数合计。所有比率统一存成百分数，
    ``< 85`` 是85%的业务阈值。任一必要分母没有有效请求时写 NaN，
    不把缺失数据当作成功；日志会指出缺失标准 key，调用方仍可继续处理
    其他可计算列。

    Args:
        df: 5G全程完好率报表的DataFrame
        log_func: 可选的日志回调函数，签名 log_func(message, level)

    Returns:
        DataFrame: 原对象上添加计算列后的DataFrame
    """
    if log_func is None:
        log_func = lambda msg, level='INFO': None

    field_map = _build_field_map(df, _5G_FIELD_MAP)
    log_func(f"[5G全程完好率] 字段映射: {list(field_map.keys())}", "INFO")

    # SA 接通率的三个分段比例都以0到1参与相乘，最后一次性乘100；
    # 这样不会在中间步骤混用百分数和小数。任一分母为0时整行记为 NaN。
    rrc_ok = all(k in field_map for k in ['rrc_succ', 'rrc_att'])
    flow_ok = all(k in field_map for k in ['flow_succ', 'flow_att'])
    ngsig_ok = all(k in field_map for k in ['ngsig_succ', 'ngsig_att'])

    if rrc_ok and flow_ok and ngsig_ok:
        rrc_succ = df[field_map['rrc_succ']].fillna(0).astype(float)
        rrc_att = df[field_map['rrc_att']].fillna(0).astype(float)
        flow_succ = df[field_map['flow_succ']].fillna(0).astype(float)
        flow_att = df[field_map['flow_att']].fillna(0).astype(float)
        ngsig_succ = df[field_map['ngsig_succ']].fillna(0).astype(float)
        ngsig_att = df[field_map['ngsig_att']].fillna(0).astype(float)

        rrc_rate = np.where(rrc_att > 0, rrc_succ / rrc_att, 0)
        flow_rate = np.where(flow_att > 0, flow_succ / flow_att, 0)
        ngsig_rate = np.where(ngsig_att > 0, ngsig_succ / ngsig_att, 0)

        df['SA无线接通率(%)'] = np.where(
            (rrc_att > 0) & (flow_att > 0) & (ngsig_att > 0),
            rrc_rate * flow_rate * ngsig_rate * 100,
            np.nan
        )
        df['SA无线接通率(%)'] = df['SA无线接通率(%)'].round(4)
        valid_count = df['SA无线接通率(%)'].notna().sum()
        log_func(f"[5G全程完好率] SA无线接通率计算完成, 有效数据: {valid_count}", "SUCCESS")
    else:
        missing = []
        if not rrc_ok:
            missing.extend([k for k in ['rrc_succ', 'rrc_att'] if k not in field_map])
        if not flow_ok:
            missing.extend([k for k in ['flow_succ', 'flow_att'] if k not in field_map])
        if not ngsig_ok:
            missing.extend([k for k in ['ngsig_succ', 'ngsig_att'] if k not in field_map])
        log_func(f"[5G全程完好率] 缺少字段无法计算SA无线接通率: {missing}", "WARNING")

    # ========== 2. 计算SA无线掉线率% ==========
    drop_ok = all(k in field_map for k in ['context_rel', 'context_rel_normal', 'context_init_succ',
                                              'context_left', 'ho_inc_succ', 'rrc_reestab_succ'])
    if drop_ok:
        context_rel = df[field_map['context_rel']].fillna(0).astype(float)
        context_rel_normal = df[field_map['context_rel_normal']].fillna(0).astype(float)
        context_init_succ = df[field_map['context_init_succ']].fillna(0).astype(float)
        context_left = df[field_map['context_left']].fillna(0).astype(float)
        ho_inc_succ = df[field_map['ho_inc_succ']].fillna(0).astype(float)
        rrc_reestab_succ = df[field_map['rrc_reestab_succ']].fillna(0).astype(float)

        numerator = context_rel - context_rel_normal
        denominator = context_init_succ + context_left + ho_inc_succ + rrc_reestab_succ

        df['SA无线掉线率(%)'] = np.where(denominator > 0, numerator / denominator * 100, np.nan)
        df['SA无线掉线率(%)'] = df['SA无线掉线率(%)'].round(4)
        valid_count = df['SA无线掉线率(%)'].notna().sum()
        log_func(f"[5G全程完好率] SA无线掉线率计算完成, 有效数据: {valid_count}", "SUCCESS")
    else:
        missing = [k for k in ['context_rel', 'context_rel_normal', 'context_init_succ',
                                'context_left', 'ho_inc_succ', 'rrc_reestab_succ'] if k not in field_map]
        log_func(f"[5G全程完好率] 缺少字段无法计算SA无线掉线率: {missing}", "WARNING")

    # ========== 3. 计算SA切换成功率% ==========
    ho_succ_ok = all(k in field_map for k in ['ho_ng_succ', 'ho_xn_succ', 'ho_cu_du_succ', 'ho_cu_intra_succ'])
    ho_att_ok = all(k in field_map for k in ['ho_ng_att', 'ho_xn_att', 'ho_cu_du_att', 'ho_cu_intra_att'])

    if ho_succ_ok and ho_att_ok:
        ho_ng_succ = df[field_map['ho_ng_succ']].fillna(0).astype(float)
        ho_xn_succ = df[field_map['ho_xn_succ']].fillna(0).astype(float)
        ho_cu_du_succ = df[field_map['ho_cu_du_succ']].fillna(0).astype(float)
        ho_cu_intra_succ = df[field_map['ho_cu_intra_succ']].fillna(0).astype(float)
        ho_ng_att = df[field_map['ho_ng_att']].fillna(0).astype(float)
        ho_xn_att = df[field_map['ho_xn_att']].fillna(0).astype(float)
        ho_cu_du_att = df[field_map['ho_cu_du_att']].fillna(0).astype(float)
        ho_cu_intra_att = df[field_map['ho_cu_intra_att']].fillna(0).astype(float)

        succ_total = ho_ng_succ + ho_xn_succ + ho_cu_du_succ + ho_cu_intra_succ
        att_total = ho_ng_att + ho_xn_att + ho_cu_du_att + ho_cu_intra_att

        df['SA切换成功率(%)'] = np.where(att_total > 0, succ_total / att_total * 100, np.nan)
        df['SA切换成功率(%)'] = df['SA切换成功率(%)'].round(4)
        valid_count = df['SA切换成功率(%)'].notna().sum()
        log_func(f"[5G全程完好率] SA切换成功率计算完成, 有效数据: {valid_count}", "SUCCESS")
    else:
        missing = []
        if not ho_succ_ok:
            missing.extend([k for k in ['ho_ng_succ', 'ho_xn_succ', 'ho_cu_du_succ', 'ho_cu_intra_succ'] if k not in field_map])
        if not ho_att_ok:
            missing.extend([k for k in ['ho_ng_att', 'ho_xn_att', 'ho_cu_du_att', 'ho_cu_intra_att'] if k not in field_map])
        log_func(f"[5G全程完好率] 缺少字段无法计算SA切换成功率: {missing}", "WARNING")

    # ========== 4. 计算5G全程完好率 ==========
    if all(c in df.columns for c in ['SA无线接通率(%)', 'SA切换成功率(%)', 'SA无线掉线率(%)']):
        df['5G全程完好率(%)'] = (
            df['SA无线接通率(%)'] *
            df['SA切换成功率(%)'] *
            (100 - df['SA无线掉线率(%)'])
        ).round(4)
        valid_count = df['5G全程完好率(%)'].notna().sum()
        log_func(f"[5G全程完好率] 5G全程完好率计算完成, 有效数据: {valid_count}", "SUCCESS")
    else:
        log_func(f"[5G全程完好率] 无法计算5G全程完好率(缺少前置指标)", "WARNING")

    # ========== 5. 判断5G是否差小区 ==========
    if '5G全程完好率(%)' in df.columns:
        df['5G是否差小区'] = np.where(df['5G全程完好率(%)'] < 85, '是', '否')
        bad_count = (df['5G是否差小区'] == '是').sum()
        log_func(f"[5G全程完好率] 5G是否差小区计算完成, 差小区数量: {bad_count}", "SUCCESS")

    return df