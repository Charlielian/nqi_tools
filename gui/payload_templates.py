# -*- coding: utf-8 -*-
"""
硬编码Payload模板模块
基于旧版脚本nqi_tools旧版.py中的payload函数，完全硬编码所有参数
"""

def _build_columns_param(field_list):
    """构建DataTables格式的columns参数（与浏览器HAR格式一致）"""
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


def _build_columns_param_v2(field_list):
    """构建DataTables格式的columns参数（包含更多字段，与浏览器HAR格式一致）
    
    浏览器HAR中的columns格式:
    columns[0][data]: starttime
    columns[0][name]: 
    columns[0][searchable]: true
    columns[0][orderable]: true
    columns[0][search][value]: 
    columns[0][search][regex]: false
    """
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
        fixed_datatype_fields: 使用固定datatype='1'的字段集合（字符类型）
        time_datatype_fields: 使用固定datatype='2'的字段集合（时间/整数类型）
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

        # ncgi 和 nrcell_name 在 HAR 中为 datatype='character varying', columntype=2
        if feild in ('ncgi', 'nrcell_name'):
            datatype = 'character varying'
            columntype = 2
        elif feild in fixed_datatype_fields:
            datatype = '1'
        elif feild in ('starttime', 'endtime', 'city'):
            datatype = '2'  # 与浏览器HAR保持一致
        else:
            datatype = 'character varying'
        
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


# ==================== 通用性能报表-小区(天)v3 ====================
def get_common_pm_cell_day_v3_payload(start_date=None, end_date=None, city=None):
    """通用性能报表-小区(天)v3 payload (基于HAR抓包)

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        city: 地市名称
    """
    # 基础字段 (feildtype: 通用性能统计-小区(天))
    base_fields = [
        ('starttime', '记录开始时间'),
        ('endtime', '记录结束时间'),
        ('city', '所属地市'),
        ('area', '所属区县'),
        ('grid', '责任网格'),
        ('branch', '人力区县分公司'),
        ('cgi', 'CGI'),
        ('cell_name', '小区名称'),
    ]
    base_feildtype = '通用性能统计-小区(天)'
    result_list = _build_result_fields(base_fields, base_feildtype, 'appdbv3.a_common_pm_lte_cell_d', set(f[0] for f in base_fields))

    # 干扰指标字段 (feildtype: 干扰指标) - PRB0-99
    interference_fields = [
        ('ulmeannl_prb_avg', '小区RB上行平均干扰电平平均值'),
    ]
    # 添加PRB0-PRB99字段
    for i in range(100):
        interference_fields.append((f'ulmeannl_prb{i}', f'小区RB上行平均干扰电平PRB{i}'))
    interference_result = _build_result_fields(interference_fields, '干扰指标', 'appdbv3.a_common_pm_lte_cell_d', set())
    result_list.extend(interference_result)

    # 默认日期
    if start_date is None:
        start_date = '2026-05-16'
    if end_date is None:
        end_date = '2026-05-17'
    if city is None:
        city = '阳江'

    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': 'city',
        'timedimension': '天粒度',
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


