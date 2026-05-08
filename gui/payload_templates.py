# -*- coding: utf-8 -*-
"""
硬编码Payload模板模块
基于旧版脚本nqi_tools旧版.py中的payload函数，完全硬编码所有参数
"""

def _build_columns_param(field_list):
    """构建DataTables格式的columns参数"""
    columns = []
    for field in field_list:
        columns.append({
            'data': field,
            'name': '',
            'searchable': True,
            'orderable': True,
            'search': {'value': '', 'regex': False}
        })
    return columns


def _build_result_fields(fields_config, fieldtype, table_name, fixed_datatype_fields=None):
    """构建result字段列表
    
    Args:
        fields_config: 字段配置列表，每个元素是(feild, feildName)元组或dict
        fieldtype: 字段类型
        table_name: 表名
        fixed_datatype_fields: 使用固定datatype='1'的字段集合
    """
    if fixed_datatype_fields is None:
        fixed_datatype_fields = set()
    
    result_list = []
    for config in fields_config:
        if isinstance(config, dict):
            feild = config.get('feild', config.get('columnname', ''))
            feildName = config.get('feildName', feild)
        else:
            feild = config[0]
            feildName = config[1] if len(config) > 1 else feild
        
        if not feild:
            continue
            
        # 时间维度字段使用columntype=2
        columntype = 2 if feild == 'starttime' else 1
        # 固定类型字段使用datatype='1'
        datatype = '1' if feild in fixed_datatype_fields else 'character varying'
        
        result_list.append({
            'feildtype': fieldtype,
            'table': table_name,
            'tableName': fieldtype,
            'datatype': datatype,
            'columntype': columntype,
            'feildName': feildName,
            'feild': feild,
            'poly': '无',
            'anyWay': '无',
            'chart': '无',
            'chartpoly': '无'
        })
    return result_list


