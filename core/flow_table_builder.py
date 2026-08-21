# -*- coding: utf-8 -*-
"""
45G流量表合成模块
负责从大数据平台下载数据并合成45G容量表

处理链路说明：
    1. 先按周起止日期和地市构造查询条件，下载八类源表；
    2. 以5G/4G周容量表分别作为主表，再把天粒度、MR、KPI及共站同覆盖
       数据按小区标识关联并聚合；
    3. 对流量系数、长尾和负荷等派生指标执行业务阈值判断；
    4. 将5G和4G结果统一为“网络制式 + CGI/NCGI”结构，合并成45G总表，
       最后输出单独的5G、4G和45G文件。

这里的“45G”是4G与5G容量结果的合称，并不是第五代网络。各源表的
字段名称、粒度和单位可能不同，下面的注释重点说明它们如何在合成阶段
对齐，而不重复报表模板中的全部字段。
"""

import os
import logging
import time
import inspect
# TODO: 使用 inspect.signature 检测 payload_func 参数个数，说明 payload 函数签名不一致。
# 建议统一 payload 函数签名（如统一为 (start_date, end_date, city)），消除运行时反射。
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import copy

import pandas as pd

from utils.config import OUTPUT_DIR
from utils.logger import ensure_dirs, get_report_logger
from core.export import export_dataframe_streaming
from core.query import JXCXQuery

logger = logging.getLogger(__name__)


# 合成45G流量表需要的数据源配置
SYNTHESIZE_45G_TABLES = [
    '5G小区容量-周',
    '5G小区容量报表',
    '5GMR覆盖-小区天',
    '5G小区性能KPI报表',
    '重要场景-周',
    '重要场景-天',
    '4GMR覆盖-小区天',
    '共站同覆盖小区_4g_5g',
]


def get_week_date_range(week_start_date):
    """获取指定周的开始日期和结束日期（周一至周日）
    
    Args:
        week_start_date: 周开始日期（周一）
        
    Returns:
        tuple: (start_date, end_date) 日期字符串格式 YYYY-MM-DD
    """
    start_date = week_start_date
    end_date = start_date + timedelta(days=6)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')


def get_week_number(date_str):
    """获取日期对应的周数（年内第几周）
    
    Args:
        date_str: 日期字符串 YYYY-MM-DD
        
    Returns:
        int: 周数（1-53）
    """
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    return dt.isocalendar()[1]


