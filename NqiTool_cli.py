# -*- coding: utf-8 -*-
"""
NQI工具 - CLI 交互式版本
命令行界面，无需图形环境即可运行

使用方法：
    python NqiTool_cli.py

功能：
    - 交互式登录认证
    - 聚类工单查询
    - 即席数据查询
    - 数据导出到Excel
"""

import sys
import os
import cmd
import shlex
import getpass
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.auth import LoginManager
from core.query import JXCXQuery
from core.export import export_with_format
from core.license import (
    get_hw_info, generate_machine_code,
    verify_with_user_code, save_user_code, decrypt_user_code
)
from utils.logger import ensure_dirs, setup_report_logging
from utils.config import (
    LOG_DIR, OUTPUT_DIR, EXPIRY_DATE,
    DEFAULT_USERNAME, DEFAULT_PASSWORD
)
from utils.helpers import save_cookie, load_cookie

import logging
import requests


class Colors:
    """ANSI 颜色代码"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def colored(text, color):
    """为文本添加颜色"""
    return f"{color}{text}{Colors.END}"


def print_banner():
    """打印程序横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════════════╗
║                    NQI工具 - CLI 交互式版本                          ║
║                    数据提取工具 v2.0                                 ║
╚══════════════════════════════════════════════════════════════════════╝
"""
    print(colored(banner, Colors.CYAN))


def print_menu():
    """打印主菜单"""
    menu = """