# ==================== 5G干扰小区 ====================
def get_5g_interference_payload(start_date=None, end_date=None, city=None):
    """5G干扰小区报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '数据时间'), ('endtime', '结束时间'), ('cgi', 'CGI'),
        ('cell_name', '小区名'), ('freq', '频段'), ('micro_grid', '微网格标识'),
        ('averagevalue', '全频段均值'), ('averagevalued1', 'D1均值'),
        ('averagevalued2', 'D2均值'), ('is_interfere_5g', '是否干扰小区')
    ]
    fixed_fields = {'starttime', 'endtime', 'cgi', 'cell_name', 'city'}
    result_list = _build_result_fields(fields, '5G干扰报表（忙时）', 'appdbv3.a_interfere_nr_cell_zb2_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2025-01-13'
    if end_date is None:
        end_date = '2025-01-18'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '天',
        'enodebField': 'gnodeb_id', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'cell', 'cityField': 'city',
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== 4G干扰小区 ====================
def get_4g_interference_payload(start_date=None, end_date=None, city=None):
    """4G干扰小区报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '数据时间'), ('endtime', '结束时间'), ('cgi', 'CGI'),
        ('cell_name', '小区名'), ('freq', '频段'), ('micro_grid', '微网格标识'),
        ('bandwidth', '系统带宽'), ('averagevalue', '平均干扰电平'), ('is_interfere', '是否干扰小区')
    ]
    fixed_fields = {'starttime', 'endtime', 'cgi', 'cell_name', 'city'}
    result_list = _build_result_fields(fields, '4G干扰报表（忙时）', 'appdbv3.a_interfere_lte_cell_zb2_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2025-01-13'
    if end_date is None:
        end_date = '2025-01-18'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '天',
        'enodebField': 'enodeb_id', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'cell', 'cityField': 'city',
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== 5G小区容量 ====================
def get_5g_capacity_payload(start_date=None, end_date=None, city=None):
    """5G小区容量报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    import logging
    logger = logging.getLogger(__name__)
    
    fields = [
        ('starttime', '记录开始时间'), ('endtime', '记录结束时间'), ('city', '地市'),
        ('grid', '责任网格'), ('nrcell_name', '小区名称'), ('ncgi', 'NCGI'),
        ('busy_hour', '忙时'), ('state', '网元状态'), ('vendor', '厂家'),
        ('frequency_band_detail', '详细使用频段'), ('freq', '使用频段'),
        ('cover_type', '覆盖类型'), ('cover_scene', '覆盖场景'), ('is_remote', '是否拉远'),
        ('station_name', '所属基站'), ('longitude', '经度'), ('latitude', '纬度'),
        ('bh_rru_pdcchcceutil', '忙时PDCCH信道CCE占用个数'), ('sectors_name', '共站同覆盖小区名称'),
        ('bh_rru_pdcchcceavail', '忙时PDCCH信道CCE可用个数'),
        ('bh_pdcchcceoccupancyrate', '忙时PDCCH信道CCE占用率(%)'),
        ('bh_rru_puschprbassn', '忙时上行PUSCH PRB占用个数'),
        ('bh_rru_puschprbtot', '忙时上行PUSCH PRB可用个数'),
        ('bh_prbassnrateul', '忙时上行PRB平均利用率(%)'),
        ('bh_rru_pdschprbassn', '忙时下行PDSCH PRB占用个数'),
        ('bh_rru_pdschprbtot', '忙时下行PDSCH PRB可用个数'),
        ('bh_prbassnratedl', '忙时下行PRB平均利用率(%)'),
        ('bh_rlc_upoctul', '忙时RLC层上行业务字节数(G)'),
        ('bh_rlc_upoctdl', '忙时RLC层下行业务字节数(G)'),
        ('bh_mac_cpoctul', '忙时MAC层上行业务流量(G)'),
        ('bh_mac_cpoctdl', '忙时MAC层下行业务流量(G)'),
        ('bh_pdcp_upoctul', '忙时PDCP上行业务字节数(G)'),
        ('bh_pdcp_upoctdl', '忙时PDCP下行业务字节数(G)'),
        ('rlc_upoctul', '日RLC层上行业务字节数(G)'),
        ('rlc_upoctdl', '日RLC层下行业务字节数(G)'),
        ('rlc_upoctudl', '日RLC层上下行总流量(G)'),
        ('mac_cpoctudl', '日MAC层上下行总流量(G)'),
        ('pdcp_upoctudl', '日PDCP层上下行总流量(G)'),
        ('bh_rrc_connmean', 'RRC连接平均数-忙时'), ('is_highload', '是否高负荷待扩容小区'),
        ('bh_rrc_connmax', 'RRC连接最大数-忙时'),
        ('bh_flow_nbrattestab', 'Flow建立请求数-忙时'),
        ('bh_flow_nbrsuccestab', 'Flow建立成功数-忙时'),
        ('bh_kpi_flowsuccconnrate', 'QoS Flow建立成功率-忙时'),
        ('grid_road', '路测网格'), ('second_scene_detail', '二级场景细化'),
        ('bh_puschprbtot_reuse', '忙时上行PRB可用空分层数'),
        ('bh_puschprbassn_reuse', '忙时上行PRB占用空分层数'),
        ('bh_avgdtchmimolayerul', '忙时上行业务信道平均空分层数'),
        ('bh_pdschprbtot_reuse', '忙时下行PRB可用空分层数'),
        ('bh_pdschprbassn_reuse', '忙时下行PRB占用空分层数'),
        ('bh_avgdtchmimolayerdl', '忙时下行业务信道平均空分层数'),
        ('maxdtchmimolayerul', '上行业务信道最大空分层数'),
        ('maxdtchmimolayerdl', '下行业务信道最大空分层数'),
        ('bh_dtchmimoprbassnrateul', '忙时上行业务信道空分PRB占用率'),
        ('bh_dtchmimoprbassnratedl', '忙时下行业务信道空分PRB占用率'),
        ('bh_cellprbrate', '忙时小区PRB利用率'),
        ('bh_flow_nbrhoinc', '忙时切换进入Flow数'),
        ('bh_upoctudl_perflow', '忙时每Flow流量'),
        ('band_width', '小区带宽'), ('ssbfrequenc', '中心载频号'),
        ('txrxmode', '射频通道数'), ('area_type', '区域类型'),
        ('micro_grid', '微网格标识'), ('cover_scene1', '覆盖场景1'),
        ('cover_scene2', '覆盖场景2'), ('cover_scene3', '覆盖场景3'),
        ('cover_scene4', '覆盖场景4'),
    ]
    fixed_fields = {'starttime', 'endtime', 'city', 'grid', 'nrcell_name', 'ncgi', 'busy_hour', 'state', 'vendor', 'sectors_name', 'station_name'}
    result_list = _build_result_fields(fields, '5G小区容量报表 - 天粒度', 'appdbv3.a_adhoc_capacity_nr_nrcell_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
        logger.warning(f"5G小区容量报表: start_date为None，使用默认值 {start_date}")
    if end_date is None:
        end_date = '2026-04-19'
        logger.warning(f"5G小区容量报表: end_date为None，使用默认值 {end_date}")
    if city is None:
        city = '阳江'
        logger.warning(f"5G小区容量报表: city为None，使用默认值 {city}")
    
    logger.info(f"[5G小区容量报表] 生成payload: start_date={start_date}, end_date={end_date}, city={city}")
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '天',
        'enodebField': 'enodeb_id', 'cgiField': 'ncgi', 'timeField': 'starttime',
        'cellField': 'nrcell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 1
    }


# ==================== 重要场景 ====================
def get_important_scene_payload(start_date=None, end_date=None, city=None):
    """重要场景-天报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '记录开始时间'), ('endtime', '记录结束时间'), ('city', '所属地市'),
        ('cgi', 'CGI'), ('busy_hour', '自忙时'), ('freq_name', '详细频段'),
        ('cell_name', '小区名称'), ('state', '网元状态'), ('scene', '场景'),
        ('scene_name', '场景具体名称'), ('upoctudl', '日4G流量（GB）'),
        ('ul_prbuse_rate_max', '日峰值上行PRB平均利用率'),
        ('dl_prbuse_rate_max', '日峰值下行PRB平均利用率'),
        ('pdcchcceutilratio_max', '日峰值PDCCH信道CCE占用率'),
        ('bh_effectiveconnmax', '自忙时有效RRC连接最大数'),
        ('bh_connmax', '自忙时RRC连接最大数'),
        ('bh_effectiveconnmean', '自忙时有效RRC连接平均数'),
        ('bh_upoctul', '自忙时空口上行业务字节数'),
        ('bh_upoctdl', '自忙时空口下行业务字节数'),
        ('bh_ul_prbuse_rate', '自忙时上行PRB平均利用率'),
        ('bh_dl_prbuse_rate', '自忙时下行PRB平均利用率'),
        ('bh_pdcchcceutilratio', '自忙时PDCCH信道CCE占用率'),
        ('radio_succ_rate', '无线接通率'),
        ('radio_drop_rate_cell', '无线掉线率(小区级)'),
        ('call_connect_rate', '呼叫接通率(MTC+MOC)'),
        ('volte_drop_rate', 'VOLTE掉话率'),
        ('esrvcc_ho_succ_rate', 'ESRVCC切换成功率'),
        ('volte_voice_traffic', 'VOLTE语音话务量'),
        ('bh_avg_erab', '小区自忙时平均E-RAB流量'),
        ('bh_peak_use_rate', '自忙时峰值利用率'),
        ('bh_nbrsuccestab', '自忙时E-RAB建立成功数'),
        ('is_highflow', '是否高流量预警小区（集团高负荷预警）'),
        ('is_highload', '是否高负荷待扩容小区'),
        ('bh_pdcchcceutil', '自忙时PDCCH信道CCE占用个数'),
        ('bh_pdcchcceavail', '自忙时PDCCH信道CCE可用个数'),
        ('bh_pdschprbassn', '自忙时下行PDSCH_PRB占用数'),
        ('bh_pdschprbtot', '自忙时下行PDSCH_PRB可用数'),
        ('bh_puschprbassn', '自忙时上行PUSCH_PRB占用数'),
        ('bh_puschprbtot', '自忙时上行PUSCH_PRB可用数'),
        ('pdcchcceutil_max', '日峰值PDCCH信道CCE占用个数'),
        ('pdcchcceavail_max', '日峰值PDCCH信道CCE可用个数'),
        ('pdschprbassn_max', '日峰值下行PDSCH_PRB占用数'),
        ('pdschprbtot_max', '日峰值下行PDSCH_PRB可用数'),
        ('puschprbassn_max', '日峰值上行PUSCH_PRB占用数'),
        ('puschprbtot_max', '日峰值上行PUSCH_PRB可用数'),
        ('vendor', '设备厂家'), ('freq', '使用频段'),
        ('flow_coefficient', '流量系数'), ('bandwidth', '小区带宽'),
        ('is_remote', '是否拉远'), ('station_name', '所属站点名称'),
        ('lte_soc_tcpsetup_c_007', 'TCP二三次握手时延（ms)'),
        ('lte_soc_http_cell_c_055', '大包速率(>500KB)'),
        ('lte_soc_tcpsetup_c_003', 'TCP二三次握手成功率'),
        ('is_highflow_perceive', '是否高流量感知问题小区'),
        ('equivalent_20m_carrier', '等效TDD_20M载波数'),
        ('lte_soc_tcpsetup_021', '三次握手成功次数(HTTP)'),
        ('lte_soc_tcpsetup_023', '三次握手成功次数(S1U)'),
        ('lte_soc_tcpsetup_027', 'TCP一、二次握手成功次数(HTTP)'),
        ('lte_soc_tcpsetup_029', 'TCP一、二次握手成功次数(S1U)'),
        ('lte_soc_tcpsetup_030', 'TCP建立总延时（HTTP)'),
        ('lte_soc_tcpsetup_032', 'TCP建立总延时(S1U)'),
        ('lte_soc_tcpsetup_033', 'TCP一、二次握手总延时(HTTP)'),
        ('lte_soc_tcpsetup_035', 'TCP一、二次握手总延时(S1U)'),
        ('lte_soc_http_cell_078', '大包流量(>500KB)'),
        ('lte_soc_http_cell_079', '大包总时延(>500KB)'),
        ('sectors_no', '所属共站同覆盖区域编号'),
        ('sectors_name', '所属共站同覆盖区域名'),
        ('aim_user', '小区自忙时5M感知需求能力-用户数'),
        ('aim_flow', '小区自忙时5M感知需求能力-流量（GB）'),
        ('aim_utilization', '小区自忙时5M感知需求能力-利用率（%）'),
        ('cover', '覆盖类型'), ('coverlayer', '覆盖层标识'),
        ('capacitylayer', '容量层标识'), ('sectors_width', '扇区宽度'),
        ('cell_scene_name', '小区所属区域'), ('longitude', '经度'),
        ('latitude', '维度'), ('channel_numbers', '天线通道数'),
        ('is_dilatation', '是否扩容小区+'),
        ('is_carry', '是否纳入载波调度'),
        ('network_structure', '网络结构属性'),
        ('cell_scene_type', '小区所属区域类型'),
        ('is_city_tail', '是否本地市尾部小区'),
        ('is_province_tail', '是否全省尾部小区'),
    ]
    fixed_fields = {'starttime', 'endtime', 'city', 'cgi', 'busy_hour', 'freq_name', 'cell_name', 'state', 'scene', 'scene_name', 'vendor', 'sectors_name', 'station_name', 'sectors_no'}
    result_list = _build_result_fields(fields, '重要场景-小区天', 'appdbv3.a_overview_ispm_lte_cell_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '天',
        'enodebField': 'enodeb_id', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'cell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== VoLTE告警 ====================
def get_volte_warning_payload(start_date=None, end_date=None, city=None):
    """VoLTE小区监控预警报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '时间'), ('city', '地市'), ('cgi', '小区'),
        ('grid', '责任网格'), ('area', '区县'), ('nrcell_name', '小区名称'),
        ('cs_reg1_suss_rate', '初始注册成功率（控制面）'),
        ('cs_reg_suss_rate', 'VoLTE注册成功率（控制面）'),
        ('cs_reg_sbc_suss_rate', 'SBC注册成功率（控制面）'),
        ('cs_moc_sbc_suss_rate', '始呼接通率（控制面）'),
        ('cs_moc_sbc_180_suss_rate', '始呼接通率(180)（控制面）'),
        ('cs_mtc_sbc_suss_rate', '终呼接通率（控制面）'),
        ('cs_mtc_sbc_180_suss_rate', '终呼接通率(180)（控制面）'),
        ('cs_sbc_suss_rate', '呼叫接通率(MOC+MTC)（控制面）'),
        ('cs_sbc_180_suss_rate', '呼叫接通率(180_MOC+MTC)（控制面）'),
        ('cs_moc_sbc_net_suss_rate', '始呼网络接通率（控制面）'),
        ('cs_sbc_net_suss_rate', '网络接通率(MOC+MTC)（控制面）'),
        ('cs_sbc_drops_rate', 'VOLTE+掉话率（控制面）'),
        ('cs_xsrvcc_ho_suss_rate', 'xSRVCC切换成功率（控制面）'),
        ('cs_ho_len_avg', 'SRVCC平均切换时长(ms)（控制面）'),
        ('cs_ho_rtp_delay_avg', 'SRVCC平均媒体切换时长(ms)（控制面）'),
        ('cs_alert_delay_vf_avg', '呼叫建立平均时长(V-固网IMS)（控制面）'),
        ('cs_alert_delay_vv_avg', '呼叫建立平均时长(V2V)（控制面）'),
        ('cs_alert_delay_vall_rate', '呼叫建立平均时长(V2ALL)（控制面）'),
        ('cs_mt_alert_delay_avg', '终呼平均接续时长(ms)（控制面）'),
        ('mconv_rtp_ul_mos_avg', 'RTP上行平均MOS（会话）'),
        ('mconv_rtp_dl_mos_avg', 'RTP下行平均MOS（会话）'),
        ('mconv_mos_300_nok_rate', 'RTP上行MOS 3.0 差占比率（会话）'),
        ('mconv_rtcp_ul_mos_avg', 'RTCP上行平均MOS（会话）'),
        ('mconv_rtcp_dl_mos0', 'RTCP下行平均MOS（会话）'),
        ('mconv_rtp_ul_pkts_lost_rate', 'RTP上行丢包率（会话）'),
        ('mconv_rtp_dl_pkts_lost_rate', 'RTP下行丢包率（会话）'),
        ('mconv_rtcp_ul_pkts_lost_rate', 'RTCP上行丢包率（会话）'),
        ('mconv_rtcp_dl_pkts_lost_rate', 'RTCP下行丢包率（会话）'),
        ('mconv_single_voice_call_rate', 'VoLTE语音单通率（会话）'),
        ('mconv_dx_call_rate', 'VoLTE语音断续/掉话率（会话）'),
        ('mconv_rtp_ul_delay_avg', 'RTP上行平均时延(us)（会话）'),
        ('mconv_rtp_dl_delay_avg', 'RTP下行平均时延(us)（会话）'),
        ('mconv_rtcp_ul_delay_avg', 'RTCP上行平均时延(us)（会话）'),
        ('mconv_rtcp_dl_delay_avg', 'RTCP下行平均时延(us)（会话）'),
        ('mconv_dl_mos_300_nok_rate', 'RTP下行MOS 3.0 差占比率（会话）'),
        ('msli_ul_tunzi_len_rate', 'VoLTE语音上行质差率（片段）'),
        ('msli_ul_duanxu_len_rate', 'VoLTE语音上行断续率（片段）'),
        ('msli_ul_dantong_len_rate', 'VoLTE语音上行单通率（片段）'),
        ('msli_ul_mos_poor_len_rate', 'VoLTE上行MOS质差率（片段）'),
        ('msli_dl_tunzi_len_rate', 'VoLTE语音下行质差率（片段）'),
        ('msli_dl_duanxu_len_rate', 'VoLTE语音下行断续率（片段）'),
        ('msli_dl_dantong_len_rate', 'VoLTE语音下行单通率（片段）'),
        ('msli_dl_mos_poor_len_rate', 'VoLTE下行MOS质差率（片段）'),
        ('msli_ul_mos_v2v_avg', 'VoLTE上行平均MOS（对端VoLTE）（片段）'),
        ('msli_ul_mos_v2f_avg', 'VoLTE上行平均MOS（对端EPS FB）（片段）'),
        ('msli_ul_mos_v2n_avg', 'VoLTE上行平均MOS（对端VoNR）（片段）'),
        ('msli_ul_mos_v2cs_avg', 'VoLTE上行平均MOS（对端CS）（片段）'),
        ('msli_ul_mos_v2all_avg', 'VoLTE上行平均MOS(对端ALL)（片段）'),
        ('msli_dl_mos_v2v_avg', 'VoLTE下行平均MOS（对端VoLTE）（片段）'),
        ('msli_dl_mos_v2f_avg', 'VoLTE下行平均MOS（对端EPS FB）（片段）'),
        ('msli_dl_mos_v2n_avg', 'VoLTE下行平均MOS（对端VoNR）（片段）'),
        ('msli_dl_mos_v2cs_avg', 'VoLTE下行平均MOS（对端CS）（片段）'),
        ('msli_dl_mos_v2all_avg', 'VoLTE下行平均MOS(对端ALL)（片段）'),
        ('msli_ul_rtp_lost_rate', '上行RTP丢包率（片段）'),
        ('msli_dl_rtp_lost_rate', '下行RTP丢包率（片段）'),
        ('volte_sbc_net_suss', 'VoLTE_网络接通次数(MOC+MTC)'),
        ('volte_sbc_net_sums', 'VoLTE_网络试呼次数(MOC+MTC)'),
        ('volte_sbc_drops', 'VoLTE_掉话次数'),
        ('volte_sbc_ans', 'VoLTE_应答复次数(掉话率)'),
        ('volte_local_radio_single_voice_call', 'VoLTE_语音本端无线单通通话次数'),
        ('volte_local_radio_dx_call', 'VoLTE_语音本端无线断续通话次数'),
        ('volte_ans_voice_call', 'VoLTE_语音通话总次数'),
        ('volte_local_radio_dtdx_rate', 'VoLTE_单通断续次数占比'),
        ('volte_ul_tunzi_len', 'VoLTE_语音上行质差时长(s)'),
        ('volte_ul_dantong_len', 'VoLTE_语音上行单通时长(s)'),
        ('volte_ul_duanxu_len', 'VoLTE_语音上行断续时长(s)'),
        ('volte_ul_voice_sum_len', 'VoLTE_语音上行总时长(s)'),
        ('volte_dl_tunzi_len', 'VoLTE_语音下行质差时长(s)'),
        ('volte_dl_dantong_len', 'VoLTE_语音下行单通时长(s)'),
        ('volte_dl_duanxu_len', 'VoLTE_语音下行断续时长(s)'),
        ('volte_dl_voice_sum_len', 'VoLTE_语音下行总时长(s)'),
        ('micro_grid', '微网格标识'), ('cover_scene1', '覆盖场景1'),
        ('cover_scene2', '覆盖场景2'), ('cover_scene3', '覆盖场景3'),
        ('cover_scene4', '覆盖场景4'), ('grid_road', '网格道路'),
        ('marketduty', '市场职责'), ('vendor', '厂商'),
        ('state', '网元状态'), ('coverage_type', '覆盖类型'),
        ('network_type', '网络制式'), ('freq', '频段_无线'),
    ]
    fixed_fields = {'starttime', 'city', 'cgi', 'grid', 'area', 'nrcell_name', 'micro_grid', 'cover_scene1', 'cover_scene2', 'cover_scene3', 'cover_scene4', 'grid_road', 'marketduty', 'vendor', 'state', 'coverage_type', 'network_type', 'freq'}
    result_list = _build_result_fields(fields, 'VoLTE小区监控预警数据表-天', 'csem.f_nk_volte_keykpi_cell_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '天',
        'enodebField': 'enodeb_id', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'cell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== EPSFB告警 ====================
def get_epsfb_warning_payload(start_date=None, end_date=None, city=None):
    """EPSFB小区监控预警报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '时间'), ('city', '地市'), ('cgi', '小区'),
        ('grid', '责任网格'), ('area', '区县'), ('nrcell_name', '小区名称'),
        # EPSFB特有字段较多，这里使用简化版
        ('sacs_start_moc_net_succ_rate', 'EPSFB始呼网络接通率'),
        ('sacs_start_mtc_net_succ_rate', 'EPSFB终呼网络接通率'),
        ('sacs_start_call_net_succ_rate', 'EPSFB呼叫网络接通率'),
        ('sacs_start_call_drop_rate', 'EPSFB掉话率'),
        ('sacs_start_fb_succ_rate', 'EPSFB切换成功率'),
        ('epsfb_sbc_net_suss', 'EPSFB网络接通次数'),
        ('epsfb_sbc_net_sums', 'EPSFB网络试呼次数'),
        ('epsfb_sbc_drops', 'EPSFB掉话次数'),
        ('epsfb_sbc_ans', 'EPSFB应答复次数'),
        ('epsfb_local_radio_single_voice_call', 'EPSFB语音本端无线单通通话次数'),
        ('epsfb_local_radio_dx_call', 'EPSFB语音本端无线断续通话次数'),
        ('epsfb_ans_voice_call', 'EPSFB语音通话总次数'),
        ('epsfb_local_radio_dtdx_rate', 'EPSFB单通断续次数占比'),
        ('epsfb_ul_tunzi_len', 'EPSFB语音上行质差时长(s)'),
        ('epsfb_ul_dantong_len', 'EPSFB语音上行单通时长(s)'),
        ('epsfb_ul_duanxu_len', 'EPSFB语音上行断续时长(s)'),
        ('epsfb_ul_voice_sum_len', 'EPSFB语音上行总时长(s)'),
        ('epsfb_dl_tunzi_len', 'EPSFB语音下行质差时长(s)'),
        ('epsfb_dl_dantong_len', 'EPSFB语音下行单通时长(s)'),
        ('epsfb_dl_duanxu_len', 'EPSFB语音下行断续时长(s)'),
        ('epsfb_dl_voice_sum_len', 'EPSFB语音下行总时长(s)'),
        ('micro_grid', '微网格标识'), ('cover_scene1', '覆盖场景1'),
        ('cover_scene2', '覆盖场景2'), ('cover_scene3', '覆盖场景3'),
        ('cover_scene4', '覆盖场景4'), ('grid_road', '网格道路'),
        ('marketduty', '市场职责'), ('vendor', '厂商'),
        ('state', '网元状态'), ('coverage_type', '覆盖类型'),
        ('network_type', '网络制式'), ('freq', '频段_无线'),
    ]
    fixed_fields = {'starttime', 'city', 'cgi', 'grid', 'area', 'nrcell_name', 'micro_grid', 'cover_scene1', 'cover_scene2', 'cover_scene3', 'cover_scene4', 'grid_road', 'marketduty', 'vendor', 'state', 'coverage_type', 'network_type', 'freq'}
    result_list = _build_result_fields(fields, 'EPSFB小区监控预警数据表-天', 'csem.f_nk_epsfb_keykpi_cell_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '天',
        'enodebField': '---', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'cell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== VONR告警 ====================
def get_vonr_warning_payload(start_date=None, end_date=None, city=None):
    """5G语音小区（VONR）监控预警报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '时间'), ('city', '地市'), ('cgi', '小区'),
        ('grid', '责任网格'), ('area', '区县'), ('nrcell_name', '小区名称'),
        ('vonr_ul_tunzi_len', 'VoNR语音上行吞字时长(s)'),
        ('vonr_ul_dantong_len', 'VoNR语音上行单通时长(s)'),
        ('vonr_ul_duanxu_len', 'VoNR语音上行断续时长(s)'),
        ('vonr_ul_voice_sum_len', 'VoNR语音上行总时长(s)'),
        ('vonr_ans_voice_call', 'VoNR语音通话总次数'),
        ('micro_grid', '微网格标识'), ('cover_scene1', '覆盖场景1'),
        ('cover_scene2', '覆盖场景2'), ('cover_scene3', '覆盖场景3'),
        ('cover_scene4', '覆盖场景4'), ('grid_road', '网格道路'),
        ('marketduty', '市场职责'), ('vendor', '厂商'),
        ('state', '网元状态'), ('coverage_type', '覆盖类型'),
        ('network_type', '网络制式'), ('freq', '频段_无线'),
    ]
    fixed_fields = {'starttime', 'city', 'cgi', 'grid', 'area', 'nrcell_name', 'micro_grid', 'cover_scene1', 'cover_scene2', 'cover_scene3', 'cover_scene4', 'grid_road', 'marketduty', 'vendor', 'state', 'coverage_type', 'network_type', 'freq'}
    result_list = _build_result_fields(fields, '5G语音小区报表', 'csem.f_nk_vonr_keykpi_cell_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '天',
        'enodebField': 'gnodeb_id', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'cell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== 4G全程完好率 ====================
def get_4g_wanchenglv_payload(start_date=None, end_date=None, city=None):
    """4G全程完好率报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '开始时间'), ('cgi', 'CGI'), ('cell_name', '小区名称'),
        ('city', '所属地市'), ('branch', '人力区县分公司'),
        ('network_type', '网络制式'), ('state', '网元状态'), ('cover_type', '覆盖类型'),
        ('succconnestab', 'RRC连接建立成功次数'), ('attconnestab', 'RRC连接建立请求次数'),
        ('nbrsuccestab', 'E-RAB建立成功数'), ('nbrattestab', 'E-RAB建立请求数'),
        ('succexecinc', '切换入成功次数'), ('ho_succ_out', '切换成功次数'),
        ('ho_att__out', '切换请求次数'), ('hofail', '切出失败的E-RAB数'),
        ('nbrreqrelenb_normal', '正常的eNB请求释放的E-RAB数'),
        ('nbrreqrelenb', 'eNB请求释放的E-RAB数'),
        ('nbrleft', '遗留上下文个数'), ('nbrhoinc', '切换入E-RAB数'),
    ]
    fixed_fields = {'starttime', 'cgi', 'cell_name', 'city', 'branch', 'network_type', 'state', 'cover_type'}
    result_list = _build_result_fields(fields, '公共信息（小区级粒度）', 'appdbv3.a_common_pm_lte', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区，网格，地市，分公司',
        'timedimension': '小时,天,周.月,忙时,15分钟',
        'enodebField': 'enodeb_id', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'cell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': '0', 'supportedtimedimension': '1'}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== 5G全程完好率 ====================