class FlowTableBuilder:
    """45G流量表合成器"""
    
    def __init__(self, session, city, week_start_date, progress_callback=None):
        """
        初始化一次45G合成任务的上下文。

        Args:
            session: 已登录的requests Session。它代表主线程的登录态，后续
                下载线程只复制其 cookies 和连接属性，不直接共享这个对象。
            city: 地市列表，逗号分隔；会原样传给后端 payload 的 city 条件。
            week_start_date: 周开始日期（周一），datetime对象；结束日由此
                顺延六天，查询窗口按 YYYY-MM-DD 传递给源表接口。
            progress_callback: 进度回调函数 callback(message, progress_percent)。

        合成结果保存在 self.data 中，键是源表名称，值是 DataFrame。这个
        显式的中间层使“下载源表”和“构建容量表”分离，也便于源表缺失时
        只跳过对应关联而不改变其他已下载数据。
        """
        self.session = session
        self.city = city
        self.week_start = week_start_date
        self.start_date, self.end_date = get_week_date_range(week_start_date)
        self.week_num = get_week_number(self.start_date)
        self.progress_callback = progress_callback
        
        # 创建即席查询实例
        self.jxcx = JXCXQuery(session)
        
        # 数据存储
        self.data = {}
        
        # 创建输出目录
        self.output_dir = self._create_output_dir()
        
        # 报表日志
        self.report_logger = get_report_logger(f'45G流量表_{self.start_date}_{self.end_date}')
    
    def _log(self, message, level='info'):
        """记录日志到文件和回调"""
        getattr(self.report_logger, level)(message)
        if self.progress_callback:
            self.progress_callback(message)
    
    def _create_output_dir(self):
        """创建输出目录结构"""
        dir_name = f"45G流量表_{self.start_date.replace('-', '')}_{self.end_date.replace('-', '')}"
        base_dir = Path(OUTPUT_DIR)

        output_dir = base_dir / dir_name
        raw_dir = output_dir / "原始数据"
        merged_dir = output_dir / "合成表"

        raw_dir.mkdir(parents=True, exist_ok=True)
        merged_dir.mkdir(parents=True, exist_ok=True)

        self.raw_dir = raw_dir
        self.merged_dir = merged_dir

        return output_dir
    
    def _download_single_table(self, table_name):
        """下载单个数据表（用于并行下载）。

        每个任务都是一个独立的后端查询会话：requests.Session 不能安全地
        被多个线程同时复用，因此这里只复制登录 cookies、headers 等连接
        配置。这样既保留登录态，又避免一个线程修改连接状态时影响其他
        源表请求。

        Args:
            table_name: 表名。

        Returns:
            dict: 包含 table_name、df、success、error_message 的结果字典。
                df 为空或查询失败时仍返回结构化结果，供主线程记录失败原因。
        """
        # 为每个线程创建独立的requests.Session（复制cookies，避免并发共享同一Session）
        import requests as req
        thread_session = req.Session()
        for c in self.session.cookies:
            thread_session.cookies.set_cookie(c)
        for attr in ('verify', 'trust_env', 'headers', 'auth', 'proxies', 'params', 'cert'):
            if hasattr(self.session, attr):
                setattr(thread_session, attr, copy.copy(getattr(self.session, attr)))
        jxcx = JXCXQuery(thread_session)
        
        try:
            # 进入即席查询模块
            if not jxcx.enter_jxcx():
                return {
                    'table_name': table_name,
                    'df': None,
                    'success': False,
                    'error': "进入即席查询模块失败"
                }

            # 构建payload
            from gui.widgets import TableConfig
            payload = None

            table_config = TableConfig.get_table_config(table_name)
            if table_config and table_config.get('payload_func'):
                payload_func = table_config.get('payload_func')
                try:
                    sig = inspect.signature(payload_func)
                    if len(sig.parameters) > 0:
                        payload = payload_func(self.start_date, self.end_date, self.city)
                    else:
                        payload = payload_func()
                except (ValueError, TypeError):
                    try:
                        payload = payload_func(self.start_date, self.end_date, self.city)
                    except TypeError:
                        payload = payload_func()

            if not payload:
                return {
                    'table_name': table_name,
                    'df': None,
                    'success': False,
                    'error': f"无法生成payload"
                }

            # 查询数据
            df = jxcx.get_table(payload, report_name=table_name)

            return {
                'table_name': table_name,
                'df': df,
                'success': not df.empty,
                'error': "查询结果为空" if df.empty else None
            }

        except Exception as e:
            return {
                'table_name': table_name,
                'df': None,
                'success': False,
                'error': str(e)
            }
    
    def download_source_tables(self):
        """并行下载8个数据源表（4线程）"""
        import threading
        thread_id = threading.current_thread().ident
        
        self._log("=" * 60)
        self._log(f"开始下载数据源表（4线程并行下载）线程ID: {thread_id}")
        self._log(f"时间范围: {self.start_date} 至 {self.end_date}")
        self._log(f"地市: {self.city}")
        self._log("=" * 60)

        success_count = 0
        failed_tables = []
        import time
        download_start = time.time()
        
        # 45G合成不是只查一张表：每个源表的字段、时间粒度和单位由其
        # payload 决定，先完整下载再在本地按 CGI/NCGI 做关联。payload
        # 函数历史上存在有参/无参两种签名，反射只负责兼容这层调用约定，
        # 不改变后端协议内容。
        # 这里固定四个 worker 是为了让八个独立查询并发执行；Session
        # 已在 _download_single_table 内按线程拆分，不能把主 Session
        # 直接作为共享客户端传入。
        with ThreadPoolExecutor(max_workers=4) as executor:
            # 提交所有下载任务；future 与表名的反向索引让主线程能在
            # as_completed 返回乱序结果时，仍准确记录对应源表。
            future_to_table = {
                executor.submit(self._download_single_table, table_name): table_name
                for table_name in SYNTHESIZE_45G_TABLES
            }
            
            self._log(f"已提交 {len(future_to_table)} 个下载任务，等待完成...")
            
            # 收集结果
            results = []
            for future in as_completed(future_to_table):
                table_name = future_to_table[future]
                task_start = time.time()
                result = future.result()
                task_elapsed = time.time() - task_start
                results.append(result)
                
                if result['success']:
                    self.data[result['table_name']] = result['df']
                    success_count += 1
                    
                    # 保存原始数据
                    filename = f"{result['table_name']}_{self.start_date}_{self.end_date}.xlsx"
                    filepath = self.raw_dir / filename
                    if not export_dataframe_streaming(result['df'], str(filepath), sheet_name='数据'):
                        raise RuntimeError(f"原始表导出失败: {result['table_name']}")
                    self._log(f"  ✅ [{result['table_name']}] 成功: {len(result['df'])} 行, 耗时: {task_elapsed:.1f}秒")
                else:
                    failed_tables.append((result['table_name'], result.get('error', '未知错误')))
                    self._log(f"  ❌ [{result['table_name']}] 失败: {result.get('error', '未知错误')}, 耗时: {task_elapsed:.1f}秒", 'warning')

        total_elapsed = time.time() - download_start
        self._log("-" * 60)
        self._log(f"数据下载完成: {success_count}/{len(SYNTHESIZE_45G_TABLES)} 成功, 总耗时: {total_elapsed:.1f}秒")

        if failed_tables:
            self._log(f"失败列表: {[t[0] for t in failed_tables]}", 'warning')

        return success_count >= 4  # 至少需要4个核心表；缺少较边缘的源表时，仍允许合成可用结果
    
    def _normalize_datetime(self, series):
        """标准化日期时间列"""
        def parse_date(val):
            if pd.isna(val):
                return pd.NaT
            if isinstance(val, str):
                try:
                    return pd.to_datetime(val)
                except:
                    return pd.NaT
            return val
        
        return series.apply(parse_date)
    
    def _load_5g_week_data(self):
        """加载并处理5G周容量数据"""
        table_name = '5G小区容量-周'
        if table_name not in self.data:
            return None
        
        df = self.data[table_name].copy()
        
        # NCGI去重（按第一条记录）
        # 注意：实际数据列名是大写 NCGI
        ncgi_col = None
        for c in ['NCGI', 'ncgi']:
            if c in df.columns:
                ncgi_col = c
                break
        
        if ncgi_col:
            df = df.drop_duplicates(subset=[ncgi_col], keep='first')
        
        return df
    
    def _load_5g_day_data(self):
        """加载并处理5G天容量数据"""
        table_name = '5G小区容量报表'
        if table_name not in self.data:
            return None
        
        df = self.data[table_name].copy()
        
        # 时间列标准化 - 注意：实际数据列名是中文 '记录开始时间'
        time_col = None
        for c in ['记录开始时间', 'starttime']:
            if c in df.columns:
                time_col = c
                df[c] = self._normalize_datetime(df[c])
                # 判断是否周末
                df['是否周末'] = df[c].dt.weekday >= 5
                break
        
        return df
    
    def _load_4g_week_data(self):
        """加载并处理4G周容量数据"""
        table_name = '重要场景-周'
        if table_name not in self.data:
            return None
        
        df = self.data[table_name].copy()
        
        # CGI去重 - 注意：实际数据列名是大写 CGI
        cgi_col = None
        for c in ['CGI', 'cgi']:
            if c in df.columns:
                cgi_col = c
                break
        
        if cgi_col:
            df = df.drop_duplicates(subset=[cgi_col], keep='first')
        
        return df
    
    def _load_4g_day_data(self):
        """加载并处理4G天容量数据"""
        table_name = '重要场景-天'
        if table_name not in self.data:
            return None
        
        df = self.data[table_name].copy()
        
        # 时间列标准化 - 注意：实际数据列名是中文 '记录开始时间'
        time_col = None
        for c in ['记录开始时间', 'starttime']:
            if c in df.columns:
                time_col = c
                df[c] = self._normalize_datetime(df[c])
                # 判断是否周末
                df['是否周末'] = df[c].dt.weekday >= 5
                break
        
        return df
    
    def _load_5g_mr_data(self):
        """加载并处理5G MR覆盖数据"""
        table_name = '5GMR覆盖-小区天'
        if table_name not in self.data:
            return None
        
        df = self.data[table_name].copy()
        return df
    
    def _load_4g_mr_data(self):
        """加载并处理4G MR覆盖数据"""
        table_name = '4GMR覆盖-小区天'
        if table_name not in self.data:
            return None
        
        df = self.data[table_name].copy()
        return df
    
    def _load_5g_kpi_data(self):
        """加载并处理5G KPI数据"""
        table_name = '5G小区性能KPI报表'
        if table_name not in self.data:
            return None
        
        df = self.data[table_name].copy()
        return df
    
    def _load_cog_coverage(self):
        """加载共站同覆盖映射表"""
        table_name = '共站同覆盖小区_4g_5g'
        if table_name not in self.data:
            return None
        
        df = self.data[table_name].copy()
        
        # CGI去重
        if 'cgi' in df.columns:
            df = df.drop_duplicates(subset=['cgi'], keep='first')
        
        return df
    
    def _safe_divide(self, numerator, denominator):
        """安全的除法运算"""
        if isinstance(denominator, (int, float)):
            if denominator == 0:
                return pd.Series([pd.NA] * len(numerator), index=numerator.index)
            return numerator / denominator
        else:
            denominator = denominator.replace(0, pd.NA)
            return numerator.div(denominator)
    
    def build_5g_table(self):
        """构建5G合成容量表。

        以5G周容量表为主键骨架，天表按 NCGI 聚合日均/忙时指标，MR 表
        聚合采样点和覆盖率，KPI 表补充 VoNR 话务量，最后使用 left join
        保留周表中的小区全集。天表的流量字段单位是 G，利用率字段通常是
        百分数数值（例如 20 表示20%）；这里保持源表单位，不在合成阶段
        额外乘除100，避免与后续阈值口径错位。
        """
        self._log("-" * 60)
        self._log("开始构建5G容量表")
        
        # 加载数据
        week_df = self._load_5g_week_data()
        day_df = self._load_5g_day_data()
        mr_df = self._load_5g_mr_data()
        kpi_df = self._load_5g_kpi_data()
        
        if week_df is None:
            self._log("5G周容量数据缺失，跳过5G表构建", 'warning')
            return None
        
        # 复制周表作为基础
        result = week_df.copy()
        
        # 查找NCGI列名 - 注意：实际数据列名是大写 NCGI
        ncgi_col = None
        for c in ['NCGI', 'ncgi']:
            if c in result.columns:
                ncgi_col = c
                break
        
        # 天数据不是简单追加：同一小区会有多天记录，先按 NCGI 聚合为
        # 一行。mean 用于日均流量、忙时利用率、PRB/CCE 和连接数等指标；
        # 忙时上下行流量仍按源表的 G 单位聚合，随后才相加得到总流量。
        day_ncgi_col = None
        for c in ['NCGI', 'ncgi']:
            if day_df is not None and c in day_df.columns:
                day_ncgi_col = c
                break
        
        if day_df is not None and day_ncgi_col:
            # 流量列
            traffic_col = None
            for col in ['日RLC层上下行总流量(G)', 'rlc_upoctudl']:
                if col in day_df.columns:
                    traffic_col = col
                    break
            
            # PRB利用率列 - 注意：5G天表列名是 '忙时小区PRB利用率'（无括号）
            util_col_5g = None
            for col in ['忙时小区PRB利用率', '忙时小区PRB利用率(%)', 'bh_cellprbrate']:
                if col in day_df.columns:
                    util_col_5g = col
                    break
            
            # 基础聚合
            agg_dict = {}
            if traffic_col:
                agg_dict['日均流量'] = (traffic_col, 'mean')
            if util_col_5g:
                agg_dict['自忙时利用率'] = (util_col_5g, 'mean')
            
            # PRB相关
            prb_ul_cols = ['忙时上行PRB平均利用率(%)', 'bh_prbassnrateul']
            prb_dl_cols = ['忙时下行PRB平均利用率(%)', 'bh_prbassnratedl']
            prb_ul = next((c for c in prb_ul_cols if c in day_df.columns), None)
            prb_dl = next((c for c in prb_dl_cols if c in day_df.columns), None)
            
            if prb_ul:
                agg_dict['自忙时上行PRB平均利用率'] = (prb_ul, 'mean')
            if prb_dl:
                agg_dict['自忙时下行PRB平均利用率'] = (prb_dl, 'mean')
            
            # CCE占用率
            cce_cols = ['忙时PDCCH信道CCE占用率(%)', 'bh_pdcchcceoccupancyrate']
            cce_col = next((c for c in cce_cols if c in day_df.columns), None)
            if cce_col:
                agg_dict['自忙时PDCCH信道CCE占用率'] = (cce_col, 'mean')
            
            # RRC连接
            rrc_max_cols = ['RRC连接最大数-忙时', 'bh_rrc_connmax']
            rrc_mean_cols = ['RRC连接平均数-忙时', 'bh_rrc_connmean']
            rrc_max = next((c for c in rrc_max_cols if c in day_df.columns), None)
            rrc_mean = next((c for c in rrc_mean_cols if c in day_df.columns), None)
            
            if rrc_max:
                agg_dict['自忙时RRC连接最大数'] = (rrc_max, 'mean')
            if rrc_mean:
                agg_dict['自忙时有效RRC连接平均数'] = (rrc_mean, 'mean')
            
            # 忙时流量
            bh_ul_cols = ['忙时RLC层上行业务字节数(G)', 'bh_rlc_upoctul']
            bh_dl_cols = ['忙时RLC层下行业务字节数(G)', 'bh_rlc_upoctdl']
            bh_ul = next((c for c in bh_ul_cols if c in day_df.columns), None)
            bh_dl = next((c for c in bh_dl_cols if c in day_df.columns), None)
            
            if bh_ul:
                agg_dict['自忙时上行流量'] = (bh_ul, 'mean')
            if bh_dl:
                agg_dict['自忙时下行流量'] = (bh_dl, 'mean')
            
            day_group = day_df.groupby(day_ncgi_col, dropna=False).agg(**agg_dict).reset_index()
            day_group = day_group.rename(columns={day_ncgi_col: ncgi_col})
            
            # 计算总流量
            if '自忙时上行流量' in day_group.columns and '自忙时下行流量' in day_group.columns:
                day_group['自忙时总流量'] = day_group['自忙时上行流量'].fillna(0) + day_group['自忙时下行流量'].fillna(0)
            
            # 5G 工作日/周末是同一份天表的两个切片，分别按 NCGI 求均值后
            # 回连到日聚合结果；缺少日期列时，加载阶段会提供全为 False
            # 的标记，因此不会把记录错误地归入周末。
            weekday_df = day_df[~day_df.get('是否周末', pd.Series([False]*len(day_df)))]
            weekend_df = day_df[day_df.get('是否周末', pd.Series([False]*len(day_df)))]

            if not weekday_df.empty and traffic_col:
                weekday_agg = {
                    '工作日自忙时利用率': (util_col_5g, 'mean') if util_col_5g else ('记录开始时间', 'count'),
                    '工作日日均流量': (traffic_col, 'mean'),
                }
                # 如果有PRB利用率，也聚合工作日的
                if prb_ul:
                    weekday_agg['工作日自忙时上行PRB平均利用率'] = (prb_ul, 'mean')
                weekday_group = weekday_df.groupby(day_ncgi_col, dropna=False).agg(**weekday_agg).reset_index()
                weekday_group = weekday_group.rename(columns={day_ncgi_col: ncgi_col})
                day_group = day_group.merge(weekday_group, on=ncgi_col, how='left')
            
            if not weekend_df.empty and traffic_col:
                weekend_agg = {
                    '周末自忙时利用率': (util_col_5g, 'mean') if util_col_5g else ('记录开始时间', 'count'),
                    '周末日均流量': (traffic_col, 'mean'),
                }
                if prb_ul:
                    weekend_agg['周末自忙时上行PRB平均利用率'] = (prb_ul, 'mean')
                weekend_group = weekend_df.groupby(day_ncgi_col, dropna=False).agg(**weekend_agg).reset_index()
                weekend_group = weekend_group.rename(columns={day_ncgi_col: ncgi_col})
                day_group = day_group.merge(weekend_group, on=ncgi_col, how='left')
            
            # 合并到结果
            result = result.merge(day_group, on=ncgi_col, how='left')
        
        # MR数据聚合
        # 注意：5G MR表的列名是 '小区NCGI'，不是 'NCGI'
        mr_ncgi_col = None
        for c in ['小区NCGI', 'NCGI', 'ncgi']:
            if mr_df is not None and c in mr_df.columns:
                mr_ncgi_col = c
                break
        
        if mr_df is not None and mr_ncgi_col:
            # 总采样点
            sample_col = None
            for c in ['移动RSRP采样的总采样点', 'nr_rsrp_count']:
                if c in mr_df.columns:
                    sample_col = c
                    break
            
            # 强覆盖采样点
            strong_col = None
            for c in ['移动RSRP采样强于-110采样点', 'nr_rsrp_gt_f110']:
                if c in mr_df.columns:
                    strong_col = c
                    break
            
            # 平均TA
            ta_col = None
            for c in ['移动平均TA(M)', 'mro_yd_ta_dist_avg']:
                if c in mr_df.columns:
                    ta_col = c
                    break
            
            # 5G MR 是采样记录级数据，不能按行直接拼接；这里按小区汇总，
            # 同时保留平均采样点、总采样点和强覆盖采样点，以便覆盖率
            # 使用“强于110采样点合计 / 总采样点合计”计算。平均TA的单位
            # 是米，导出时保持该物理单位，不与百分比字段混用。
            mr_agg = {}
            if sample_col:
                mr_agg['MRO移动总采样点'] = (sample_col, 'mean')
                mr_agg['MRO总采样点合计'] = (sample_col, 'sum')
            if strong_col:
                mr_agg['MRO强于110采样点合计'] = (strong_col, 'sum')
            if ta_col:
                mr_agg['平均TA米'] = (ta_col, 'mean')
            
            if mr_agg:
                mr_group = mr_df.groupby(mr_ncgi_col, dropna=False).agg(**mr_agg).reset_index()
                # 重命名分组列
                mr_group = mr_group.rename(columns={mr_ncgi_col: ncgi_col})
                
                # 计算覆盖率
                if 'MRO强于110采样点合计' in mr_group.columns and 'MRO总采样点合计' in mr_group.columns:
                    mr_group['MRO移动覆盖率'] = self._safe_divide(
                        mr_group['MRO强于110采样点合计'], 
                        mr_group['MRO总采样点合计']
                    )
                
                result = result.merge(mr_group, on=ncgi_col, how='left')
        
        # KPI数据聚合（VoNR话务量）
        # 注意：5G KPI表的列名是 'NCGI'
        kpi_ncgi_col = None
        for c in ['NCGI', 'ncgi']:
            if kpi_df is not None and c in kpi_df.columns:
                kpi_ncgi_col = c
                break
        
        if kpi_df is not None and kpi_ncgi_col:
            vonr_col = None
            for c in ['VoNR语音话务量', 'vonr_voice_traffic']:
                if c in kpi_df.columns:
                    vonr_col = c
                    break
            
            if vonr_col:
                kpi_group = kpi_df.groupby(kpi_ncgi_col, dropna=False).agg(
                    VoNR语音话务量=(vonr_col, 'mean')
                ).reset_index()
                kpi_group = kpi_group.rename(columns={kpi_ncgi_col: ncgi_col})
                result = result.merge(kpi_group, on=ncgi_col, how='left')
        
        # 计算流量系数和分类
        if '日均流量' in result.columns:
            avg_traffic = result['日均流量'].mean(skipna=True)
            if avg_traffic > 0:
                result['流量系数'] = self._safe_divide(result['日均流量'], avg_traffic)
                result['流量排名升序'] = result['日均流量'].rank(method='min', ascending=True)
                
                # 流量是否正常
                result['流量是否正常'] = pd.NA
                result.loc[result['流量系数'] < 0.2, '流量是否正常'] = '低流量系数小区'
                result.loc[(result['流量系数'] >= 0.2) & (result['流量系数'] < 3), '流量是否正常'] = '正常'
                result.loc[result['流量系数'] >= 3, '流量是否正常'] = '高流量系数小区'
                
                # 长尾小区分类
                tail_threshold = result['日均流量'].quantile(0.3)
                result['长尾小区'] = pd.NA
                
                is_na_traffic = result['日均流量'].isna()
                is_tail = (result['日均流量'] <= tail_threshold) & ~is_na_traffic
                is_zero = result['日均流量'] == 0
                if '自忙时利用率' in result.columns:
                    is_high_util = result['自忙时利用率'].notna() & (result['自忙时利用率'] > 20)
                else:
                    is_high_util = pd.Series([False] * len(result))
                
                result.loc[is_tail & is_zero, '长尾小区'] = '长尾具体原因待确认'
                result.loc[is_tail & ~is_zero & is_high_util, '长尾小区'] = '长尾待观察'
                result.loc[is_tail & ~is_zero & ~is_high_util, '长尾小区'] = '长尾需处理'
        
        # 负荷情况判定
        if '自忙时利用率' in result.columns:
            result['负荷情况'] = '正常'
            result.loc[result['自忙时利用率'].notna() & (result['自忙时利用率'] > 80), '负荷情况'] = '负荷高小区'
        
        # 扇区映射
        cog_df = self._load_cog_coverage()
        if cog_df is not None and 'cgi' in cog_df.columns:
            # 提取需要映射的列
            map_cols = ['cgi']
            for col in ['共站同覆盖名', '路测网格', '乡镇街道', '是否覆盖层', '小区所属区域']:
                if col in cog_df.columns:
                    map_cols.append(col)
            
            cog_subset = cog_df[map_cols].copy()
            
            # 映射扇区 - 使用实际的ncgi_col
            if '共站同覆盖名' in cog_subset.columns:
                sector_map = dict(zip(cog_subset['cgi'], cog_subset['共站同覆盖名']))
                result['扇区'] = result[ncgi_col].map(sector_map)
        
        # 字段重命名以匹配文档
        rename_map = {
            '使用频段': 'band',
            '一级场景': '场景V容量表',
            '站点名称': '物理站',
        }
        for old_name, new_name in rename_map.items():
            if old_name in result.columns and new_name not in result.columns:
                result = result.rename(columns={old_name: new_name})
        
        # 添加TYPE空字段
        if 'TYPE' not in result.columns:
            result['TYPE'] = pd.NA
        
        # 添加预警标识字段
        if '是否全省高负荷预警小区（集团口径）' not in result.columns:
            result['是否全省高负荷预警小区（集团口径）'] = pd.NA
        if '是否全省高负荷预警小区（省内口径）' not in result.columns:
            result['是否全省高负荷预警小区（省内口径）'] = pd.NA
        
        # 字段重排和输出
        result = self._reorder_5g_fields(result)
        
        self._log(f"5G容量表构建完成: {len(result)} 行")
        return result
    
    def _reorder_5g_fields(self, df):
        """重排5G表字段顺序"""
        # 扩展的优先级字段列表，包含实际数据中的列名
        priority_fields = [
            # 时间字段
            '记录开始时间', '记录结束时间',
            # 基础信息
            '地市', '网元状态', '小区名称', 'NCGI',
            '扇区', 'band', '场景V容量表', 'TYPE', '物理站',
            # 流量分析
            '流量是否正常', '负荷情况', '流量排名升序', '长尾小区', '流量系数', '日均流量',
            # 核心指标
            '自忙时利用率', 'VoNR语音话务量', '自忙时上行流量', '自忙时下行流量', '自忙时总流量',
            # 工作日/周末
            '工作日自忙时利用率', '工作日日均流量', '周末自忙时利用率', '周末日均流量',
            # PRB指标
            '自忙时上行PRB平均利用率', '自忙时下行PRB平均利用率', '自忙时PDCCH信道CCE占用率',
            # RRC指标
            '自忙时RRC连接最大数', '自忙时有效RRC连接平均数', '自忙时有效RRC连接最大数',
            # MR覆盖
            'MRO移动总采样点', 'MRO移动覆盖率', '平均TA米',
            # 预警标识
            '是否全省高负荷预警小区（集团口径）', '是否高负荷待扩容小区', '是否全省高负荷预警小区（省内口径）', '是否高负荷',
        ]
        
        # 获取存在的字段并按优先级排序
        existing = [f for f in priority_fields if f in df.columns]
        remaining = [c for c in df.columns if c not in priority_fields]
        ordered = existing + remaining
        
        return df[ordered]
    
    def build_4g_table(self):
        """构建4G合成容量表"""
        self._log("-" * 60)
        self._log("开始构建4G容量表")
        
        # 加载数据
        week_df = self._load_4g_week_data()
        day_df = self._load_4g_day_data()
        mr_df = self._load_4g_mr_data()
        
        if week_df is None:
            self._log("4G周容量数据缺失，跳过4G表构建", 'warning')
            return None
        
        # 复制周表作为基础
        result = week_df.copy()
        
        # 查找CGI列名 - 注意：实际数据列名是大写 CGI
        cgi_col = None
        for c in ['CGI', 'cgi']:
            if c in result.columns:
                cgi_col = c
                break
        
        # 查找day_df中的CGI列名
        day_cgi_col = None
        for c in ['CGI', 'cgi']:
            if day_df is not None and c in day_df.columns:
                day_cgi_col = c
                break
        
        # 天数据聚合
        if day_df is not None and day_cgi_col:
            # 流量列 - 注意：实际列名是 '日4G流量（GB）'
            traffic_col = None
            for col in ['日4G流量（GB）', 'upoctudl']:
                if col in day_df.columns:
                    traffic_col = col
                    break
            
            # 查找PRB相关列 - 注意：实际列名是 '日峰值上行PRB平均利用率' 和 '日峰值下行PRB平均利用率'
            # 但4G天表中是 '自忙时上行PRB平均利用率' 等
            prb_ul_cols = ['自忙时上行PRB平均利用率', '日峰值上行PRB平均利用率', 'bh_ul_prbuse_rate']
            prb_dl_cols = ['自忙时下行PRB平均利用率', '日峰值下行PRB平均利用率', 'bh_dl_prbuse_rate']
            prb_ul = next((c for c in prb_ul_cols if c in day_df.columns), None)
            prb_dl = next((c for c in prb_dl_cols if c in day_df.columns), None)
            
            # CCE占用率
            cce_cols = ['自忙时PDCCH信道CCE占用率', '日峰值PDCCH信道CCE占用率', 'bh_pdcchcceutilratio']
            cce_col = next((c for c in cce_cols if c in day_df.columns), None)
            
            # RRC连接
            rrc_max_cols = ['自忙时RRC连接最大数', 'bh_connmax']
            rrc_eff_max_cols = ['自忙时有效RRC连接最大数', 'bh_effectiveconnmax']
            rrc_mean_cols = ['自忙时有效RRC连接平均数', 'bh_effectiveconnmean']
            rrc_max = next((c for c in rrc_max_cols if c in day_df.columns), None)
            rrc_eff_max = next((c for c in rrc_eff_max_cols if c in day_df.columns), None)
            rrc_mean = next((c for c in rrc_mean_cols if c in day_df.columns), None)
            
            # 忙时流量
            bh_ul_cols = ['自忙时空口上行业务字节数', 'bh_upoctul']
            bh_dl_cols = ['自忙时空口下行业务字节数', 'bh_upoctdl']
            bh_ul = next((c for c in bh_ul_cols if c in day_df.columns), None)
            bh_dl = next((c for c in bh_dl_cols if c in day_df.columns), None)
            
            # 基础聚合
            agg_dict = {}
            if traffic_col:
                agg_dict['日均流量'] = (traffic_col, 'mean')
            
            # 计算自忙时利用率（上下行PRB最大值）
            if prb_ul and prb_dl:
                day_df['自忙时利用率_计算'] = day_df[[prb_ul, prb_dl]].max(axis=1)
                agg_dict['自忙时利用率'] = ('自忙时利用率_计算', 'mean')
            elif prb_ul:
                agg_dict['自忙时利用率'] = (prb_ul, 'mean')
            elif prb_dl:
                agg_dict['自忙时利用率'] = (prb_dl, 'mean')
            
            if prb_ul:
                agg_dict['自忙时上行PRB平均利用率'] = (prb_ul, 'mean')
            if prb_dl:
                agg_dict['自忙时下行PRB平均利用率'] = (prb_dl, 'mean')
            if cce_col:
                agg_dict['自忙时PDCCH信道CCE占用率'] = (cce_col, 'mean')
            if rrc_max:
                agg_dict['自忙时RRC连接最大数'] = (rrc_max, 'mean')
            if rrc_eff_max:
                agg_dict['自忙时有效RRC连接最大数'] = (rrc_eff_max, 'mean')
            if rrc_mean:
                agg_dict['自忙时有效RRC连接平均数'] = (rrc_mean, 'mean')
            if bh_ul:
                agg_dict['自忙时上行流量'] = (bh_ul, 'mean')
            if bh_dl:
                agg_dict['自忙时下行流量'] = (bh_dl, 'mean')
            
            day_group = day_df.groupby(day_cgi_col, dropna=False).agg(**agg_dict).reset_index()
            # 重命名分组列
            if day_cgi_col != cgi_col:
                day_group = day_group.rename(columns={day_cgi_col: cgi_col})
            
            # 计算总流量
            if '自忙时上行流量' in day_group.columns and '自忙时下行流量' in day_group.columns:
                day_group['自忙时总流量'] = day_group['自忙时上行流量'].fillna(0) + day_group['自忙时下行流量'].fillna(0)
            
            # 工作日/周末聚合
            weekday_df = day_df[~day_df.get('是否周末', pd.Series([False]*len(day_df)))]
            weekend_df = day_df[day_df.get('是否周末', pd.Series([False]*len(day_df)))]
            
            if not weekday_df.empty and traffic_col:
                weekday_group = weekday_df.groupby(day_cgi_col, dropna=False).agg(
                    工作日自忙时利用率=(prb_ul, 'mean') if prb_ul else ('记录开始时间', 'count'),
                    工作日日均流量=(traffic_col, 'mean'),
                ).reset_index()
                if day_cgi_col != cgi_col:
                    weekday_group = weekday_group.rename(columns={day_cgi_col: cgi_col})
                day_group = day_group.merge(weekday_group, on=cgi_col, how='left')
            
            if not weekend_df.empty and traffic_col:
                weekend_group = weekend_df.groupby(day_cgi_col, dropna=False).agg(
                    周末自忙时利用率=(prb_ul, 'mean') if prb_ul else ('记录开始时间', 'count'),
                    周末日均流量=(traffic_col, 'mean'),
                ).reset_index()
                if day_cgi_col != cgi_col:
                    weekend_group = weekend_group.rename(columns={day_cgi_col: cgi_col})
                day_group = day_group.merge(weekend_group, on=cgi_col, how='left')
            
            # 合并到结果
            result = result.merge(day_group, on=cgi_col, how='left')
        
        # MR数据聚合
        if mr_df is not None:
            mr_cgi_col = None
            for c in ['cgi', 'CGI', '小区CGI']:
                if c in mr_df.columns:
                    mr_cgi_col = c
                    break
            
            if mr_cgi_col:
                # 总采样点
                sample_col = None
                for c in ['MRO移动总采样点', 'mro_total_count']:
                    if c in mr_df.columns:
                        sample_col = c
                        break
                
                # 强覆盖采样点
                strong_col = None
                for c in ['MRO移动大于等于负110DBM的采样点数', 'mro_strong_count']:
                    if c in mr_df.columns:
                        strong_col = c
                        break
                
                # 平均TA
                ta_col = None
                for c in ['平均TA', 'mro_avg_ta']:
                    if c in mr_df.columns:
                        ta_col = c
                        break
                
                mr_agg = {}
                if sample_col:
                    mr_agg['MRO移动总采样点'] = (sample_col, 'mean')
                    mr_agg['MRO总采样点合计'] = (sample_col, 'sum')
                if strong_col:
                    mr_agg['MRO强于110采样点合计'] = (strong_col, 'sum')
                if ta_col:
                    mr_agg['平均TA米'] = (ta_col, 'mean')
                
                if mr_agg:
                    mr_group = mr_df.groupby(mr_cgi_col, dropna=False).agg(**mr_agg).reset_index()
                    
                    # 计算覆盖率
                    if 'MRO强于110采样点合计' in mr_group.columns and 'MRO总采样点合计' in mr_group.columns:
                        mr_group['MRO移动覆盖率'] = self._safe_divide(
                            mr_group['MRO强于110采样点合计'], 
                            mr_group['MRO总采样点合计']
                        )
                    
                    # 重命名mr_group的分组列，使其与result的CGI列名一致
                    # 4G MR表用的是小写'cgi'，但4G周表用的是大写'CGI'
                    if mr_cgi_col == 'cgi' and cgi_col == 'CGI':
                        mr_group = mr_group.rename(columns={'cgi': 'CGI'})
                    result = result.merge(mr_group, on=cgi_col, how='left')
        
        # 计算流量系数和分类
        if '日均流量' in result.columns:
            avg_traffic = result['日均流量'].mean(skipna=True)
            if avg_traffic > 0:
                result['流量系数'] = self._safe_divide(result['日均流量'], avg_traffic)
                result['流量排名升序'] = result['日均流量'].rank(method='min', ascending=True)
                
                # 流量是否正常
                result['流量是否正常'] = pd.NA
                result.loc[result['流量系数'] < 0.2, '流量是否正常'] = '低流量系数小区'
                result.loc[(result['流量系数'] >= 0.2) & (result['流量系数'] < 3), '流量是否正常'] = '正常'
                result.loc[result['流量系数'] >= 3, '流量是否正常'] = '高流量系数小区'
                
                # 长尾小区分类
                tail_threshold = result['日均流量'].quantile(0.3)
                result['长尾小区'] = pd.NA
                
                is_na_traffic = result['日均流量'].isna()
                is_tail = (result['日均流量'] <= tail_threshold) & ~is_na_traffic
                is_zero = result['日均流量'] == 0
                
                # 4G负荷判定（需要根据小区名称类型判断）
                name_col = None
                for c in ['cell_name', '小区名称']:
                    if c in result.columns:
                        name_col = c
                        break
                
                if name_col and '自忙时利用率' in result.columns:
                    name = result[name_col].fillna('')
                    util = result['自忙时利用率']
                    
                    # 判断小区类型
                    is_rdc_dc = name.str.contains('RDC|DC-|RGS|GS-', regex=True, na=False)
                    is_rd = name.str.contains('RD-', regex=True, na=False)
                    
                    # 场景化阈值判断
                    result['负荷情况'] = '正常'
                    result.loc[is_rdc_dc & (util > 90), '负荷情况'] = '负荷高小区'
                    result.loc[is_rd & (util > 70) & ~is_rdc_dc, '负荷情况'] = '负荷高小区'
                    result.loc[~is_rdc_dc & ~is_rd & (util > 50), '负荷情况'] = '负荷高小区'
                elif '自忙时利用率' in result.columns:
                    result['负荷情况'] = '正常'
                    result.loc[result['自忙时利用率'] > 50, '负荷情况'] = '负荷高小区'
        
        # 扇区映射（从共站同覆盖表）
        cog_df = self._load_cog_coverage()
        if cog_df is not None and 'cgi' in cog_df.columns:
            # 提取需要映射的列
            map_cols = ['cgi']
            for col in ['共站同覆盖名', '路测网格', '乡镇街道', '是否覆盖层', '小区所属区域']:
                if col in cog_df.columns:
                    map_cols.append(col)
            
            cog_subset = cog_df[map_cols].copy()
            
            # 映射扇区 - 使用实际的cgi_col
            if '共站同覆盖名' in cog_subset.columns:
                sector_map = dict(zip(cog_subset['cgi'], cog_subset['共站同覆盖名']))
                result['扇区'] = result[cgi_col].map(sector_map)
        
        # 字段重命名以匹配文档
        rename_map = {
            '所属地市': '地市',
            '使用频段': 'band',
            '场景': '场景V容量表',
            '所属站点名称': '物理站',
        }
        for old_name, new_name in rename_map.items():
            if old_name in result.columns and new_name not in result.columns:
                result = result.rename(columns={old_name: new_name})
        
        # 添加TYPE空字段
        if 'TYPE' not in result.columns:
            result['TYPE'] = pd.NA
        
        # 添加预警标识字段
        if '是否全省高负荷预警小区（集团口径）' not in result.columns:
            result['是否全省高负荷预警小区（集团口径）'] = pd.NA
        if '是否全省高负荷预警小区（省内口径）' not in result.columns:
            if '是否高流量预警小区' in result.columns:
                result['是否全省高负荷预警小区（省内口径）'] = result['是否高流量预警小区']
            else:
                result['是否全省高负荷预警小区（省内口径）'] = pd.NA
        
        # 字段重排和输出
        result = self._reorder_4g_fields(result)
        
        self._log(f"4G容量表构建完成: {len(result)} 行")
        return result
    
    def _reorder_4g_fields(self, df):
        """重排4G表字段顺序"""
        # 扩展的优先级字段列表，包含实际数据中的列名
        priority_fields = [
            # 时间字段
            '记录开始时间', '记录结束时间',
            # 基础信息
            '地市', '网元状态', '小区名称', 'CGI',
            '扇区', 'band', '场景V容量表', 'TYPE', '物理站',
            # 流量分析
            '流量是否正常', '负荷情况', '流量排名升序', '长尾小区', '流量系数', '日均流量',
            # 核心指标
            '自忙时利用率', 'VOLTE语音话务量', '自忙时上行流量', '自忙时下行流量', '自忙时总流量',
            # 工作日/周末
            '工作日自忙时利用率', '工作日日均流量', '周末自忙时利用率', '周末日均流量',
            # PRB指标
            '自忙时上行PRB平均利用率', '自忙时下行PRB平均利用率', '自忙时PDCCH信道CCE占用率',
            # RRC指标
            '自忙时RRC连接最大数', '自忙时有效RRC连接最大数', '自忙时有效RRC连接平均数',
            # MR覆盖
            'MRO移动总采样点', 'MRO移动覆盖率', '平均TA米',
            # 预警标识
            '是否全省高负荷预警小区（集团口径）', '是否高负荷待扩容小区', '是否全省高负荷预警小区（省内口径）',
        ]
        
        # 获取存在的字段并按优先级排序
        existing = [f for f in priority_fields if f in df.columns]
        remaining = [c for c in df.columns if c not in priority_fields]
        ordered = existing + remaining
        
        return df[ordered]
    
    def merge_45g_table(self, table_5g, table_4g):
        """合并45G总表"""
        self._log("-" * 60)
        self._log("开始合并45G总表")
        
        if table_5g is None and table_4g is None:
            self._log("5G和4G数据都为空，无法合并", 'warning')
            return None
        
        dfs = []
        
        # 处理5G数据
        if table_5g is not None and not table_5g.empty:
            df_5g = table_5g.copy()
            df_5g.insert(0, '网络制式', '5G')
            
            # NCGI -> CGI/NCGI (处理大小写)
            ncgi_col = None
            for c in ['NCGI', 'ncgi']:
                if c in df_5g.columns:
                    ncgi_col = c
                    break
            if ncgi_col:
                df_5g['CGI/NCGI'] = df_5g[ncgi_col]
                df_5g = df_5g.drop(columns=[ncgi_col])
            
            dfs.append(df_5g)
        
        # 处理4G数据
        if table_4g is not None and not table_4g.empty:
            df_4g = table_4g.copy()
            df_4g.insert(0, '网络制式', '4G')
            
            # CGI -> CGI/NCGI (处理大小写)
            cgi_col = None
            for c in ['CGI', 'cgi']:
                if c in df_4g.columns:
                    cgi_col = c
                    break
            if cgi_col:
                df_4g['CGI/NCGI'] = df_4g[cgi_col]
                df_4g = df_4g.drop(columns=[cgi_col])
            
            dfs.append(df_4g)
        
        if not dfs:
            return None
        
        # 合并
        merged = pd.concat(dfs, ignore_index=True)
        
        self._log(f"45G总表合并完成: {len(merged)} 行")
        return merged
    
    def save_results(self, table_5g, table_4g, table_45g):
        """保存所有结果"""
        self._log("-" * 60)
        self._log("保存结果文件")

        timestamp = f"{self.start_date.replace('-', '')}_{self.end_date.replace('-', '')}"

        # 保存5G表
        if table_5g is not None and not table_5g.empty:
            filename_5g = f"合成_容量表_5G_{timestamp}.xlsx"
            filepath_5g = self.merged_dir / filename_5g
            if not export_dataframe_streaming(table_5g, str(filepath_5g), sheet_name='数据'):
                raise RuntimeError(f"5G结果导出失败: {filename_5g}")
            self._log(f"已保存: {filename_5g}")

        # 保存4G表
        if table_4g is not None and not table_4g.empty:
            filename_4g = f"合成_容量表_4G_{timestamp}.xlsx"
            filepath_4g = self.merged_dir / filename_4g
            if not export_dataframe_streaming(table_4g, str(filepath_4g), sheet_name='数据'):
                raise RuntimeError(f"4G结果导出失败: {filename_4g}")
            self._log(f"已保存: {filename_4g}")

        # 保存45G总表
        if table_45g is not None and not table_45g.empty:
            filename_45g = f"容量表_45G_{timestamp}.xlsx"
            filepath_45g = self.merged_dir / filename_45g
            if not export_dataframe_streaming(table_45g, str(filepath_45g), sheet_name='数据'):
                raise RuntimeError(f"45G结果导出失败: {filename_45g}")
            self._log(f"已保存: {filename_45g}")
        
        self._log(f"结果已保存到: {self.output_dir}")
    
    def run(self):
        """执行完整的合成流程"""
        self._log("=" * 60)
        self._log(f"开始合成45G流量表")
        self._log(f"周范围: {self.start_date} 至 {self.end_date} (第{self.week_num}周)")
        self._log(f"地市: {self.city}")
        self._log("=" * 60)
        
        # 1. 下载数据源
        if not self.download_source_tables():
            self._log("数据下载失败，终止合成流程", 'error')
            return False
        
        # 2. 构建5G表
        table_5g = self.build_5g_table()
        
        # 3. 构建4G表
        table_4g = self.build_4g_table()
        
        # 4. 合并45G表
        table_45g = self.merge_45g_table(table_5g, table_4g)
        
        # 5. 保存结果
        self.save_results(table_5g, table_4g, table_45g)
        
        self._log("=" * 60)
        self._log("45G流量表合成完成！")
        self._log("=" * 60)
        
        return True


def synthesize_45g_flow_table(session, city, week_start_date, progress_callback=None):
    """合成45G流量表的主入口函数
    
    Args:
        session: 已登录的requests Session
        city: 地市列表，逗号分隔
        week_start_date: 周开始日期（周一），datetime对象
        progress_callback: 进度回调函数 callback(message)
        
    Returns:
        bool: 是否成功
    """
    builder = FlowTableBuilder(session, city, week_start_date, progress_callback)
    return builder.run()