┌──────────────────────────────────────────────────────────────────────┐
│  主菜单                                                                │
├──────────────────────────────────────────────────────────────────────┤
│  1. 登录认证         - 登录 NQI 平台                                  │
│  2. 聚类工单查询     - 查询聚类工单数据                                │
│  3. 即席查询         - 使用即席查询提取数据                            │
│  4. 导出数据         - 导出已查询的数据到 Excel                        │
│  5. 查看状态         - 查看当前登录状态和会话信息                       │
│  6. 帮助             - 显示帮助信息                                    │
│  0. 退出             - 退出程序                                        │
└──────────────────────────────────────────────────────────────────────┘
"""
    print(colored(menu, Colors.BLUE))


class NqiCLI(cmd.Cmd):
    """NQI 工具命令行交互界面"""

    intro = ''
    prompt = colored('\n[NQI-CLI] ', Colors.YELLOW)
    doc_header = colored("可用命令 (输入 help <命令> 查看详细帮助)", Colors.GREEN)

    def __init__(self):
        super().__init__()
        self.session = None
        self.logged_in = False
        self.jxcx = None
        self.current_data = None
        self.current_data_name = None
        self.username = DEFAULT_USERNAME
        self.password = DEFAULT_PASSWORD

        # 初始化日志
        ensure_dirs()
        setup_report_logging(LOG_DIR, console=True)
        self.logger = logging.getLogger('NqiTool.CLI')
        self.logger.setLevel(logging.DEBUG)

        # 初始化聚类查询相关变量
        self.selected_city = None
        self.selected_grids = []
        self.selected_labels = []
        self.all_labels = []

    def _check_auth(self):
        """检查是否已登录"""
        if not self.logged_in:
            print(colored("\n[错误] 请先登录！输入 'login' 或 '1' 进行登录。", Colors.RED))
            return False
        return True

    def _init_services(self):
        """初始化查询服务"""
        if self.logged_in and self.session:
            self.jxcx = JXCXQuery(self.session)

    # ========== 登录命令 ==========

    def do_login(self, arg):
        """登录 NQI 平台
        用法: login [用户名]
        如果不提供用户名，将使用配置文件中的默认用户名
        """
        if self.logged_in:
            print(colored("\n[提示] 您已登录，是否重新登录？ (y/n): ", Colors.YELLOW), end='')
            choice = input().strip().lower()
            if choice != 'y':
                print(colored("取消登录。", Colors.CYAN))
                return

        # 获取用户名
        if arg:
            username = arg.strip()
        else:
            print(colored("\n[登录] NQI 平台", Colors.GREEN))
            print(colored("-" * 40, Colors.BLUE))
            default_user = DEFAULT_USERNAME if DEFAULT_USERNAME != 'XXXXX' else ''
            if default_user:
                print(colored(f"默认用户名: {default_user}", Colors.CYAN))
                print(colored("直接回车使用默认用户名，或输入新用户名: ", Colors.YELLOW), end='')
                user_input = input().strip()
                username = user_input if user_input else default_user
            else:
                print(colored("请输入用户名: ", Colors.YELLOW), end='')
                username = input().strip()

        if not username:
            print(colored("[错误] 用户名不能为空", Colors.RED))
            return

        # 获取密码
        print(colored("请输入密码: ", Colors.YELLOW), end='')
        password = getpass.getpass('')

        if not password:
            print(colored("[错误] 密码不能为空", Colors.RED))
            return

        self.username = username
        self.password = password

        print(colored("\n[登录] 正在验证凭据...", Colors.YELLOW))

        # 执行登录
        login_mgr = LoginManager(username, password)
        self.session = login_mgr.login(try_times=3)

        if self.session:
            self.logged_in = True
            self._init_services()
            print(colored("\n[成功] 登录成功！", Colors.GREEN))
            print(colored("-" * 40, Colors.BLUE))
            print(colored(f"  用户名: {username}", Colors.CYAN))
            print(colored(f"  登录时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Colors.CYAN))
            print(colored("-" * 40, Colors.BLUE))
        else:
            print(colored("\n[失败] 登录失败，请检查用户名和密码。", Colors.RED))
            print(colored("提示: 可能需要短信验证码，请确保能接收短信。", Colors.YELLOW))

    def do_logout(self, arg):
        """退出登录
        用法: logout
        """
        if not self.logged_in:
            print(colored("\n[提示] 您尚未登录。", Colors.YELLOW))
            return

        print(colored("\n[退出登录] 确定退出？ (y/n): ", Colors.YELLOW), end='')
        choice = input().strip().lower()

        if choice == 'y':
            self.session = None
            self.logged_in = False
            self.jxcx = None
            print(colored("[成功] 已退出登录。", Colors.GREEN))

    # ========== 状态查看命令 ==========

    def do_status(self, arg):
        """查看当前状态
        用法: status
        """
        print(colored("\n┌─────────────────────────────────────┐", Colors.BLUE))
        print(colored("│         NQI 工具状态信息             │", Colors.GREEN))
        print(colored("├─────────────────────────────────────┤", Colors.BLUE))

        # 登录状态
        if self.logged_in:
            print(colored("│  登录状态:  ✓ 已登录                │", Colors.GREEN))
            print(colored(f"│  用户名:    {self.username:<24} │", Colors.CYAN))
            print(colored(f"│  登录时间:  {datetime.now().strftime('%Y-%m-%d %H:%M'):<22} │", Colors.CYAN))

            # 检查 Session 有效性
            if self.jxcx and self.jxcx.check_session_valid():
                print(colored("│  Session:   ✓ 有效                  │", Colors.GREEN))
            else:
                print(colored("│  Session:   ⚠ 可能已过期            │", Colors.YELLOW))
        else:
            print(colored("│  登录状态:  ✗ 未登录                 │", Colors.RED))

        # 当前数据状态
        print(colored("├─────────────────────────────────────┤", Colors.BLUE))
        if self.current_data is not None:
            rows = len(self.current_data) if hasattr(self.current_data, '__len__') else 0
            print(colored(f"│  当前数据:  ✓ 已加载                │", Colors.GREEN))
            print(colored(f"│  数据名称:  {self.current_data_name or '未知':<22} │", Colors.CYAN))
            print(colored(f"│  数据行数:  {rows:<24} │", Colors.CYAN))
        else:
            print(colored("│  当前数据:  ✗ 未加载                 │", Colors.YELLOW))

        print(colored("└─────────────────────────────────────┘", Colors.BLUE))

    # ========== 即席查询命令 ==========

    def do_query(self, arg):
        """即席查询
        用法: query [报表名称]
        进入即席查询交互流程
        """
        if not self._check_auth():
            return

        print(colored("\n╔══════════════════════════════════════════════════════════════╗", Colors.CYAN))
        print(colored("║                  即席查询系统                                ║", Colors.GREEN))
        print(colored("╚══════════════════════════════════════════════════════════════╝", Colors.CYAN))

        # 预定义的报表模板
        reports = {
            '1': ('VoLTE小区监控预警数据表-天', 'volte'),
            '2': ('EPSFB小区监控预警数据表-天', 'epsfb'),
            '3': ('4G小区监控预警日报', '4g'),
            '4': ('5G小区监控日报', '5g'),
            '5': ('自定义查询', 'custom')
        }

        print(colored("\n【步骤 1/3】选择报表模板", Colors.YELLOW))
        print(colored("-" * 50, Colors.BLUE))
        for k, (name, code) in reports.items():
            print(colored(f"  {k}. {name}", Colors.CYAN))

        print(colored("\n请输入报表编号: ", Colors.YELLOW), end='')
        report_choice = input().strip() or '5'

        if report_choice == '5':
            print(colored("\n请输入报表名称（从 JXCX 系统获取）: ", Colors.YELLOW), end='')
            report_name = input().strip()
            if not report_name:
                print(colored("[错误] 报表名称不能为空", Colors.RED))
                return
        else:
            report_name = reports.get(report_choice, ('', ''))[0]

        print(colored(f"  已选择报表: {report_name}", Colors.GREEN))

        # 选择日期范围
        print(colored("\n【步骤 2/3】选择日期范围", Colors.YELLOW))
        print(colored("-" * 50, Colors.BLUE))

        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        print(colored(f"  默认开始日期: {week_ago}", Colors.CYAN))
        print(colored(f"  默认结束日期: {yesterday}", Colors.CYAN))

        print(colored("\n  开始日期 (YYYY-MM-DD): ", Colors.YELLOW), end='')
        start_date = input().strip() or week_ago

        print(colored("  结束日期 (YYYY-MM-DD): ", Colors.YELLOW), end='')
        end_date = input().strip() or yesterday

        # 验证日期格式
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            print(colored("[错误] 日期格式不正确", Colors.RED))
            return

        # 选择地市
        print(colored("\n【步骤 3/3】选择地市（可选）", Colors.YELLOW))
        print(colored("-" * 50, Colors.BLUE))
        print(colored("  输入地市名称（如：广州、深圳），直接回车跳过: ", Colors.YELLOW), end='')
        city = input().strip()

        # 构建查询条件
        where_conditions = []
        if start_date:
            where_conditions.append({
                'field': 'starttime',
                'operator': '>=',
                'value': start_date
            })
        if end_date:
            where_conditions.append({
                'field': 'starttime',
                'operator': '<=',
                'value': end_date
            })
        if city:
            where_conditions.append({
                'field': 'city',
                'operator': '=',
                'value': city
            })

        # 确认并执行
        print(colored("\n" + "=" * 60, Colors.CYAN))
        print(colored("查询参数确认", Colors.BOLD))
        print(colored("=" * 60, Colors.CYAN))
        print(colored(f"  报表: {report_name}", Colors.CYAN))
        print(colored(f"  日期范围: {start_date} 至 {end_date}", Colors.CYAN))
        print(colored(f"  地市: {city or '全部'}", Colors.CYAN))
        print(colored("=" * 60, Colors.CYAN))

        print(colored("\n是否执行查询？ (y/n): ", Colors.YELLOW), end='')
        confirm = input().strip().lower()

        if confirm != 'y':
            print(colored("已取消查询。", Colors.YELLOW))
            return

        # 执行查询
        print(colored("\n正在进入即席查询模块...", Colors.YELLOW))

        # 进入即席查询
        if not self.jxcx.enter_jxcx():
            print(colored("[错误] 无法进入即席查询模块", Colors.RED))
            return

        print(colored("[成功] 即席查询模块已就绪", Colors.GREEN))

        # 构建 payload
        payload = self.jxcx.build_payload_from_config(
            report_name,
            report_name,
            where_conditions,
            api_type='table'
        )

        if not payload:
            print(colored("[错误] 无法构建查询参数", Colors.RED))
            return

        # 执行查询
        print(colored("\n正在查询数据，请稍候（这可能需要一些时间）...", Colors.YELLOW))

        def progress_callback(current, total, message):
            print(colored(f"\r  {message}", Colors.CYAN), end='', flush=True)

        df = self.jxcx.get_table(payload, to_df=True, progress_callback=progress_callback, report_name=report_name)

        if not df.empty:
            print(colored(f"\n\n[成功] 查询完成！获取到 {len(df)} 行数据", Colors.GREEN))

            # 询问是否导出
            print(colored("\n是否导出数据到 Excel？ (y/n): ", Colors.YELLOW), end='')
            if input().strip().lower() == 'y':
                self._export_jxcx_data(df, report_name, start_date, end_date)
        else:
            print(colored("\n[提示] 查询结果为空", Colors.YELLOW))

    def _export_jxcx_data(self, df, report_name, start_date, end_date):
        """导出即席查询数据"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{report_name}_{start_date}_{end_date}_{timestamp}.xlsx"

        try:
            result_path = export_with_format(df, filename, sheet_name='数据', header_color='165DFF')
            if result_path:
                print(colored(f"\n[成功] 数据已导出到:", Colors.GREEN))
                print(colored(f"  {result_path}", Colors.CYAN))
                self.current_data = df
                self.current_data_name = filename
            else:
                print(colored("\n[失败] 导出失败", Colors.RED))
        except Exception as e:
            print(colored(f"\n[错误] 导出异常: {e}", Colors.RED))

    # ========== 导出命令 ==========

    def do_export(self, arg):
        """导出数据
        用法: export [文件名]
        导出当前加载的数据到 Excel 文件
        """
        if self.current_data is None:
            print(colored("\n[错误] 没有已加载的数据可导出", Colors.RED))
            print(colored("提示: 请先执行查询命令加载数据", Colors.YELLOW))
            return

        import pandas as pd

        if isinstance(self.current_data, pd.DataFrame):
            rows = len(self.current_data)
        else:
            rows = len(self.current_data)

        print(colored(f"\n当前数据: {self.current_data_name or '未命名'}", Colors.CYAN))
        print(colored(f"数据行数: {rows}", Colors.CYAN))

        if arg:
            filename = arg.strip()
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            print(colored(f"\n输入文件名（默认: export_{timestamp}.xlsx）: ", Colors.YELLOW), end='')
            filename = input().strip() or f"export_{timestamp}.xlsx"

        if not filename.endswith('.xlsx'):
            filename += '.xlsx'

        print(colored(f"\n正在导出到: {filename}", Colors.YELLOW))

        try:
            import pandas as pd
            if isinstance(self.current_data, pd.DataFrame):
                df = self.current_data
            else:
                df = pd.DataFrame(self.current_data)

            result_path = export_with_format(df, filename, header_color='165DFF')
            if result_path:
                print(colored(f"\n[成功] 数据已导出到:", Colors.GREEN))
                print(colored(f"  {result_path}", Colors.CYAN))
            else:
                print(colored("\n[失败] 导出失败", Colors.RED))
        except Exception as e:
            print(colored(f"\n[错误] 导出异常: {e}", Colors.RED))

    # ========== 帮助命令 ==========

    def do_help(self, arg):
        """显示帮助信息
        用法: help [命令]
        """
        if not arg:
            print(colored("""
╔══════════════════════════════════════════════════════════════════════╗
║                        NQI 工具 CLI 帮助                             ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  登录认证                                                                 ║
║    login [用户名]     登录 NQI 平台                                     ║
║    logout            退出登录                                           ║
║                                                                        ║
║  数据查询                                                                 ║
║    cluster           聚类工单查询（交互式）                              ║
║    query             即席查询（交互式）                                  ║
║                                                                        ║
║  数据导出                                                                 ║
║    export [文件名]    导出当前数据到 Excel                               ║
║                                                                        ║
║  系统命令                                                                 ║
║    status            查看当前状态                                       ║
║    help [命令]       显示帮助信息                                       ║
║    clear             清屏                                               ║
║    exit / quit / 0   退出程序                                           ║
║                                                                        ║
╚══════════════════════════════════════════════════════════════════════╝
""", Colors.CYAN))
        else:
            # 显示特定命令的帮助
            cmd_help = {
                'login': '登录 NQI 平台。用法: login [用户名]',
                'logout': '退出当前登录。',
                'cluster': '聚类工单查询。提供交互式界面选择地市、日期、标签等参数。',
                'query': '即席查询。从 JXCX 系统提取报表数据。',
                'export': '导出数据。将当前加载的数据导出为 Excel 文件。',
                'status': '查看登录状态和当前数据信息。',
                'help': '显示帮助信息。用法: help [命令]',
                'clear': '清屏。',
            }
            help_text = cmd_help.get(arg.lower())
            if help_text:
                print(colored(f"\n{arg}: {help_text}", Colors.GREEN))
            else:
                print(colored(f"\n[错误] 未知命令: {arg}", Colors.RED))

    def do_clear(self, arg):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')

    # ========== 快捷命令 ==========

    def do_1(self, arg):
        """快捷命令: 登录"""
        self.do_login(arg)

    def do_2(self, arg):
        """快捷命令: 聚类工单查询"""
        self.do_cluster(arg)

    def do_3(self, arg):
        """快捷命令: 即席查询"""
        self.do_query(arg)

    def do_4(self, arg):
        """快捷命令: 导出数据"""
        self.do_export(arg)

    def do_5(self, arg):
        """快捷命令: 查看状态"""
        self.do_status(arg)

    def do_6(self, arg):
        """快捷命令: 帮助"""
        self.do_help(arg)

    def do_0(self, arg):
        """快捷命令: 退出"""
        self.do_quit(arg)

    # ========== 退出命令 ==========

    def do_quit(self, arg):
        """退出程序"""
        print(colored("\n感谢使用 NQI 工具 CLI 版本！", Colors.GREEN))
        print(colored("再见！\n", Colors.CYAN))
        return True

    def do_exit(self, arg):
        """退出程序"""
        return self.do_quit(arg)

    def do_EOF(self, arg):
        """处理 Ctrl+D"""
        print(colored("\n再见！", Colors.GREEN))
        return True

    # ========== 空命令处理 ==========

    def emptyline(self):
        """空行处理"""
        print_menu()