def get_5g_wanchenglv_payload(start_date=None, end_date=None, city=None):
    """5G全程完好率报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '数据时间'), ('ncgi', 'NCGI'), ('nrcell_name', '小区名称'),
        ('branch', '人力区县分公司'), ('grid', '责任网格'), ('grid_road', '路测网格'),
        ('city', '所属地市'), ('area', '所属区县'), ('vendor', '设备厂家'),
        ('network_type', '网络制式'), ('cover_type', '覆盖类型'), ('state', '网元状态'),
        ('rrc_succconnestab', 'RRC连接建立成功次数'), ('rrc_attconnestab', 'RRC连接建立请求次数'),
        ('flow_nbrsuccestab', 'Flow建立成功数'), ('flow_nbrattestab', 'Flow建立请求数'),
        ('ngsig_connestabsucc', 'NG接口UE相关逻辑信令连接建立成功次数'),
        ('ngsig_connestabatt', 'NG接口UE相关逻辑信令连接建立请求次数'),
        ('context_attrelgnb', 'gNB请求释放上下文数'),
        ('context_attrelgnb_normal', '正常的gNB请求释放上下文数'),
        ('context_succinitalsetup', '初始上下文建立成功次数'),
        ('context_nbrleft', '遗留上下文个数'),
        ('ho_succexecinc', '切换入成功次数'),
        ('rrc_succconnreestab_nonsrccell', 'RRC连接重建成功次数(非源侧小区)'),
        ('ho_succoutintercung', 'gNB间NG切换出成功次数'),
        ('ho_succoutintercuxn', 'gNB间Xn切换出成功次数'),
        ('ho_succoutintracuinterdu', 'CU内DU间切换出执行成功次数'),
        ('ho_succoutintradu', 'CU内DU内切换出成功次数'),
        ('ho_attoutintercung', 'gNB间NG切换出准备请求次数'),
        ('ho_attoutintercuxn', 'gNB间Xn切换出准备请求次数'),
        ('ho_attoutintracuinterdu', 'CU内DU间切换出执行请求次数'),
        ('ho_attoutcuintradu', 'CU内DU内切换出执行请求次数'),
    ]
    fixed_fields = {'starttime', 'ncgi', 'nrcell_name', 'branch', 'grid', 'grid_road', 'city', 'area', 'vendor', 'network_type', 'cover_type', 'state'}
    result_list = _build_result_fields(fields, 'SA_CU性能', 'appdbv3.a_common_pm_sacu', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区，网格，地市，分公司',
        'timedimension': '小时,天,周,月',
        'enodebField': 'gnodeb_id', 'cgiField': 'ncgi', 'timeField': 'starttime',
        'cellField': 'nrcell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': '0', 'supportedtimedimension': '1'}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== VoLTE小区 ====================
def get_volte_payload(start_date=None, end_date=None, city=None):
    """VoLTE小区报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '时间'), ('city', '地市'), ('cgi', '小区'),
        ('grid', '责任网格'), ('area', '区县'), ('nrcell_name', '小区名称'),
        ('volte_ul_tunzi_len', 'VoLTE语音上行吞字时长(s)'),
        ('volte_ul_dantong_len', 'VoLTE语音上行单通时长(s)'),
        ('volte_ul_duanxu_len', 'VoLTE语音上行断续时长(s)'),
        ('volte_ul_voice_sum_len', 'VoLTE语音上行总时长(s)'),
        ('volte_ans_voice_call', 'VoLTE语音通话总次数'),
        ('volte_dl_tunzi_len', 'VoLTE语音下行吞字时长(s)'),
        ('volte_dl_dantong_len', 'VoLTE语音下行单通时长(s)'),
        ('volte_dl_duanxu_len', 'VoLTE语音下行断续时长(s)'),
        ('volte_dl_voice_sum_len', 'VoLTE语音下行总时长(s)'),
    ]
    fixed_fields = {'starttime', 'city', 'cgi', 'grid', 'area', 'nrcell_name'}
    result_list = _build_result_fields(fields, 'VoLTE小区监控预警数据表-天', 'csem.f_nk_volte_keykpi_cell_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '天',
        'enodebField': 'enodeb_id', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'cell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== EPSFB小区 ====================
def get_epsfb_payload(start_date=None, end_date=None, city=None):
    """EPSFB小区报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '时间'), ('city', '地市'), ('cgi', '小区'),
        ('grid', '责任网格'), ('area', '区县'), ('nrcell_name', '小区名称'),
        ('epsfb_ul_tunzi_len', 'EPSFB语音上行吞字时长(s)'),
        ('epsfb_ul_dantong_len', 'EPSFB语音上行单通时长(s)'),
        ('epsfb_ul_duanxu_len', 'EPSFB语音上行断续时长(s)'),
        ('epsfb_ul_voice_sum_len', 'EPSFB语音上行总时长(s)'),
        ('epsfb_ans_voice_call', 'EPSFB语音通话总次数'),
        ('epsfb_dl_tunzi_len', 'EPSFB语音下行吞字时长(s)'),
        ('epsfb_dl_dantong_len', 'EPSFB语音下行单通时长(s)'),
        ('epsfb_dl_duanxu_len', 'EPSFB语音下行断续时长(s)'),
        ('epsfb_dl_voice_sum_len', 'EPSFB语音下行总时长(s)'),
    ]
    fixed_fields = {'starttime', 'city', 'cgi', 'grid', 'area', 'nrcell_name'}
    result_list = _build_result_fields(fields, 'EPSFB小区监控预警数据表-天', 'csem.f_nk_epsfb_keykpi_cell_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '天',
        'enodebField': '---', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'cell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== 5G语音 ====================
def get_5g_voice_payload(start_date=None, end_date=None, city=None):
    """5G语音小区（VONR）报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '时间'), ('city', '地市'), ('cgi', '小区'),
        ('grid', '责任网格'), ('area', '区县'), ('nrcell_name', '小区名称'),
        ('vonr_ul_tunzi_len', 'VoNR语音上行吞字时长(s)'),
        ('vonr_ul_dantong_len', 'VoNR语音上行单通时长(s)'),
        ('vonr_ul_duanxu_len', 'VoNR语音上行断续时长(s)'),
        ('vonr_ul_voice_sum_len', 'VoNR语音上行总时长(s)'),
        ('vonr_ans_voice_call', 'VoNR语音通话总次数'),
    ]
    fixed_fields = {'starttime', 'city', 'cgi', 'grid', 'area', 'nrcell_name'}
    result_list = _build_result_fields(fields, '5G语音小区报表', 'csem.f_nk_vonr_keykpi_cell_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '天',
        'enodebField': 'gnodeb_id', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'cell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== 5G工参 ====================
def get_5g_gongcan_payload():
    """5G小区工参报表payload"""
    return {
        '__gongcan__': True,
        'table_key': 'appdbv3.a_common_cfg_nr_cellant_d',
        'fieldtype': '5G小区工参',
        'api_type': 'table',
        'geographicdimension': '小区，网格，地市，分公司',
        'timedimension': '天粒度',
        'enodebField': 'gnodeb_id',
        'cgiField': 'ncgi',
        'timeField': 'starttime',
        'cellField': 'nrcell_name',
        'cityField': 'city'
    }


# ==================== 4G工参 ====================
def get_4g_gongcan_payload():
    """4G小区工参报表payload"""
    return {
        '__gongcan__': True,
        'table_key': 'appdbv3.v_a_common_cfg_lte_cellant_d',
        'fieldtype': '4G小区工参',
        'api_type': 'table',
        'geographicdimension': '小区，网格，地市，分公司',
        'timedimension': '天粒度',
        'enodebField': 'enodeb_id',
        'cgiField': 'cgi',
        'timeField': 'starttime',
        'cellField': 'cell_name',
        'cityField': 'city'
    }


# ==================== 5G KPI ====================
def get_5g_kpi_payload(start_date=None, end_date=None, city=None):
    """5G小区KPI报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '数据时间'), ('ncgi', 'NCGI'), ('nrcell_name', '小区名称'),
        ('city', '地市'), ('area', '区县'), ('branch', '分公司'),
        ('grid', '网格'), ('vendor', '设备厂家'), ('state', '网元状态'),
        ('cover_type', '覆盖类型'), ('cover_scene', '覆盖场景'),
        ('rrc_succconnestab', 'RRC连接建立成功次数'),
        ('rrc_attconnestab', 'RRC连接建立请求次数'),
        ('rrc_conn_succ_rate', 'RRC连接建立成功率'),
        ('flow_nbrsuccestab', 'Flow建立成功数'),
        ('flow_nbrattestab', 'Flow建立请求数'),
        ('flow_succ_rate', 'Flow建立成功率'),
        ('ngsig_connestabsucc', 'NG接口连接建立成功次数'),
        ('ngsig_connestabatt', 'NG接口连接建立请求次数'),
        ('context_succinitalsetup', '初始上下文建立成功次数'),
        ('context_attinitalsetup', '初始上下文建立请求次数'),
        ('context_succrate', '初始上下文建立成功率'),
        ('ho_succexecinc', '切换入成功次数'),
        ('ho_attoutintercung', 'gNB间NG切换出请求次数'),
        ('ho_succoutintercung', 'gNB间NG切换出成功次数'),
        ('ho_outintercung_rate', 'gNB间NG切换出成功率'),
        ('pdcp_upoctdl', 'PDCP下行业务字节数'),
        ('pdcp_upoctul', 'PDCP上行业务字节数'),
        ('bh_pdcp_upoctdl', '忙时PDCP下行业务字节数'),
        ('bh_pdcp_upoctul', '忙时PDCP上行业务字节数'),
        ('bh_cellprbrate', '忙时小区PRB利用率'),
        ('bh_prbassnratedl', '忙时下行PRB平均利用率'),
        ('bh_prbassnrateul', '忙时上行PRB平均利用率'),
    ]
    fixed_fields = {'starttime', 'ncgi', 'nrcell_name', 'city', 'area', 'branch', 'grid', 'vendor', 'state', 'cover_type', 'cover_scene'}
    result_list = _build_result_fields(fields, '5G小区KPI报表', 'appdbv3.a_adhoc_kpi_nr_cell_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区，网格，地市，分公司',
        'timedimension': '天',
        'enodebField': 'gnodeb_id', 'cgiField': 'ncgi', 'timeField': 'starttime',
        'cellField': 'nrcell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== 4G KPI ====================
def get_4g_kpi_payload(start_date=None, end_date=None, city=None):
    """4G小区KPI报表payload
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '数据时间'), ('cgi', 'CGI'), ('cell_name', '小区名称'),
        ('city', '地市'), ('area', '区县'), ('branch', '分公司'),
        ('grid', '网格'), ('vendor', '设备厂家'), ('state', '网元状态'),
        ('cover_type', '覆盖类型'), ('cover_scene', '覆盖场景'),
        ('succconnestab', 'RRC连接建立成功次数'),
        ('attconnestab', 'RRC连接建立请求次数'),
        ('rrc_conn_succ_rate', 'RRC连接建立成功率'),
        ('nbrsuccestab', 'E-RAB建立成功数'),
        ('nbrattestab', 'E-RAB建立请求数'),
        ('erab_succ_rate', 'E-RAB建立成功率'),
        ('succexecinc', '切换入成功次数'),
        ('ho_att__out', '切换请求次数'),
        ('ho_succ_rate', '切换成功率'),
        ('upoctdl', '下行业务字节数'),
        ('upoctul', '上行业务字节数'),
        ('bh_upoctdl', '忙时下行业务字节数'),
        ('bh_upoctul', '忙时上行业务字节数'),
        ('bh_cellprbrate', '忙时小区PRB利用率'),
        ('bh_dl_prbuse_rate', '忙时下行PRB平均利用率'),
        ('bh_ul_prbuse_rate', '忙时上行PRB平均利用率'),
    ]
    fixed_fields = {'starttime', 'cgi', 'cell_name', 'city', 'area', 'branch', 'grid', 'vendor', 'state', 'cover_type', 'cover_scene'}
    result_list = _build_result_fields(fields, '4G小区KPI报表', 'appdbv3.a_adhoc_kpi_lte_cell_d', fixed_fields)
    
    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区，网格，地市，分公司',
        'timedimension': '天',
        'enodebField': 'enodeb_id', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'cell', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== 5G MR覆盖 ====================
def get_5g_mr_payload(start_date=None, end_date=None, city=None):
    """5G MR覆盖报表payload

    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    # 基于HAR抓包的正确字段配置
    fields = [
        ('starttime', '记录开始时间'),
        ('ncgi', '小区NCGI'),
        ('nrcell_name', '小区名称'),
        ('nr_rsrp_count', '移动RSRP采样的总采样点'),
        ('nr_rsrp_gt_f110', '移动RSRP采样强于-110采样点'),
        ('nr_rsrp_rate', '移动RSRP采样强于-110覆盖率(%)'),
        ('mro_yd_rsrp_avg', '移动平均RSRP'),
        ('mro_lt_rsrp_avg', '联通平均RSRP'),
        ('mro_dx_rsrp_avg', '电信平均RSRP'),
        ('mro_rh_rsrp_avg', '融合竞对平均RSRP'),
        ('mro_rh_all_count', '移动融合竞对均有RSRP采样的总采样点'),
        ('mro_rh_yd_f110_count', '采集到融合频点是移动大于等于-110采样点'),
        ('mro_rh_f110_count', '移动融合竞对均有RSRP采样的竞对强于-110采样点'),
        ('mro_overlap_rsrp_count', '重叠覆盖采样点'),
        ('mro_all_phr_count', 'PHR总采样点'),
        ('mro_phr_lt_0', 'PHR小于0采样点数'),
        ('mro_phr_lt_0_rate', 'PHR小于0采样点占比'),
        ('mro_yd_ta_dist_avg', '移动平均TA(M)'),
    ]
    fixed_fields = {'starttime', 'ncgi', 'nrcell_name'}
    result_list = _build_result_fields(fields, '5GMR覆盖-小区天', 'appdbv3.a_common_mro_scssrsrp_nr_nrcell', fixed_fields)

    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'

    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区，网格，地市，分公司',
        'timedimension': '天、周、月粒度',
        'enodebField': 'gnodeb_id',
        'cgiField': 'ncgi',
        'timeField': 'starttime',
        'cellField': 'nrcell',
        'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== 45G流量与热点评估物理站级 ====================
def get_flow_hot_spot_station_payload(start_date=None, end_date=None, city=None):
    """45G流量与热点评估物理站级报表payload

    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    fields = [
        ('starttime', '开始时间'), ('endtime', '结束时间'), ('city', '地市'),
        ('station_name', '物理站名称'), ('station_id', '物理站ID'), ('cover_type', '覆盖类型'),
        ('gnodeb_count', '5G逻辑站数量'), ('enodeb_count', '4G逻辑站数量'),
        ('nr_cell_count', '5G小区数量'), ('lte_cell_count', '4G小区数量'),
        ('lte_e_site_list', 'E频站点名列表'), ('lte_d_site_list', 'D频站点名列表'),
        ('lte_f_site_list', 'F频站点名列表'), ('lte_fdd1800_site_list', 'FDD1800站点名列表'),
        ('lte_fdd900_site_list', 'FDD900站点名列表'), ('lte_reverse_site_list', '反向4G站点名列表'),
        ('other_lte_site_list', '其它4G站点列表'), ('nr_2600_site_list', '2.6G站点名列表'),
        ('nr_700_site_list', '700M站点名列表'), ('nr_4900_site_list', '4.9G站点名列表'),
        ('other_nr_site_list', '其它5G站点列表'),
        ('flow_bh_lte_upoctudl', '流量忙时4G流量'), ('flow_bh_nr_upoctudl', '流量忙时5G流量'),
        ('flow_bh_total_upoctudl', '流量忙时45G总流量'), ('flow_bh_nr_upoctudl_rate', '流量忙时5G流量占比'),
        ('flow_bh_lte_connmean', '流量忙时4G RRC连接平均数'), ('flow_bh_lte_connmax', '流量忙时4G RRC连接最大数'),
        ('flow_bh_nr_connmean', '流量忙时5G RRC连接平均数'), ('flow_bh_nr_connmax', '流量忙时5G RRC连接最大数'),
        ('flow_bh_lte_use_rate', '流量忙时4G利用率'), ('lte_hot_level', '流量忙时4G热点等级'),
        ('lte_upoctudl', '4G日流量'), ('nr_upoctudl', '5G日流量'),
        ('total_upoctudl', '45G日总流量'), ('nr_upoctudl_rate', '5G日流量占比'),
    ]
    # 前3个字段(starttime, endtime, city)的datatype应为'1'，与浏览器请求一致
    fixed_fields = {'starttime', 'endtime', 'city'}
    result_list = _build_result_fields(fields, '45G流量与热点评估物理站级', 'appdbv3.a_cap_ltenr_station', fixed_fields)

    # 默认日期
    if start_date is None:
        start_date = '2026-05-07'
    if end_date is None:
        end_date = '2026-05-07'
    if city is None:
        city = '阳江'

    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区',
        'timedimension': '天、周',
        'enodebField': 'gnodeb_id',
        'cgiField': 'cgi',
        'timeField': 'starttime',
        'cellField': 'cell',
        'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': '1'}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