# ==================== 5G干扰报表_自忙时 ====================
def get_5g_interference_zimang_payload(start_date=None, end_date=None, city=None):
    """5G干扰报表_自忙时payload (基于HAR抓包的精确配置)
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    from gui.field_configs import INTERFERENCE_5G_ZIMANG_FIELDS
    
    # 根据HAR抓包：时间维度字段(city, area, grid)没有columntype
    no_columntype_fields = {'starttime', 'endtime', 'city', 'area', 'grid'}
    result_list = []
    for field in INTERFERENCE_5G_ZIMANG_FIELDS:
        feild = field.get('feild', '')
        feildName = field.get('feildName', feild)
        datatype = field.get('datatype', 'character varying')
        columntype = field.get('columntype', '1')
        
        item = {
            'feildtype': '5G_干扰报表_自忙时',
            'table': 'appdbv3.a_interfere_nrcell_zb4',
            'tableName': '5G_干扰报表_自忙时',
            'datatype': datatype,
            'feildName': feildName,
            'feild': feild,
            'poly': '无',
            'anyWay': '无',
            'chart': '无',
            'chartpoly': '无'
        }
        # 这些字段不需要 columntype（与浏览器行为一致）
        if feild not in no_columntype_fields:
            item['columntype'] = columntype
        
        result_list.append(item)
    
    # 默认日期
    if start_date is None:
        start_date = '2025-05-01'
    if end_date is None:
        end_date = '2025-05-15'
    if city is None:
        city = '阳江'
    
    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '天、周',
        'enodebField': 'gnodeb_id', 'cgiField': 'cgi', 'timeField': 'starttime',
        'cellField': 'nrcell', 'cityField': 'city',
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': '1'}, 'columnname': ''},
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
        'indexcount': 0  # 与浏览器保持一致
    }


# ==================== 5G小区容量-周 ====================
def get_5g_capacity_week_payload(start_date=None, end_date=None, city=None):
    """5G小区容量-周报表payload (基于HAR抓包)

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        city: 地市名称
    """
    # 字段列表 - 与 HAR getSelectTable 完全一致（共67个字段，按 sort 顺序排列）
    # HAR 中 sort=15 有3个字段: sectors_name, bh_rru_pdcchcceutil, grid
    fields = [
        ('starttime', '记录开始时间'),
        ('endtime', '记录结束时间'),
        ('city', '地市'),
        ('nrcell_name', '小区名称'),
        ('ncgi', 'NCGI'),
        ('state', '网元状态'),
        ('vendor', '设备厂家'),
        ('freq', '使用频段'),
        ('frequency_band_detail', '详细使用频段'),
        ('cover_type', '覆盖类型'),
        ('cover_scene', '一级场景'),
        ('is_remote', '是否拉远'),
        ('station_name', '站点名称'),
        ('longitude', '经度'),
        ('latitude', '纬度'),
        ('sectors_name', '共站同覆盖小区名称'),
        ('bh_rru_pdcchcceutil', '忙时PDCCH信道CCE占用个数'),
        ('grid', '网格'),
        ('grid_road', '网格道路'),
        ('bh_rru_pdcchcceavail', '忙时PDCCH信道CCE可用个数'),
        ('bh_pdcchcceoccupancyrate', 'PDCCH信道CCE占用率(%)'),
        ('bh_rru_puschprbassn', '忙时上行PUSCH PRB占用数'),
        ('bh_rru_puschprbtot', '忙时上行PUSCH PRB总可用数'),
        ('bh_prbassnrateul', '忙时上行PRB平均利用率(%)'),
        ('bh_rru_pdschprbassn', '忙时下行PDSCH PRB占用数'),
        ('bh_rru_pdschprbtot', '忙时下行PDSCH PRB总可用数'),
        ('bh_prbassnratedl', '忙时下行PRB平均利用率(%)'),
        ('bh_rlc_upoctul', 'RLC层上行字节数(G)'),
        ('bh_rlc_upoctdl', 'RLC层下行字节数(G)'),
        ('bh_mac_cpoctul', 'MAC层上行字节数(G)'),
        ('bh_mac_cpoctdl', 'MAC层下行字节数(G)'),
        ('bh_pdcp_upoctul', 'PDCP层上行字节数(G)'),
        ('bh_pdcp_upoctdl', 'PDCP层下行字节数(G)'),
        ('rlc_upoctul', '日RLC层上行字节数(G)'),
        ('rlc_upoctdl', '日RLC层下行字节数(G)'),
        ('rlc_upoctudl', '日RLC层上下行字节数(G)'),
        ('mac_cpoctudl', 'MAC层上下行字节数(G)'),
        ('pdcp_upoctudl', 'PDCP层上下行字节数(G)'),
        ('is_highload', '是否高负荷'),
        ('bh_rrc_connmean', '忙时RRC连接平均数'),
        ('bh_rrc_connmax', '忙时RRC连接最大数'),
        ('bh_flow_nbrattestab', 'Flow建立请求次数'),
        ('bh_flow_nbrsuccestab', 'Flow建立成功次数'),
        ('bh_kpi_flowsuccconnrate', '忙时流量建立成功率'),
        ('second_scene_detail', '二级场景细化'),
        ('bh_puschprbtot_reuse', '忙时上行PRB可用空分层数'),
        ('bh_puschprbassn_reuse', '忙时上行PRB占用空分层数'),
        ('bh_avgdtchmimolayerul', '忙时上行空分复用层数'),
        ('bh_pdschprbtot_reuse', '忙时下行PRB可用空分层数'),
        ('bh_pdschprbassn_reuse', '忙时下行PRB占用空分层数'),
        ('bh_avgdtchmimolayerdl', '忙时下行空分复用层数'),
        ('maxdtchmimolayerul', '最大上行MIMO层数'),
        ('maxdtchmimolayerdl', '最大下行MIMO层数'),
        ('bh_dtchmimoprbassnrateul', '忙时上行空分PRB占用率'),
        ('bh_dtchmimoprbassnratedl', '忙时下行空分PRB占用率'),
        ('bh_cellprbrate', '忙时小区PRB利用率(%)'),
        ('bh_flow_nbrhoinc', '忙时切换入成功次数'),
        ('bh_upoctudl_perflow', '忙时每Flow上下行流量'),
        ('band_width', '带宽'),
        ('ssbfrequenc', '中心载频信道号'),
        ('txrxmode', '收发模式'),
        ('area_type', '区域类型'),
        ('micro_grid', '微网格'),
        ('cover_scene1', '场景1'),
        ('cover_scene2', '场景2'),
        ('cover_scene3', '场景3'),
        ('cover_scene4', '场景4'),
    ]

    # 固定datatype='1'的字段 - 与 HAR 一致
    fixed_fields = {'starttime', 'endtime', 'city', 'ncgi', 'nrcell_name'}
    result_list = _build_result_fields(fields, '5G小区容量报表 - 周粒度', 'appdbv3.a_adhoc_capacity_nr_nrcell_w', fixed_fields)

    # 默认日期
    if start_date is None:
        start_date = '2026-05-01'
    if end_date is None:
        end_date = '2026-05-25'
    if city is None:
        city = '阳江'

    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '周',
        'enodebField': 'station_name', 'cgiField': 'ncgi', 'timeField': 'starttime',
        'cellField': 'nrcell_name', 'cityField': 'city',
        'columns': _build_columns_param([f[0] for f in fields]),
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0  # HAR使用0，与浏览器保持一致
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


# ==================== 重要场景-周 ====================
def get_important_scene_week_payload(start_date=None, end_date=None, city=None):
    """重要场景-周报表payload (基于HAR抓包)

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        city: 地市名称
    """
    # 字段列表 (从HAR日志中提取)
    fields = [
        ('starttime', '记录开始时间'), ('endtime', '记录结束时间'), ('city', '所属地市'),
        ('cgi', 'CGI'), ('freq_name', '频点'),
        ('cell_name', '小区名称'), ('state', '网元状态'),
        ('scene', '场景'), ('scene_name', '场景具体名称'),
        ('upoctudl_avg', '日平均4G流量（GB）'),
        ('ul_prbuse_rate_max', '日峰值上行PRB平均利用率'),
        ('dl_prbuse_rate_max', '日峰值下行PRB平均利用率'),
        ('pdcchcceutilratio_max', '日峰值PDCCH信道CCE占用率'),
        ('bh_effectiveconnmax', '自忙时有效RRC连接最大数'),
        ('bh_connmax', '自忙时RRC连接最大数'),
        ('bh_ul_prbuse_rate', '自忙时上行PRB平均利用率'),
        ('bh_dl_prbuse_rate', '自忙时下行PRB平均利用率'),
        ('bh_pdcchcceutilratio', '自忙时PDCCH信道CCE占用率'),
        ('radio_succ_rate', '无线接通率'),
        ('radio_drop_rate_cell', '无线掉线率(小区级)'),
        ('call_connect_rate', '呼叫接通率(MTC+MOC)'),
        ('volte_drop_rate', 'VOLTE掉话率'),
        ('esrvcc_ho_succ_rate', 'ESRVCC切换成功率'),
        ('volte_voice_traffic', 'VOLTE语音话务量'),
        ('is_highflow', '是否高流量预警小区'),
        ('is_highload', '是否高负荷待扩容小区'),
        ('is_dilatation', '是否扩容小区'),
        ('is_carry', '是否纳入载波调度'),
        ('is_city_tail', '是否本地市尾部小区'),
        ('is_province_tail', '是否全省尾部小区'),
        ('longitude', '经度'), ('latitude', '维度'),
        ('cover', '覆盖类型'), ('coverlayer', '覆盖层标识'),
        ('capacitylayer', '容量层标识'), ('cell_scene_name', '小区所属区域'),
        ('vendor', '设备厂家'), ('freq', '使用频段'),
        ('flow_coefficient', '流量系数'), ('bandwidth', '小区带宽'),
        ('is_remote', '是否拉远'), ('station_name', '所属站点名称'),
    ]

    # 固定datatype='1'的字段（时间维度相关）
    fixed_fields = {'starttime', 'endtime', 'cgi', 'cell_name', 'city'}
    result_list = _build_result_fields(fields, '[管理视图]重要场景-小区周粒度', 'appdbv3.a_overview_ispm_lte_cell_w', fixed_fields)

    # 默认日期
    if start_date is None:
        start_date = '2026-05-01'
    if end_date is None:
        end_date = '2026-05-25'
    if city is None:
        city = '阳江'

    return {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区', 'timedimension': '周',
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
    """5G小区KPI报表payload (基于HAR抓包的正确配置)
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    # SA_CU性能 - 基于HAR抓包
    fields = [
        ('starttime', '数据时间'), ('ncgi', 'NCGI'), ('nrcell_name', '小区名称'),
        ('branch', '人力区县分公司'), ('grid', '责任网格'), ('city', '所属地市'),
        ('area', '所属区县'), ('vendor', '设备厂家'), ('cover_type', '覆盖类型'),
        ('rrc_connmean', 'RRC连接平均数'), ('rrc_connmax', 'RRC连接最大数'),
        ('rrc_attconnestab', 'RRC连接建立请求次数'), ('rrc_succconnestab', 'RRC连接建立成功次数'),
        ('kpi_rrcsuccconnrate', 'RRC连接建立成功率'), ('flow_nbrattestab', 'Flow建立请求数'),
        ('flow_nbrsuccestab', 'Flow建立成功数'), ('kpi_flowsuccconnrate', 'QoS+Flow建立成功率'),
        ('ngsig_connestabatt', 'NG接口UE相关逻辑信令连接建立请求次数'),
        ('ngsig_connestabsucc', 'NG接口UE相关逻辑信令连接建立成功次数'),
        ('kpi_ngsig_succconnrate', 'NG接口UE相关逻辑信令连接建立成功率'),
        ('kpi_wirelesssuccconnrate', '无线接通率'), ('context_attrelgnb', 'gNB请求释放上下文数'),
        ('context_attrelgnb_normal', '正常的gNB请求释放上下文数'),
        ('context_succinitalsetup', '初始上下文建立成功次数'), ('context_nbrleft', '遗留上下文个数'),
        ('ho_succexecinc', '切换入成功次数'),
        ('rrc_succconnreestab_nonsrccell', 'RRC连接重建成功次数(非源侧小区)'),
        ('kpi_wirelessdroprate_celllevel', '无线掉线率_小区级'),
        ('flow_nbrreqrelgnb', 'gNB请求释放的Flow数'),
        ('flow_nbrreqrelgnb_normal', '正常的GNB请求释放的Flow数'),
        ('flow_hoadmitfail', '切出失败的Flow数'), ('flow_nbrleft', '遗留Flow个数'),
        ('flow_nbrhoinc', '切换入Flow数'), ('kpi_flowdroprate_celllevel', 'Flow掉线率（小区级）'),
        ('rrc_attconnreestab', 'RRC连接重建请求次数'), ('kpi_rrcconnreestabrate', 'RRC连接重建比率'),
        ('ho_attoutintercung', 'gNB间NG切换出准备请求次数'),
        ('ho_succoutintercung', 'gNB间NG切换出成功次数'),
        ('kpi_hosuccoutintergnbrate_ng', 'gNB间NG切换成功率'),
        ('ho_attoutintercuxn', 'gNB间Xn切换出准备请求次数'),
        ('ho_succoutintercuxn', 'gNB间Xn切换出成功次数'),
        ('kpi_hosuccoutintergnbrate_xn', 'gNB间Xn切换成功率'),
        ('kpi_hosuccoutintergnbrate', 'gNB间切换成功率'),
        ('ho_attoutintracuinterdu', 'CU内DU间切换出执行请求次数'),
        ('ho_succoutintracuinterdu', 'CU内DU间切换出执行成功次数'),
        ('ho_attoutcuintradu', 'CU内DU内切换出执行请求次数'),
        ('ho_succoutintradu', 'CU内DU内切换出成功次数'),
        ('kpi_hosuccoutintragnbrate', 'gNB内切换成功率'),
        ('kpi_hosuccoutrate', '切换成功率'),
        ('ho_attoutexecintrafreq', '同频切换出执行请求次数'),
        ('ho_succoutintrafreq', '同频切换出成功次数'),
        ('kpi_hosuccoutrate_intrafreq', '同频切换执行成功率'),
        ('ho_attoutexecinterfreq', '异频切换出执行请求次数'),
        ('ho_succoutinterfreq', '异频切换出成功次数'),
        ('kpi_hosuccoutrate_interfreq', '异频切换执行成功率'),
        ('kpi_pdcpupoctul', 'PDCP上行业务字节数'),
        ('kpi_pdcpupoctdl', 'PDCP下行业务字节数'),
        ('ee_carriershutdowntime', '载波关断时长'),
        ('flow_nbrattestab_5qi1', 'Flow建立请求数5QI1'),
        ('flow_nbrsuccestab_5qi1', 'Flow建立成功数5QI1'),
        ('kpi_wirelesssuccconnrate_5qi1', 'VoNR无线接通率(5QI1)'),
        ('flow_nbrreqrelgnb_5qi1', 'gNB请求释放的Flow数5QI1'),
        ('flow_nbrreqrelgnb_normal_5qi1', '正常的gNB请求释放的Flow数5QI1'),
        ('flow_hoadmitfail_5qi1', '切出接纳失败的Flow数5QI1'),
        ('flow_nbrleft_5qi1', '遗留Flow个数5QI1'), ('flow_nbrhoinc_5qi1', '切换入Flow数5QI1'),
        ('kpi_wirelessdroprate_celllevel_5qi1', '掉线率(5QI1)(小区级)'),
        ('kpi_wirelessdroprate_netlevel_5qi1', '掉线率(5QI1)(网络级)'),
        ('pdcp_upoctul_5qi1', '小区用户面上行PDCP+PDU字节数5QI1'),
        ('pdcp_upoctdl_5qi1', '小区用户面下行PDCP+PDU字节数5QI1'),
        ('pdcp_nbrpktlossul_5qi1', '上行PDCP丢包数5QI1'),
        ('pdcp_nbrpktul_5qi1', '上行PDCP包数5QI1'),
        ('kpi_pdcpnbrpktlossrateul_5qi1', '上行PDCP+SDU平均丢包率(5QI1)'),
        ('flow_nbrattestab_5qi2', 'Flow建立请求数5QI2'),
        ('flow_nbrsuccestab_5qi2', 'Flow建立成功数5QI2'),
        ('kpi_wirelesssuccconnrate_5qi2', 'VoNR无线接通率(5QI2)'),
        ('flow_nbrreqrelgnb_5qi2', 'gNB请求释放的Flow数5QI2'),
        ('flow_nbrreqrelgnb_normal_5qi2', '正常的gNB请求释放的Flow数5QI2'),
        ('flow_hoadmitfail_5qi2', '切出接纳失败的Flow数5QI2'),
        ('flow_nbrleft_5qi2', '遗留Flow个数5QI2'), ('flow_nbrhoinc_5qi2', '切换入Flow数5QI2'),
        ('kpi_wirelessdroprate_celllevel_5qi2', '掉线率(5QI2)(小区级)'),
        ('kpi_wirelessdroprate_netlevel_5qi2', '掉线率(5QI2)(网络级)'),
        ('pdcp_upoctul_5qi2', '小区用户面上行PDCP+PDU字节数5QI2'),
        ('pdcp_upoctdl_5qi2', '小区用户面下行PDCP+PDU字节数5QI2'),
        ('pdcp_nbrpktlossul_5qi2', '上行PDCP丢包数5QI2'),
        ('pdcp_nbrpktul_5qi2', '上行PDCP包数5QI2'),
        ('kpi_pdcpnbrpktlossrateul_5qi2', '上行PDCP+SDU平均丢包率（5QI2）'),
        ('vonr_voice_traffic', 'VoNR语音话务量'), ('vinr_voice_traffic', 'ViNR语音话务量'),
        ('iratho_succouteutran_epsfallback', 'EpsFallBack切换至LTE成功次数'),
        ('iratho_succprepouteutran_epsfallback', 'EpsFallBack切换至LTE准备成功次数'),
        ('flow_nbrattestab_epsfb', 'EPS+fallback触发的Flow建立请求数'),
        ('iratho_attouteutran_epsfallback', 'EpsFallBack切换至LTE准备请求次数'),
        ('kpi_vonr_flowsuccconnrate', 'VoNR业务Flow建立成功率(5QI1)（小区级）'),
        ('kpi_vinr_flowsuccconnrate', 'ViNR业务Flow建立成功率(5QI2)（小区级）'),
        ('kpi_vonr_flowdroprate_celllevel', 'VoNR业务Flow掉线率（5QI1）（小区级）'),
        ('kpi_vinr_flowdroprate_celllevel', 'ViNR业务Flow掉线率（5QI2）（小区级）'),
        ('kpi_wirelessdroprate_netlevel', '无线掉线率（网络级）'),
        ('kpi_flowdroprate_netlevel', 'Flow掉线率（网络级）'),
        ('kpi_vonr_flowdroprate_netlevel', 'VoNR业务QoS+Flow掉线率（5QI1）（网络级）'),
        ('kpi_hosuccoutrate_intersystemnrtolte', 'NR到LTE的系统间切换出成功率'),
        ('kpi_hosuccoutrate_intersystemltetonr', 'LTE到NR的系统间切换入成功率'),
        ('kpi_esfbhosuccoutrate_intersystemnrtolte', 'NR到LTE的基于切换的EPSFB成功率'),
        ('rrc_redirecttolte_epsfallback', 'EPS+fallback+RRC+重定向到LTE次数'),
        ('iratho_succprepouteutran', '切换至LTE准备成功次数'),
        ('iratho_attouteutran', '切换至LTE准备请求次数'),
        ('iratho_attprepinc', 'LTE切换入准备请求次数'),
        ('iratho_succprepinc', 'LTE切换入准备成功次数'),
        ('iratho_succouteutran', '切换至LTE成功次数'),
        ('kpi_vonr_succconnrate', 'VoNR业务接通成功率(5QI1)'),
        ('kpi_vinr_succconnrate', 'ViNR业务接通成功率(5QI2)'),
        ('kpi_slice_flowsuccconnrate', '每切片QOS+FLOW建立成功率'),
        ('kpi_inactive_succconnrate', 'RRC+Resume成功率'),
        ('kpi_hosuccoutrate_vonrtolte', 'VoNR到VoLTE的系统间切换出成功率'),
        ('kpi_hosuccoutrate_vinrtolte', 'ViNR到ViLTE的系统间切换出成功率'),
        ('kpi_hosuccoutrate_intersystemvoltetovonr', 'VoLTE到VoNR的系统间切换入成功率'),
        ('kpi_hosuccoutrate_intersystemviltetovinr', 'ViLTE到ViNR的系统间切换入成功率'),
        ('kpi_hosuccoutrate_vonr', 'VoNR系统内切换成功率'),
        ('kpi_hosuccoutrate_vinr', 'ViNR系统内切换成功率'),
        ('kpi_pdcpnbrpktlossrateul', 'PDCP层上行丢包率'),
        ('kpi_vonrtraffic_5qi1', 'VoNR语音话务量（小时级）'),
        ('kpi_vinrtraffic_5qi1', 'ViNR视频话务量（小时级）'),
        ('flow_nbrsuccestab_vonr', 'VoNRFlow建立成功数'),
        ('flow_nbrattestab_vonr', 'VoNRFlow建立请求数'),
        ('flow_nbrsuccestab_vinr', 'ViNRFlow建立成功数'),
        ('flow_nbrattestab_vinr', 'ViNRFlow建立请求数'),
        ('flow_nbrsuccestabslice', '每切片FLOW建立成功数'),
        ('flow_nbrattestabslice', '每切片FLOW建立请求数'),
        ('rrc_succconnresume', 'Resume成功次数'), ('rrc_attconnresume', 'resume请求次数'),
        ('iratho_succouteutran_vonr', 'VoNR切换至LTE成功Flow数'),
        ('iratho_attouteutran_vonr', 'VoNR切换至LTE准备请求Flow数'),
        ('iratho_succouteutran_vinr', 'ViNR切换至LTE成功Flow数'),
        ('iratho_attouteutran_vinr', 'ViNR切换至LTE准备请求Flow数'),
        ('iratho_succexecinc_voltetovonr', 'LTEVoLTEtoVoNR切换入成功flow数'),
        ('iratho_attprepinc_voltetovonr', 'LTEVoLTEtoVoNR切换入准备请求flow数'),
        ('iratho_succexecinc_viltetovinr', 'LTEViLTEtoVoiNR切换入成功flow数'),
        ('iratho_attprepinc_viltetovinr', 'LTEViLTEtoViNR切换入准备请求flow数'),
        ('ho_succoutintercung_vonr', 'VoNRgNB间NG切换出成功flow数'),
        ('ho_succoutintercuxn_vonr', 'VoNRgNB间Xn切换出成功flow数'),
        ('ho_succoutintradu_vonr', 'VoNRCU内DU内切换出成功flow数'),
        ('ho_attoutintercung_vonr', 'VoNRgNB间NG切换出准备请求flow数'),
        ('ho_attoutintercuxn_vonr', 'VoNRgNB间Xn切换出准备请求flow数'),
        ('ho_attprepoutcuintradu_vonr', 'VoNRCU内DU内切换出准备请求flow数'),
        ('ho_succoutintercung_vinr', 'ViNRgNB间NG切换出成功flow数'),
        ('ho_succoutintercuxn_vinr', 'ViNRgNB间Xn切换出成功flow数'),
        ('ho_succoutintradu_vinr', 'ViNRCU内DU内切换出成功flow数'),
        ('ho_attoutintercung_vinr', 'ViNRgNB间NG切换出准备请求flow数'),
        ('ho_attoutintercuxn_vinr', 'ViNRgNB间Xn切换出准备请求flow数'),
        ('ho_attprepoutcuintradu_vinr', 'ViNRCU内DU内切换出准备请求flow数'),
        ('pdcp_nbrpktlossul', '上行PDCP丢包数'), ('pdcp_nbrpktul', '上行PDCP包数'),
        ('flow_nbrmeanestab_5qi1', '5QI1的平均Flow数'),
        ('flow_nbrmeanestab_5qi2', '5QI2的平均Flow数'),
        ('kpi_wirelesssuccconnrate_v1_8', '无线接通率（1.8算法）'),
        ('kpi_vonr_flowdroprate_netlevel_v1_8', 'VONR业务QOS+FLOW掉线率（5QI1）（网络级）_（1.8算法）'),
        ('kpi_hosuccoutrate_intersystemltetonr_v1_8', 'LTE到NR的系统间切换入成功率_（1.8算法）'),
        ('flow_succestab_resume_vonr', 'VoNR+Resume建立成功的Flow数'),
        ('iratho_succexecinc', 'LTE切换入成功次数'),
    ]
    fixed_fields = {'starttime', 'ncgi', 'nrcell_name', 'city', 'area', 'branch', 'grid', 'vendor', 'cover_type'}
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