def check_license_cli():
    """CLI 模式授权检查"""
    hw_info = get_hw_info()
    machine_code = generate_machine_code(hw_info)
    valid, result = verify_with_user_code(machine_code)
    return valid, result, machine_code


def main():
    """主函数"""
    # 打印横幅
    print_banner()

    # 检查授权
    valid, result, machine_code = check_license_cli()
    if not valid:
        print(colored("[错误] 授权验证失败！", Colors.RED))
        print(colored(f"\n机器码: {machine_code}", Colors.YELLOW))
        print(colored("\n请联系管理员获取授权。\n", Colors.YELLOW))

        # 尝试激活
        print(colored("是否尝试激活？ (y/n): ", Colors.YELLOW), end='')
        if input().strip().lower() == 'y':
            print(colored("\n请输入用户码: ", Colors.YELLOW), end='')
            user_code = input().strip()
            if user_code:
                success, expiry_ts, auth_machine = decrypt_user_code(user_code)
                if success and auth_machine == machine_code:
                    if save_user_code(user_code):
                        print(colored("\n[成功] 激活成功！", Colors.GREEN))
                        valid = True
                    else:
                        print(colored("\n[失败] 保存授权失败", Colors.RED))
                else:
                    print(colored("\n[失败] 用户码无效或与本机不匹配", Colors.RED))

        if not valid:
            print(colored("\n程序将退出。\n", Colors.RED))
            sys.exit(1)

    # 启动 CLI
    print(colored("[提示] 输入 help 查看可用命令\n", Colors.YELLOW))

    cli = NqiCLI()
    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print(colored("\n\n再见！", Colors.GREEN))
        sys.exit(0)


if __name__ == '__main__':
    main()