def get_4g_mr_payload(start_date=None, end_date=None, city=None):
    """4G MR覆盖报表payload

    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    # 基于HAR抓包的正确字段配置
    fields = [
        ('starttime', '开始时间'),
        ('cgi', 'cgi'),
        ('cell_name', '小区名'),
        ('city', '地市'),
        ('mro_all_rsrp_count', 'MRO移动总采样点'),
        ('mro_yd_rsrp_gt_f110', 'MRO移动大于等于负110DBM的采样点数'),
        ('mro_yd_rsrp_rate', 'MRO移动覆盖率'),
        ('mro_overlap_rsrp_rate', 'MRO移动重叠覆盖率'),
        ('mro_overlap_rsrp_count', 'MRO移动覆盖采样点数'),
        ('rsrp110_dist_avg', '平均TA'),
    ]
    fixed_fields = {'starttime', 'cgi', 'cell_name', 'city'}
    result_list = _build_result_fields(fields, '4G_MRO_RSRP基础性能_小区', 'appdbv3.a_common_mro_rsrp_lte_cell', fixed_fields)

    # 默认日期
    if start_date is None:
        start_date = '2026-04-19'
    if end_date is None:
        end_date = '2026-04-19'
    if city is None:
        city = '阳江'

    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区，网格，地市，分公司',
        'timedimension': '天、周、月',
        'enodebField': 'enodeb_id',
        'cgiField': 'cgi',
        'timeField': 'starttime',
        'cellField': 'cell',
        'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }
