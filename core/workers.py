# -*- coding: utf-8 -*-
"""
查询工作流模块
从 main_window.py 提取的查询/导出工作线程，与 GUI 解耦。

所有 GUI 依赖通过构造函数注入（回调函数 + tkinter 变量），
worker 本身不直接操作任何 tkinter 组件。
"""
import copy
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd
import requests

from core.export import export_to_excel, normalize_excel_rows
from core.query import JXCXQuery
from gui.calculators import (
    add_4g_voice_calc_columns,
    add_4g_wanchenglv_calc_columns,
    add_5g_wanchenglv_calc_columns,
)
from gui.widgets import TableConfig
from utils.config import OUTPUT_DIR
from utils.constants import DEFAULT_THREAD_POOL_SIZE, DEFAULT_THREAD_POOL_SMALL
from utils.logger import ensure_dirs

logger = logging.getLogger(__name__)


class QueryWorker:
    """查询工作流（与 GUI 解耦，通过回调与主窗口通信）

    Args:
        session: requests.Session
        jxcx: JXCXQuery 实例
        log_func: 日志回调（线程安全，形如 log(msg, level)）
        progress_func: 进度回调（形如 update_progress(current, total, detail)）
        after_func: 主线程调度回调（形如 root.after(ms, func, *args)）
        field_mode_var: tkinter.StringVar，'hardcode' 或 'dynamic'
        custom_fields_var: tkinter.BooleanVar，是否启用自定义字段
        selected_fields: dict，{table_name: [field_keys]}
        multi_day_var: tkinter.BooleanVar，是否按日查询
        multi_day_per_sheet_var: tkinter.BooleanVar，是否按日分Sheet
        multi_day_per_city_var: tkinter.BooleanVar，是否按日+按地市
        single_city_parallel_var: tkinter.BooleanVar，是否单地市多线程
    """

    def __init__(self, session, jxcx, log_func, progress_func, after_func,
                 field_mode_var, custom_fields_var, selected_fields,
                 multi_day_var, multi_day_per_sheet_var, multi_day_per_city_var,
                 single_city_parallel_var):
        self.session = session
        self.jxcx = jxcx
        self.log = log_func
        self._update_progress = progress_func
        self._after = after_func
        self.field_mode_var = field_mode_var
        self.custom_fields_var = custom_fields_var
        self.selected_fields = selected_fields
        self.multi_day_var = multi_day_var
        self.multi_day_per_sheet_var = multi_day_per_sheet_var
        self.multi_day_per_city_var = multi_day_per_city_var
        self.single_city_parallel_var = single_city_parallel_var

    def _make_thread_query(self):
        """为线程创建独立 Session 和 JXCXQuery，避免共享连接与缓存状态。"""
        thread_session = requests.Session()
        for cookie in self.session.cookies:
            thread_session.cookies.set_cookie(cookie)
        for attr in ('verify', 'trust_env', 'headers', 'auth', 'proxies', 'params', 'cert'):
            if hasattr(self.session, attr):
                setattr(thread_session, attr, copy.copy(getattr(self.session, attr)))
        thread_query = JXCXQuery(thread_session)
        thread_query.enabled = self.jxcx.enabled
        # 让独立查询实例轮询主查询的取消标志
        thread_query.is_cancelled = self.jxcx.is_cancelled
        return thread_query

    # ==================== 主查询工作流 ====================

    def query_worker(self, table_names, start_date, end_date, city,
                     on_complete=None, on_failed=None):
        try:
            self._query_worker_impl(
                table_names, start_date, end_date, city,
                on_complete=on_complete, on_failed=on_failed
            )
        except Exception as exc:
            logger.exception("查询工作流失败")
            self.log(f"查询失败: {exc}", "ERROR")
            if on_failed:
                self._after(0, on_failed)

    def _query_worker_impl(self, table_names, start_date, end_date, city,
                           on_complete=None, on_failed=None):
        """主查询工作流（原 NqiToolGUI._query_worker）。

        先快照 Tkinter 变量，再按模式优先级分流：单地市多表并行、4G
        语音联合查询、硬编码 payload、工参 table 流程和动态字段流程。
        按日、按日分 Sheet、按日+按地市是后续导出分支；它们共享取消
        标志，但不会直接操作 Tkinter 控件。所有完成/失败通知都通过
        ``after_func`` 投递回主线程。

        Args:
            table_names: 要查询的表名列表。
            start_date: 开始日期。
            end_date: 结束日期。
            city: 地市字符串。
            on_complete: 完成回调（将在主线程执行）。
            on_failed: 失败回调（将在主线程执行）。
        """
        total_tables = len(table_names)
        def _snapshot(value, default):
            return value.get() if value is not None else default

        multi_day = _snapshot(self.multi_day_var, False)
        multi_day_per_sheet = _snapshot(self.multi_day_per_sheet_var, False)
        multi_day_per_city = _snapshot(self.multi_day_per_city_var, False)
        single_city_parallel = _snapshot(self.single_city_parallel_var, False)
        self._use_hardcode_fields = _snapshot(self.field_mode_var, 'hardcode') == 'hardcode'
        self._custom_fields_enabled = _snapshot(self.custom_fields_var, False)

        self.log("当前配置来源: 硬编码模式（YAML配置已禁用）", "INFO")

        selected_city_list = [item.strip() for item in city.split(',') if item.strip()] if city else []
        should_parallel_tables = (
            single_city_parallel
            and not multi_day
            and len(selected_city_list) == 1
            and len(table_names) > 1
        )

        if should_parallel_tables:
            if self.jxcx.is_cancelled():
                self.log("已取消查询，跳过并行提取", "WARNING")
                self._after(0, on_complete)
                return
            self.log(f"单地市多线程模式已启用: {selected_city_list[0]}，共 {len(table_names)} 个表", "INFO")
            self.query_tables_parallel(table_names, start_date, end_date, selected_city_list[0])
            self._after(0, on_complete)
            return

        for idx, table_name in enumerate(table_names):
            if self.jxcx.is_cancelled():
                self.log("已取消查询，停止后续报表", "WARNING")
                break

            self.log(f"正在查询: {table_name}", "INFO")
            self._update_progress(idx, total_tables, f"正在查询: {table_name}")
            table_config = TableConfig.get_table_config(table_name)
            if not table_config:
                self.log(f"未找到表配置: {table_name}", "ERROR")
                continue

            self.jxcx.enter_jxcx()

            # 4G语音小区：分别查询VoLTE和EPSFB表后合并
            is_4g_voice = table_config.get('is_4g_voice', False)
            if is_4g_voice:
                self.log("4G语音小区报表：VoLTE + EPSFB 联合查询", "INFO")
                self.query_4g_voice_table(
                    table_config, start_date, end_date, city,
                    multi_day, multi_day_per_sheet, multi_day_per_city
                )
                self.log(f"查询完成: {table_name}", "SUCCESS")
                continue

            # 硬编码payload函数
            payload_func = table_config.get('payload_func')

            if payload_func:
                self._handle_payload_func(
                    table_config, payload_func, table_name, city,
                    start_date, end_date, idx, total_tables,
                    multi_day, multi_day_per_sheet, multi_day_per_city
                )
                self.log(f"查询完成: {table_name}", "SUCCESS")
                continue

            # 动态获取字段模式
            self._handle_dynamic_fields(
                table_config, table_name, city, start_date, end_date,
                idx, total_tables, multi_day, multi_day_per_sheet, multi_day_per_city
            )

        self._after(0, on_complete)

    # ==================== 硬编码 payload 分支 ====================

    def _handle_payload_func(self, table_config, payload_func, table_name, city,
                             start_date, end_date, idx, total_tables,
                             multi_day, multi_day_per_sheet, multi_day_per_city):
        """处理有 payload_func 的表"""
        payload_template = payload_func()
        if payload_template and payload_template.get('__gongcan__'):
            self._handle_gongcan(
                table_config, payload_template, table_name, city
            )
            return

        # 按日查询模式
        if multi_day:
            self._handle_multi_day_payload_func(
                payload_func, table_name, city, start_date, end_date,
                idx, total_tables, multi_day_per_sheet, multi_day_per_city, table_config
            )
            return

        # 普通模式：按日期范围查询
        self.log(f"使用硬编码payload模板: {table_name}", "INFO")
        self.log(f"  [调试] 查询日期范围: {start_date} 至 {end_date}", "INFO")
        payload = payload_func(start_date, end_date, city)

        if payload:
            for cond in payload.get('where', []):
                if 'starttime' in cond.get('feild', ''):
                    self.log(f"  [调试] 日期条件: {cond.get('feild')} {cond.get('symbol')} {cond.get('val')}", "INFO")

            df = self.jxcx.get_table(payload, report_name=table_name)
            if not df.empty:
                calc_columns = table_config.get('calc_columns', [])
                if calc_columns:
                    self.log(f"[计算列] 开始为 {table_name} 添加计算列: {calc_columns}", "INFO")
                    try:
                        if '4G全程完好率' in table_name:
                            df = add_4g_wanchenglv_calc_columns(df, log_func=self.log)
                        elif '5G全程完好率' in table_name:
                            df = add_5g_wanchenglv_calc_columns(df, log_func=self.log)
                        self.log(f"[计算列] {table_name} 计算列添加完成", "SUCCESS")
                    except Exception as e:
                        self.log(f"[计算列] {table_name} 计算列添加异常: {e}", "ERROR")

                filename = f"{table_name}_{start_date}_{end_date}.xlsx"
                filepath = export_to_excel(df, filename, table_name)
                if filepath:
                    self.log(f"数据已导出到: {os.path.basename(filepath)}", "SUCCESS")
                else:
                    self.log(f"导出失败: {table_name}", "ERROR")
            else:
                self.log(f"查询结果为空: {table_name}", "WARNING")

    def _handle_gongcan(self, table_config, payload_template, table_name, city):
        """处理工参报表"""
        self.log("工参报表: 使用table类型API", "INFO")
        conditions = table_config.get('default_conditions', []).copy()
        if city:
            conditions.append({'field': 'city', 'operator': 'in', 'value': city})

        gongcan_payload = self.jxcx.build_payload_from_config(
            payload_template.get('table_key'),
            payload_template.get('fieldtype'),
            conditions,
            payload_template.get('api_type', 'table'),
            dimension_override={
                'geographicdimension': payload_template.get('geographicdimension', ''),
                'timedimension': payload_template.get('timedimension', ''),
                'enodebField': payload_template.get('enodebField', ''),
                'cgiField': payload_template.get('cgiField', ''),
                'timeField': payload_template.get('timeField', ''),
                'cellField': payload_template.get('cellField', ''),
                'cityField': payload_template.get('cityField', '')
            }
        )
        if gongcan_payload:
            df = self.jxcx.get_table(gongcan_payload, report_name=table_name)
            if not df.empty:
                filename = f"{table_name}.xlsx"
                filepath = export_to_excel(df, filename, table_name)
                if filepath:
                    self.log(f"数据已导出到: {os.path.basename(filepath)}", "SUCCESS")
                else:
                    self.log(f"导出失败: {table_name}", "ERROR")
            else:
                self.log(f"查询结果为空: {table_name}", "WARNING")

    def _handle_multi_day_payload_func(self, payload_func, table_name, city,
                                       start_date, end_date, idx, total_tables,
                                       multi_day_per_sheet, multi_day_per_city, table_config):
        """处理按日查询模式（有 payload_func 的表）"""
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        dates = []
        while current_date <= end_datetime:
            dates.append(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)

        total_days = len(dates)
        selected_city_list = [item.strip() for item in city.split(',') if item.strip()] if city else []
        should_split_by_city = multi_day_per_city and len(selected_city_list) >= 1
        query_cities = selected_city_list if should_split_by_city else ([city] if city else [])

        tasks = []
        for query_date in dates:
            for query_city in query_cities:
                tasks.append((query_date, query_city, query_city or '全部地市'))

        total_tasks = len(tasks)
        self.log(f"按日查询模式: 共 {total_tasks} 个任务 ({total_days} 天 x {len(query_cities)} 地市)", "INFO")
        if should_split_by_city:
            self.log(f"按日+按地市导出模式: 共 {len(query_cities)} 个地市", "INFO")

        calc_columns = table_config.get('calc_columns', [])
        add_calc = bool(calc_columns)
        all_dfs = []
        city_day_dfs = []

        def _query_single_task(task_data):
            if self.jxcx.is_cancelled():
                return None, {'cancelled': True}
            q_date, q_city, q_city_label = task_data
            try:
                payload = payload_func(q_date, q_date, q_city)
                if not payload:
                    return None, None
                thread_query = self._make_thread_query()
                df = thread_query.get_table(payload, report_name=table_name)
                if df.empty:
                    return None, None
                if add_calc:
                    if '4G全程完好率' in table_name:
                        df = add_4g_wanchenglv_calc_columns(df, log_func=self.log)
                    elif '5G全程完好率' in table_name:
                        df = add_5g_wanchenglv_calc_columns(df, log_func=self.log)
                return q_date, q_city_label, df
            except Exception as e:
                return None, {'date': q_date, 'city': q_city_label, 'error': str(e)}

        completed_tasks = 0
        executor = ThreadPoolExecutor(max_workers=min(DEFAULT_THREAD_POOL_SIZE, total_tasks))
        futures = {executor.submit(_query_single_task, task): task for task in tasks}
        try:
            for future in as_completed(futures):
                if self.jxcx.is_cancelled():
                    self.log("按日查询收到取消请求，取消尚未开始的任务", "WARNING")
                    break
                result = future.result()
                completed_tasks += 1
                done_pct = completed_tasks / total_tasks
                self._after(0, lambda p=done_pct, t=completed_tasks, idx=idx, tt=total_tables, tn=table_name:
                            self._update_progress(
                                idx + p / tt, tt,
                                f"查询 {tn} [{t}/{total_tasks}]"))
                if result[0] is not None:
                    q_date, q_city_label, df = result
                    if should_split_by_city:
                        city_day_dfs.append((f"{q_date.replace('-', '')}_{q_city_label}", df))
                        city_filename = f"{table_name}_{q_date}_{q_city_label}.xlsx"
                        city_filepath = export_to_excel(df, city_filename, table_name)
                        if city_filepath:
                            self._after(0, lambda fp=city_filepath, cnt=len(df), dt=q_date, cl=q_city_label:
                                        self.log(f"  {dt} {cl}: {cnt} 条数据 -> {os.path.basename(fp)}", "SUCCESS"))
                    elif multi_day_per_sheet:
                        all_dfs.append((q_date.replace('-', ''), df))
                    else:
                        all_dfs.append(df)
                        day_filename = f"{table_name}_{q_date}.xlsx"
                        day_filepath = export_to_excel(df, day_filename, table_name)
                        if day_filepath:
                            self._after(0, lambda fp=day_filepath, cnt=len(df), dt=q_date:
                                        self.log(f"  {dt}: {cnt} 条数据 -> {os.path.basename(fp)}", "SUCCESS"))
                elif result[1] is not None:
                    err = result[1]
                    self._after(0, lambda e=err:
                                self.log(f"  查询异常 [{e['date']} {e['city']}]: {e['error']}", "ERROR"))

        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if should_split_by_city and city_day_dfs:
            self.log(f"按日+按地市导出完成: 共导出 {len(city_day_dfs)} 个文件", "SUCCESS")

        if multi_day_per_sheet and all_dfs:
            day_filename = f"{table_name}_{start_date}_{end_date}.xlsx"
            self.export_multi_sheet(day_filename, all_dfs, table_name)
            self.log(f"按日分Sheet导出完成: {day_filename}", "SUCCESS")

        if not should_split_by_city and not multi_day_per_sheet and all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            day_filename = f"{table_name}_{start_date}_{end_date}.xlsx"
            combined_filepath = export_to_excel(combined_df, day_filename, table_name)
            if combined_filepath:
                self.log(f"按日查询导出完成: {os.path.basename(combined_filepath)} ({len(combined_df)} 条)", "SUCCESS")

        if not all_dfs and not city_day_dfs:
            self.log(f"查询结果为空: {table_name}", "WARNING")

    # ==================== 动态获取字段分支 ====================

    def _handle_dynamic_fields(self, table_config, table_name, city,
                               start_date, end_date, idx, total_tables,
                               multi_day, multi_day_per_sheet, multi_day_per_city):
        """处理动态获取字段模式的表"""
        dimension = table_config.get('dimension', {})
        use_hardcode_fields = self._use_hardcode_fields
        fields = table_config.get('fields', None) if use_hardcode_fields else None
        if use_hardcode_fields and fields:
            self.log(f"使用硬编码字段配置 (共 {len(fields)} 个字段)", "INFO")
        elif use_hardcode_fields:
            self.log("使用硬编码模式但未找到预定义字段，将动态获取", "WARNING")
        else:
            self.log("使用动态字段获取模式", "INFO")
        is_gongcan = table_config.get('is_gongcan', False)
        is_4g_voice = table_config.get('is_4g_voice', False)

        if is_4g_voice:
            self.log("4G语音小区报表：VoLTE + EPSFB 联合查询", "INFO")
            self.query_4g_voice_table(
                table_config, start_date, end_date, city,
                multi_day, multi_day_per_sheet, multi_day_per_city
            )
            self.log(f"查询完成: {table_name}", "SUCCESS")
            return

        if is_gongcan:
            conditions = table_config.get('default_conditions', []).copy()
            if city:
                conditions.append({'field': 'city', 'operator': 'in', 'value': city})
            payload = self.jxcx.build_payload_from_config(
                table_config['table_key'],
                table_config['fieldtype'],
                conditions,
                table_config['api_type'],
                dimension_override=dimension if dimension else None,
                fields_override=fields,
                table_name=table_config.get('table_name'),
                table_params=table_config.get('tableParams'),
                indexcount=table_config.get('indexcount', 0)
            )
            if payload:
                df = self.jxcx.get_table(payload, report_name=table_name)
                if not df.empty:
                    df = self.apply_custom_fields(df, table_name)
                    filename = f"{table_name}_{start_date}_{end_date}.xlsx"
                    filepath = export_to_excel(df, filename, table_name)
                    if filepath:
                        self.log(f"数据已导出到: {os.path.basename(filepath)}", "SUCCESS")
                    else:
                        self.log(f"导出失败: {table_name}", "ERROR")
                else:
                    self.log(f"查询结果为空: {table_name}", "WARNING")
            return

        # 非工参报表：按日查询
        if multi_day:
            self._handle_multi_day_dynamic(
                table_config, table_name, city, start_date, end_date,
                idx, total_tables, multi_day_per_sheet, multi_day_per_city,
                dimension, fields
            )
            return

        # 普通模式：按日期范围查询
        conditions = table_config.get('default_conditions', []).copy()
        conditions.append({'field': 'starttime', 'operator': '>=', 'value': start_date})
        conditions.append({'field': 'starttime', 'operator': '<=', 'value': end_date})
        if city:
            conditions.append({'field': 'city', 'operator': 'in', 'value': city})

        payload = self.jxcx.build_payload_from_config(
            table_config['table_key'],
            table_config['fieldtype'],
            conditions,
            table_config['api_type'],
            dimension_override=dimension if dimension else None,
            fields_override=fields,
            table_name=table_config.get('table_name'),
            table_params=table_config.get('tableParams'),
            indexcount=table_config.get('indexcount', 0)
        )

        if payload:
            df = self.jxcx.get_table(payload, report_name=table_name)
            if not df.empty:
                df = self.apply_custom_fields(df, table_name)
                filename = f"{table_name}_{start_date}_{end_date}.xlsx"
                filepath = export_to_excel(df, filename, table_name)
                if filepath:
                    self.log(f"数据已导出到: {os.path.basename(filepath)}", "SUCCESS")
                else:
                    self.log(f"导出失败: {table_name}", "ERROR")
            else:
                self.log(f"查询结果为空: {table_name}", "WARNING")

    def _handle_multi_day_dynamic(self, table_config, table_name, city,
                                  start_date, end_date, idx, total_tables,
                                  multi_day_per_sheet, multi_day_per_city,
                                  dimension, fields):
        """处理按日查询模式（动态获取字段）"""
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        dates = []
        while current_date <= end_datetime:
            dates.append(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)

        total_days = len(dates)
        selected_city_list = [item.strip() for item in city.split(',') if item.strip()] if city else []
        should_split_by_city = multi_day_per_city and len(selected_city_list) >= 1
        query_cities = selected_city_list if should_split_by_city else ([city] if city else [])

        tasks = []
        for query_date in dates:
            for query_city in query_cities:
                tasks.append((query_date, query_city, query_city or '全部地市'))

        total_tasks = len(tasks)
        self.log(f"按日查询模式: 共 {total_tasks} 个任务 ({total_days} 天 x {len(query_cities)} 地市)", "INFO")
        if should_split_by_city:
            self.log(f"按日+按地市导出模式: 共 {len(query_cities)} 个地市", "INFO")

        all_dfs = []
        city_day_dfs = []

        def _query_normal_task(task_data):
            if self.jxcx.is_cancelled():
                return None, {'cancelled': True}
            q_date, q_city, q_city_label = task_data
            try:
                conditions = table_config.get('default_conditions', []).copy()
                conditions.append({'field': 'starttime', 'operator': '>=', 'value': q_date})
                conditions.append({'field': 'starttime', 'operator': '<=', 'value': q_date})
                if q_city:
                    conditions.append({'field': 'city', 'operator': 'in', 'value': q_city})
                thread_query = self._make_thread_query()
                payload = thread_query.build_payload_from_config(
                    table_config['table_key'],
                    table_config['fieldtype'],
                    conditions,
                    table_config['api_type'],
                    dimension_override=dimension if dimension else None,
                    fields_override=fields,
                    table_name=table_config.get('table_name'),
                    table_params=table_config.get('tableParams'),
                    indexcount=table_config.get('indexcount', 0)
                )
                if not payload:
                    return None, None
                df = thread_query.get_table(payload, report_name=table_name)
                if df.empty:
                    return None, None
                return q_date, q_city_label, df
            except Exception as e:
                return None, {'date': q_date, 'city': q_city_label, 'error': str(e)}

        completed_tasks = 0
        executor = ThreadPoolExecutor(max_workers=min(DEFAULT_THREAD_POOL_SIZE, total_tasks))
        futures = {executor.submit(_query_normal_task, task): task for task in tasks}
        try:
            for future in as_completed(futures):
                if self.jxcx.is_cancelled():
                    self.log("按日查询收到取消请求，取消尚未开始的任务", "WARNING")
                    break
                result = future.result()
                completed_tasks += 1
                done_pct = completed_tasks / total_tasks
                self._after(0, lambda p=done_pct, t=completed_tasks, idx=idx, tt=total_tables, tn=table_name:
                            self._update_progress(
                                idx + p / tt, tt,
                                f"查询 {tn} [{t}/{total_tasks}]"))
                if result[0] is not None:
                    q_date, q_city_label, df = result
                    if should_split_by_city:
                        city_day_dfs.append((f"{q_date.replace('-', '')}_{q_city_label}", df))
                        city_filename = f"{table_name}_{q_date}_{q_city_label}.xlsx"
                        city_filepath = export_to_excel(df, city_filename, table_name)
                        if city_filepath:
                            self._after(0, lambda fp=city_filepath, cnt=len(df), dt=q_date, cl=q_city_label:
                                        self.log(f"  {dt} {cl}: {cnt} 条数据 -> {os.path.basename(fp)}", "SUCCESS"))
                    elif multi_day_per_sheet:
                        all_dfs.append((q_date.replace('-', ''), df))
                    else:
                        all_dfs.append(df)
                        day_filename = f"{table_name}_{q_date}.xlsx"
                        day_filepath = export_to_excel(df, day_filename, table_name)
                        if day_filepath:
                            self._after(0, lambda fp=day_filepath, cnt=len(df), dt=q_date:
                                        self.log(f"  {dt}: {cnt} 条数据 -> {os.path.basename(fp)}", "SUCCESS"))
                elif result[1] is not None:
                    err = result[1]
                    self._after(0, lambda e=err:
                                self.log(f"  查询异常 [{e['date']} {e['city']}]: {e['error']}", "ERROR"))

        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if should_split_by_city and city_day_dfs:
            self.log(f"按日+按地市导出完成: 共导出 {len(city_day_dfs)} 个文件", "SUCCESS")

        if multi_day_per_sheet and all_dfs:
            day_filename = f"{table_name}_{start_date}_{end_date}.xlsx"
            self.export_multi_sheet(day_filename, all_dfs, table_name)
            self.log(f"按日分Sheet导出完成: {day_filename}", "SUCCESS")

        if not should_split_by_city and not multi_day_per_sheet and all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            day_filename = f"{table_name}_{start_date}_{end_date}.xlsx"
            combined_filepath = export_to_excel(combined_df, day_filename, table_name)
            if combined_filepath:
                self.log(f"按日查询导出完成: {os.path.basename(combined_filepath)} ({len(combined_df)} 条)", "SUCCESS")

        if not all_dfs and not city_day_dfs:
            self.log(f"查询结果为空: {table_name}", "WARNING")

    # ==================== 并行查询 ====================

    def query_tables_parallel(self, table_names, start_date, end_date, city):
        """单地市多表并行查询（原 NqiToolGUI._query_tables_parallel）

        使用主线程预读取的快照，避免子线程访问 tkinter 变量。
        """
        use_hardcode_fields = self._use_hardcode_fields
        custom_fields_enabled = self._custom_fields_enabled
        selected_fields_snapshot = {
            k: list(v) for k, v in getattr(self, 'selected_fields', {}).items()
        }

        def _run_single_table(table_index, table_name):
            if self.jxcx.is_cancelled():
                return {"table": table_name, "warning": "查询已被取消，跳过"}
            try:
                query = self._make_thread_query()
                query.enter_jxcx()
                table_config = TableConfig.get_table_config(table_name)
                if not table_config:
                    return {"table": table_name, "error": f"未找到表配置: {table_name}"}

                payload_func = table_config.get('payload_func')
                dimension = table_config.get('dimension', {})
                fields = table_config.get('fields', None) if use_hardcode_fields else None
                is_gongcan = table_config.get('is_gongcan', False)
                is_4g_voice = table_config.get('is_4g_voice', False)

                if is_4g_voice:
                    return {"table": table_name, "error": "4G语音小区暂不支持单地市多表并行，请单独提取"}

                if payload_func:
                    payload_template = payload_func()
                    if payload_template and payload_template.get('__gongcan__'):
                        conditions = table_config.get('default_conditions', []).copy()
                        if city:
                            conditions.append({'field': 'city', 'operator': 'in', 'value': city})
                        payload = query.build_payload_from_config(
                            payload_template.get('table_key'),
                            payload_template.get('fieldtype'),
                            conditions,
                            payload_template.get('api_type', 'table'),
                            dimension_override={
                                'geographicdimension': payload_template.get('geographicdimension', ''),
                                'timedimension': payload_template.get('timedimension', ''),
                                'enodebField': payload_template.get('enodebField', ''),
                                'cgiField': payload_template.get('cgiField', ''),
                                'timeField': payload_template.get('timeField', ''),
                                'cellField': payload_template.get('cellField', ''),
                                'cityField': payload_template.get('cityField', '')
                            }
                        )
                    else:
                        payload = payload_func(start_date, end_date, city)
                else:
                    conditions = table_config.get('default_conditions', []).copy()
                    conditions.append({'field': 'starttime', 'operator': '>=', 'value': start_date})
                    conditions.append({'field': 'starttime', 'operator': '<=', 'value': end_date})
                    if city:
                        conditions.append({'field': 'city', 'operator': 'in', 'value': city})
                    payload = query.build_payload_from_config(
                        table_config['table_key'],
                        table_config['fieldtype'],
                        conditions,
                        table_config['api_type'],
                        dimension_override=dimension if dimension else None,
                        fields_override=fields,
                        table_name=table_config.get('table_name'),
                        table_params=table_config.get('tableParams'),
                        indexcount=table_config.get('indexcount', 0)
                    )

                if not payload:
                    return {"table": table_name, "warning": "未生成查询条件"}

                df = query.get_table(payload, report_name=table_name)
                if df.empty:
                    return {"table": table_name, "warning": "查询结果为空"}

                calc_columns = table_config.get('calc_columns', [])
                if calc_columns:
                    if '4G全程完好率' in table_name:
                        df = add_4g_wanchenglv_calc_columns(df, log_func=self.log)
                    elif '5G全程完好率' in table_name:
                        df = add_5g_wanchenglv_calc_columns(df, log_func=self.log)

                # 自定义字段：使用线程安全快照
                if custom_fields_enabled and table_name in selected_fields_snapshot:
                    selected_keys = selected_fields_snapshot[table_name]
                    available = [col for col in df.columns if col in selected_keys]
                    if available:
                        df = df[available]

                filename = f"{table_name}_{start_date}_{end_date}.xlsx"
                filepath = export_to_excel(df, filename, table_name)
                return {
                    "table": table_name,
                    "filepath": filepath,
                    "rows": len(df),
                    "index": table_index,
                }
            except Exception as e:
                return {"table": table_name, "error": str(e)}

        completed = 0
        executor = ThreadPoolExecutor(max_workers=min(DEFAULT_THREAD_POOL_SMALL, len(table_names)))
        futures = {
            executor.submit(_run_single_table, table_index, table_name): (table_index, table_name)
            for table_index, table_name in enumerate(table_names)
        }
        try:
            for future in as_completed(futures):
                if self.jxcx.is_cancelled():
                    self.log("并行查询收到取消请求，取消尚未开始的任务", "WARNING")
                    break
                result = future.result()
                completed += 1
                self._after(0, lambda done=completed, total=len(table_names):
                            self._update_progress(done, total, f"多线程提取 [{done}/{total}]"))

                if result.get("error"):
                    self._after(0, lambda msg=result["error"], table=result["table"]:
                                self.log(f"{table}: {msg}", "ERROR"))
                elif result.get("warning"):
                    self._after(0, lambda msg=result["warning"], table=result["table"]:
                                self.log(f"{table}: {msg}", "WARNING"))
                elif result.get("filepath"):
                    self._after(0, lambda path=result["filepath"], rows=result["rows"], table=result["table"]:
                                self.log(f"{table}: {rows} 条数据 -> {os.path.basename(path)}", "SUCCESS"))
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    # ==================== 4G语音小区 ====================

    def query_4g_voice_table(self, table_config, start_date, end_date, city,
                              multi_day, multi_day_per_sheet, multi_day_per_city):
        """查询4G语音小区报表（VoLTE + EPSFB 联合查询）

        原 NqiToolGUI._query_4g_voice_table
        """
        import numpy as np

        volte_fields = table_config.get('volte_fields', [])
        epsfb_fields = table_config.get('epsfb_fields', [])

        if not volte_fields or not epsfb_fields:
            self.log("4G语音小区字段配置不完整，无法查询", "ERROR")
            return

        volte_dimension = table_config.get('dimension', {})
        epsfb_dimension = {
            'geographicdimension': '小区',
            'timedimension': '天',
            'enodebField': '---',
            'cgiField': 'cgi',
            'timeField': 'starttime',
            'cellField': 'cell',
            'cityField': 'city',
        }

        if multi_day:
            current_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            dates = []
            while current_date <= end_datetime:
                dates.append(current_date.strftime('%Y-%m-%d'))
                current_date += timedelta(days=1)

            total_days = len(dates)
            selected_city_list = [item.strip() for item in city.split(',') if item.strip()] if city else []
            should_split_by_city = multi_day_per_city and len(selected_city_list) >= 1
            query_cities = selected_city_list if should_split_by_city else ([city] if city else [])

            tasks = []
            for query_date in dates:
                for query_city in query_cities:
                    tasks.append((query_date, query_city, query_city or '全部地市'))

            total_tasks = len(tasks)
            self.log(f"4G语音小区 - 按日查询模式: 共 {total_tasks} 个任务 ({total_days} 天 x {len(query_cities)} 地市)", "INFO")
            if should_split_by_city:
                self.log(f"4G语音小区 - 按日+按地市导出模式: 共 {len(query_cities)} 个地市", "INFO")

            all_merged_dfs = []
            city_day_dfs = []

            def _query_4g_voice_task(task_data):
                if self.jxcx.is_cancelled():
                    return None, {'cancelled': True}
                q_date, q_city, q_city_label = task_data
                try:
                    conditions = [
                        {'field': 'starttime', 'operator': '>=', 'value': q_date},
                        {'field': 'starttime', 'operator': '<=', 'value': q_date},
                    ]
                    if q_city:
                        conditions.append({'field': 'city', 'operator': 'in', 'value': q_city})
                    thread_query = self._make_thread_query()
                    payloads = thread_query.build_4g_voice_payload(
                        volte_fields, epsfb_fields, conditions,
                        volte_dimension, epsfb_dimension
                    )
                    volte_payload = payloads['volte']
                    epsfb_payload = payloads['epsfb']
                    voice_data = thread_query.get_4g_voice_table(volte_payload, epsfb_payload)
                    if voice_data.empty:
                        return None, None
                    merged_df = add_4g_voice_calc_columns(voice_data, log_func=self.log)
                    return q_date, q_city_label, merged_df
                except Exception as e:
                    return None, {'date': q_date, 'city': q_city_label, 'error': str(e)}

            completed_tasks = 0
            executor = ThreadPoolExecutor(max_workers=min(DEFAULT_THREAD_POOL_SIZE, total_tasks))
            futures = {executor.submit(_query_4g_voice_task, task): task for task in tasks}
            try:
                for future in as_completed(futures):
                    if self.jxcx.is_cancelled():
                        self.log("4G语音查询收到取消请求，取消尚未开始的任务", "WARNING")
                        break
                    result = future.result()
                    completed_tasks += 1
                    self._after(0, lambda t=completed_tasks, tot=total_tasks:
                                self._update_progress(t / tot, tot, f"查询4G语音小区 [{t}/{tot}]"))
                    if result[0] is not None:
                        q_date, q_city_label, merged_df = result
                        if should_split_by_city:
                            city_day_dfs.append((f"{q_date.replace('-', '')}_{q_city_label}", merged_df))
                            filename = f"4G语音小区_{q_date}_{q_city_label}.xlsx"
                            filepath = export_to_excel(merged_df, filename, "4G语音小区")
                            if filepath:
                                self._after(0, lambda fp=filepath, cnt=len(merged_df), dt=q_date, cl=q_city_label:
                                            self.log(f"  {dt} {cl}: {cnt} 条数据 -> {os.path.basename(fp)}", "SUCCESS"))
                        elif multi_day_per_sheet:
                            all_merged_dfs.append((q_date.replace('-', ''), merged_df))
                        else:
                            filename = f"4G语音小区_{q_date}.xlsx"
                            filepath = export_to_excel(merged_df, filename, "4G语音小区")
                            if filepath:
                                self._after(0, lambda fp=filepath, cnt=len(merged_df), dt=q_date:
                                            self.log(f"  {dt}: {cnt} 条数据 -> {os.path.basename(fp)}", "SUCCESS"))
                    elif result[1] is not None:
                        err = result[1]
                        self._after(0, lambda e=err:
                                    self.log(f"  查询异常 [{e['date']} {e['city']}]: {e['error']}", "ERROR"))
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

            if should_split_by_city and city_day_dfs:
                self.log(f"4G语音小区按日+按地市导出完成: 共导出 {len(city_day_dfs)} 个文件", "SUCCESS")

            if multi_day_per_sheet and all_merged_dfs:
                filename = f"4G语音小区_{start_date}_{end_date}.xlsx"
                self.export_multi_sheet(filename, all_merged_dfs, "4G语音小区")
                self.log(f"按日分Sheet导出完成: {filename}", "SUCCESS")

        else:
            conditions = [
                {'field': 'starttime', 'operator': '>=', 'value': start_date},
                {'field': 'starttime', 'operator': '<=', 'value': end_date},
            ]
            if city:
                conditions.append({'field': 'city', 'operator': 'in', 'value': city})

            self.log(f"4G语音小区: 查询 {start_date} 至 {end_date}", "INFO")

            payloads = self.jxcx.build_4g_voice_payload(
                volte_fields, epsfb_fields, conditions,
                volte_dimension, epsfb_dimension
            )
            volte_payload = payloads['volte']
            epsfb_payload = payloads['epsfb']

            merged_df = self.jxcx.get_4g_voice_table(volte_payload, epsfb_payload)

            if not merged_df.empty:
                try:
                    merged_df = add_4g_voice_calc_columns(merged_df, log_func=self.log)
                except Exception as e:
                    self.log(f"添加计算列异常: {e}", "WARNING")

                filename = f"4G语音小区_{start_date}_{end_date}.xlsx"
                filepath = export_to_excel(merged_df, filename, "4G语音小区")
                if filepath:
                    self.log(f"4G语音小区数据已导出到: {os.path.basename(filepath)}", "SUCCESS")
            else:
                self.log("4G语音小区查询结果为空", "WARNING")

    # ==================== 工具方法 ====================

    @staticmethod
    def apply_custom_fields_static(df, custom_fields_enabled, selected_fields_snapshot, table_name, field_configs=None):
        """应用自定义字段选择到 DataFrame（纯函数，无 GUI 依赖）

        Args:
            df: 原始 DataFrame
            custom_fields_enabled: 是否启用自定义字段
            selected_fields_snapshot: {table_name: [field_keys]}
            table_name: 表名
            field_configs: (可选) 字段配置映射，用于中文名匹配

        Returns:
            DataFrame: 过滤后的 DataFrame
        """
        if not custom_fields_enabled or table_name not in selected_fields_snapshot:
            return df
        selected_field_keys = selected_fields_snapshot[table_name]
        available_fields = [col for col in df.columns if col in selected_field_keys]
        if not available_fields and field_configs and table_name in field_configs:
            config_map = {c.get('columnname'): c.get('columnname') for c in field_configs[table_name]}
            for col in df.columns:
                if col in config_map and config_map[col] in selected_field_keys:
                    available_fields.append(col)
        if available_fields:
            return df[available_fields]
        return df

    def apply_custom_fields(self, df, table_name):
        """应用自定义字段（实例方法，访问 tkinter 变量）

        仅在主线程或已预读快照的场景使用。
        """
        custom_fields_enabled = self._custom_fields_enabled
        selected_fields = getattr(self, 'selected_fields', {})
        return self.apply_custom_fields_static(
            df, custom_fields_enabled, selected_fields, table_name
        )

    def export_multi_sheet(self, filename, sheets_data, default_sheet):
        """导出多Sheet的Excel文件（原 NqiToolGUI._export_multi_sheet）"""
        ensure_dirs()
        filepath = os.path.join(OUTPUT_DIR, filename)

        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                for sheet_name, df in sheets_data:
                    clean_df = df.copy()
                    clean_df = clean_df.map(lambda value: None if pd.isna(value) else value)
                    clean_df.to_excel(writer, sheet_name=str(sheet_name)[:31], index=False)
            logger.info("多Sheet导出完成: %s (%d个Sheet)", filepath, len(sheets_data))
        except Exception as e:
            logger.error("多Sheet导出失败: %s", e)