# ==================== 4G KPI ====================
def get_4g_kpi_payload(start_date=None, end_date=None, city=None):
    """4G小区KPI报表payload (基于HAR抓包的正确配置)
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，按日查询时为单日
        end_date: 结束日期 (YYYY-MM-DD)，按日查询时与start_date相同
        city: 地市名称
    """
    # 公共信息（小区级粒度）- 基于HAR抓包
    public_fields = [
        ('starttime', '开始时间'), ('endtime', '结束时间'), ('cgi', 'CGI'),
        ('cell_name', '小区名称'), ('city', '所属地市'), ('area', '所属区县'),
        ('grid', '网格'), ('marketduty', '责任田'), ('marketgrid', '市场网格'),
        ('network_type', '网络制式'), ('state', '网元状态'), ('cover_type', '覆盖类型'),
        ('cover_scene1', '一级场景'), ('cover_scene2', '二级场景'),
        ('cover_scene3', '三级场景'), ('cover_scene4', '四级场景'),
        ('freq', '频段'), ('vendor', '厂家'),
        ('uplastttioctdl', '用户面下行尾包字节数'), ('uplastttioctul', '用户面上行尾包字节数'),
    ]
    
    # 常用指标 - 基于HAR抓包
    kpi_fields = [
        ('branch', '人力区县分公司'),
        ('attconnestab', 'RRC连接建立请求次数'),
        ('rrc_succ_rate', 'RRC连接建立成功率(%)'),
        ('rrc_restab_rate', 'RRC连接重建比率(%)'),
        ('nbrattestab', 'E-RAB建立请求数'),
        ('nbrsuccestab', 'E-RAB建立成功数'),
        ('e_rab_succ_rate', 'E-RAB建立成功率(%)'),
        ('radio_succ_rate', '无线接通率(%)'),
        ('nbrattestab_1', 'E-RAB建立请求数(QCI=1)'),
        ('e_rab_succ_rate_1', 'E-RAB建立成功率(QCI=1)(%)'),
        ('nbrfailestab_rsnotavailable', '无线资源不足原因导致的E-RAB建立失败数'),
        ('e_rab_block_rate', 'E-RAB拥塞率(无线资源不足)(%)'),
        ('nbrreqrelenb', 'eNB请求释放的E-RAB数'),
        ('nbrreqrelenb_normal', '正常的eNB请求释放的E-RAB数'),
        ('hofail', '切出失败的E-RAB数'),
        ('nbrleft', '遗留上下文个数'),
        ('nbrhoinc', '切换入E-RAB数'),
        ('erab_drop_rate', 'E-RAB掉线率(%)'),
        ('attrelenb', 'eNB请求释放上下文数'),
        ('attrelenbnormal', '正常的eNB请求释放上下文数'),
        ('succinitalsetup', '初始上下文建立成功次数'),
        ('nbrleft_context', '遗留上下文个数CONTEXT'),
        ('radio_drop_rate', '无线掉线率(%)'),
        ('radio_drop_rate_cell', '无线掉线率(小区级)(%)'),
        ('attrelenb_userinactivity', '用户不活动原因eNB请求释放上下文数'),
        ('radio_drop_rate_noui', '无线掉线率(剔除UI原因)(%)'),
        ('radio_drop_rate_cell_noui', '无线掉线率(剔除UI原因)(小区级)(%)'),
        ('nbrreqrelenb_userinactivity', '用户不活动原因eNB请求释放的E-RAB数'),
        ('erab_drop_rate_noui', 'E-RAB掉线率(剔除UI原因)(小区级)(%)'),
        ('enbout_succ_rate_s1', 'eNB间S1切换成功率(%)'),
        ('enbinter_succ_rate_x2', 'eNB间X2切换成功率(%)'),
        ('enbinter_succ_rate', 'eNB间切换成功率(%)'),
        ('enbintra_succ_rate', 'eNB内切换成功率(%)'),
        ('ho_succ_out', '切换成功次数'),
        ('ho_att__out', '切换请求次数'),
        ('enbout_succ_rate', '切换成功率(%)'),
        ('intrafreq_succ_rate', '同频切换执行成功率(%)'),
        ('interfreq_succ_rate', '异频切换执行成功率(%)'),
        ('lte_gsm_succ_rate', 'LTE到2G切换成功率(%)'),
        ('gsm_lte_succ_rate', '2G到LTE切换成功率(%)'),
        ('lte_utran_succ_rate', 'LTE到3G切换成功率(%)'),
        ('utran_lte_succ_rate', '3G到LTE切换成功率(%)'),
        ('nbrpktlossul', '小区上行丢包数'),
        ('nbrpktul', '小区上行包数'),
        ('rktul_loss_rate', '小区用户面上行丢包率(ppm)'),
        ('nbrpktlossdl', '小区下行丢包数'),
        ('nbrpktdl', '小区下行包数'),
        ('rktdl_loss_rate', '小区用户面下行丢包率(ppm)'),
        ('mac_ul_reser_rate', 'MAC层上行误块率(%)'),
        ('mac_dl_reser_rate', 'MAC层下行误块率(%)'),
        ('harq_ul_rate', '上行初始HARQ重传比率(%)'),
        ('harq_dl_rate', '下行初始HARQ重传比率(%)'),
        ('rank2_rate', '下行双流占比(%)'),
        ('ul_qpsk_rate', '上行QPSK编码比例(%)'),
        ('dl_qpsk_rate', '下行QPSK编码比例(%)'),
        ('pkt_loss_ul_1', 'VoLTE上行丢包率(ppm)'),
        ('pkt_loss_dl_1', 'VoLTE下行丢包率(ppm)'),
        ('ul_rtb_rate_1', '上行半持续调度次数占比(%)'),
        ('dl_rtb_rate_1', '下行半持续调度次数占比(%)'),
        ('upoctul', '上行流量(KByte)'),
        ('upoctdl', '下行流量(KByte)'),
        ('ul_thrp', '上行用户平均速率(Mbps)'),
        ('dl_thrp', '下行用户平均速率(Mbps)'),
        ('ul_dtchprb_rate', '上行业务信息PRB占用率(%)'),
        ('ul_ctrlprb_rate', '上行控制信息PRB占用率(%)'),
        ('dl_dtchprb_rate', '下行业务信息PRB占用率(%)'),
        ('dl_ctrlprb_rate', '下行控制信息PRB占用率(%)'),
        ('puschprbassn', '上行PUSCHPRB占用数'),
        ('ul_prbuse_rate', '上行PRB平均利用率(%)'),
        ('puschprbtot', '上行PUSCHPRB可用数'),
        ('pdschprbtot', '下行PDSCHPRB可用数'),
        ('pdschprbassn', '下行PDSCHPRB占用数'),
        ('dl_prbuse_rate', '下行PRB平均利用率(%)'),
        ('prbuse_rate', '无线利用率(%)'),
        ('pagreceived', '寻呼记录接收个数'),
        ('pagdiscarded', '寻呼记录丢弃个数'),
        ('page_disc_rate', 'eNodeB寻呼拥塞率(%)'),
        ('volte_voice_traffic', 'VOLTE语音话务量'),
    ]
    
    # 合并所有字段
    fields = public_fields + kpi_fields
    fixed_fields = {f[0] for f in public_fields}
    result_list = _build_result_fields(fields, '常用指标', 'appdbv3.a_common_pm_lte', fixed_fields)
    
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
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': '1'}, 'columnname': ''},
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
        'result': {'result': result_list, 'tableParams': {'supporteddimension': None, 'supportedtimedimension': '1'}, 'columnname': ''},
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': f'{start_date} 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': f'{end_date} 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }


# ==================== 共站同覆盖小区_4g_5g ====================
def get_sectors_4g_5g_payload(start_date=None, end_date=None, city=None):
    """共站同覆盖小区_4g_5g报表payload（标准DataTables格式）

    Args:
        start_date: 开始日期 (YYYY-MM-DD)，工参表通常不需要
        end_date: 结束日期 (YYYY-MM-DD)，工参表通常不需要
        city: 地市名称
    """
    # 默认日期（工参表通常使用当前日期）
    if start_date is None:
        start_date = '2026-06-10'
    if end_date is None:
        end_date = '2026-06-10'
    if city is None:
        city = '阳江'

    # 字段列表（标准化格式）
    result_list = [
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '物理站名', 'feild': 'station_name', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '站型', 'feild': 'sitetype', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '覆盖类型', 'feild': 'cover_type', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '经度', 'feild': 'longitude', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '纬度', 'feild': 'latitude', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '路测网格', 'feild': 'grid_road', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '小区方向角', 'feild': 'azimuth', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '机械下倾角', 'feild': 'tilt', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '电下倾角', 'feild': 'elcontroldecline', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '天线高度', 'feild': 'height', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '天线ID', 'feild': 'ant_cuid', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '天线名称', 'feild': 'ant_name', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': 'CGI', 'feild': 'cgi', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '小区名称', 'feild': 'cell_name', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '使用频段', 'feild': 'freq', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '中心载频的信道号', 'feild': 'channelnum', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '小区状态', 'feild': 'state', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '地市', 'feild': 'city', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '归属区县', 'feild': 'area', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '乡镇街道', 'feild': 'street_name', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '详细频段', 'feild': 'channelnum_re', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '共站同覆盖编号', 'feild': 'sectors_no', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '共站同覆盖宽度', 'feild': 'sectors_width', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '最大同频天线数', 'feild': 'freq_ant_num', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '是否同频天线同共站同覆盖', 'feild': 'is_sectors_freq', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '共站同覆盖名', 'feild': 'sectors_name', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '聚合物理宏站共站同覆盖区域名', 'feild': 'sectors_name_macro', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '网络制式', 'feild': 'network_type', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '扇区id', 'feild': 'sectors_id', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '是否覆盖层', 'feild': 'is_coverage', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '小区所属区域', 'feild': 'cell_scene_name', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
        {'feildtype': '共站同覆盖小区_4g_5g', 'table': 'appdbv3.a_struct_sectors_d', 'tableName': '共站同覆盖小区_4g_5g',
         'datatype': '1', 'columntype': 1, 'feildName': '小区所属区域类型', 'feild': 'cell_scene_type', 'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'},
    ]

    # 字段名列表（用于columns参数）
    field_names = [r['feild'] for r in result_list]

    return {
        'draw': 1,
        'start': 0,
        'length': 200,
        'total': 0,
        'geographicdimension': '小区',
        'timedimension': '天粒度',
        'enodebField': 'enodeb_id',
        'cgiField': 'cgi',
        'timeField': 'starttime',
        'cellField': 'cell',
        'cityField': 'city',
        'columns': [
            {'data': fn, 'name': '', 'searchable': True, 'orderable': True, 'search': {'value': '', 'regex': False}}
            for fn in field_names
        ],
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {
            'result': result_list,
            'tableParams': {'supporteddimension': None, 'supportedtimedimension': ''},
            'columnname': ''
        },
        'where': [
            {'datatype': 'character', 'feild': 'curr_flag', 'feildName': '', 'symbol': '=', 'val': '1', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': city, 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }
