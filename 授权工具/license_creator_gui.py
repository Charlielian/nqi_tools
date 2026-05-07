# -*- coding: utf-8 -*-
"""
免审批导出工具 - 授权文件生成器（GUI版本）
提供图形界面，方便生成授权文件

融合方案：生成用户码（不再生成 license.dat）
用户码格式: Base64(AES加密(过期时间戳|机器码))
"""

import os
import sys
import base64
from datetime import datetime

# 加密依赖
try:
    from Crypto.Cipher import AES as AES_Cipher
    from Crypto.Util.Padding import pad
except ModuleNotFoundError:
    from Cryptodome.Cipher import AES as AES_Cipher
    from Cryptodome.Util.Padding import pad

# 配置
PRIVATE_KEY_FILE = "private_key.pem"
LICENSE_AES_KEY = b"GMCCLicenseV2Key"  # 必须与主程序一致
LICENSE_RECORD_FILE = "license_records.json"


def load_records():
    """加载授权记录"""
    if os.path.exists(LICENSE_RECORD_FILE):
        try:
            with open(LICENSE_RECORD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_records(records):
    """保存授权记录"""
    with open(LICENSE_RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def add_record(machine_code, note=""):
    """添加授权记录"""
    records = load_records()

    # 检查是否已存在
    for record in records:
        if record["machine_code"] == machine_code:
            record["count"] = record.get("count", 1) + 1
            record["last_generate_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if note:
                record["note"] = note
            save_records(records)
            return

    # 新增记录
    records.append({
        "machine_code": machine_code,
        "first_generate_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_generate_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": 1,
        "note": note
    })
    save_records(records)


def validate_machine_code(machine_code):
    """验证机器码格式"""
    machine_code = machine_code.strip()
    if len(machine_code) != 64:
        return False, f"机器码长度应为64位，当前为{len(machine_code)}位"
    try:
        int(machine_code, 16)
        return True, None
    except ValueError:
        return False, "机器码包含非法字符"


def aes_encrypt(plaintext, key):
    """AES加密"""
    import os
    iv = os.urandom(16)
    cipher = AES_Cipher.new(key, AES_Cipher.MODE_CBC, iv)
    padded_data = pad(plaintext.encode("utf-8"), 16)
    encrypted_data = cipher.encrypt(padded_data)
    return iv + encrypted_data


def create_user_code(machine_code, expiry_date, note=""):
    """生成用户码（新融合方案）

    用户码格式: Base64(AES加密(过期时间戳|机器码))

    Args:
        machine_code: 机器码
        expiry_date: 过期日期
        note: 备注

    Returns:
        tuple: (success, user_code_or_error_message)
    """
    # 验证机器码
    valid, error = validate_machine_code(machine_code)
    if not valid:
        return False, error

    # 计算过期时间戳
    expiry_datetime = expiry_date.replace(hour=23, minute=59, second=59)
    expiry_timestamp = int(expiry_datetime.timestamp())

    # 构建明文数据
    plaintext = f"{expiry_timestamp}|{machine_code}"

    # AES 加密
    encrypted_data = aes_encrypt(plaintext, LICENSE_AES_KEY)

    # Base64 编码
    user_code = base64.b64encode(encrypted_data).decode('utf-8')

    # 添加授权记录
    add_record(machine_code, note)

    return True, user_code


def main():
    """GUI主函数"""
    import tkinter as tk
    from tkinter import ttk, messagebox
    import json

    root = tk.Tk()
    root.title("授权文件生成器")
    root.geometry("700x550")
    root.update_idletasks()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = (screen_w - 700) // 2
    y = (screen_h - 550) // 2
    root.geometry(f"700x550+{x}+{y}")

    # 创建Notebook（标签页）
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # ========== 标签页1：生成授权 ==========
    gen_frame = ttk.Frame(notebook, padding="15")
    notebook.add(gen_frame, text="  生成授权  ")

    ttk.Label(gen_frame, text="授权文件生成器", font=("Arial", 16, "bold")).pack(pady=(0, 15))

    # 机器码输入
    ttk.Label(gen_frame, text="机器码：").pack(anchor=tk.W)
    machine_entry = ttk.Entry(gen_frame, width=60, font=("Courier New", 10))
    machine_entry.pack(fill=tk.X, pady=(5, 10))
    ttk.Label(gen_frame, text="（64位十六进制机器码，从用户处获取）", foreground="gray").pack(anchor=tk.W)

    # 备注输入
    ttk.Label(gen_frame, text="备注（可选）：").pack(anchor=tk.W, pady=(10, 5))
    note_entry = ttk.Entry(gen_frame, width=60, font=("Microsoft YaHei UI", 10))
    note_entry.pack(fill=tk.X, pady=(0, 10))
    ttk.Label(gen_frame, text="（用于标记这台机器的用途，如：张三的电脑）", foreground="gray").pack(anchor=tk.W)

    # 过期日期输入
    ttk.Label(gen_frame, text="授权截止日期：").pack(anchor=tk.W, pady=(10, 5))

    date_frame = tk.Frame(gen_frame)
    date_frame.pack(fill=tk.X, pady=(0, 10))

    year_var = tk.IntVar(value=datetime.now().year)
    month_var = tk.IntVar(value=datetime.now().month)
    day_var = tk.IntVar(value=min(datetime.now().day, 28))

    ttk.Combobox(date_frame, textvariable=year_var, values=list(range(2024, 2031)), width=5, state="readonly").pack(side=tk.LEFT)
    ttk.Label(date_frame, text="年").pack(side=tk.LEFT, padx=(2, 8))
    ttk.Combobox(date_frame, textvariable=month_var, values=list(range(1, 13)), width=3, state="readonly").pack(side=tk.LEFT)
    ttk.Label(date_frame, text="月").pack(side=tk.LEFT, padx=(2, 8))
    ttk.Combobox(date_frame, textvariable=day_var, values=list(range(1, 32)), width=3, state="readonly").pack(side=tk.LEFT)
    ttk.Label(date_frame, text="日").pack(side=tk.LEFT, padx=(2, 0))

    # 用户码输出
    ttk.Label(gen_frame, text="用户码：").pack(anchor=tk.W, pady=(10, 5))

    output_frame = tk.Frame(gen_frame, bg='#f8f9fa')
    output_frame.pack(fill=tk.X, pady=(0, 10))

    output_text = tk.Text(output_frame, height=3, font=("Courier New", 9), relief='flat', wrap=tk.WORD)
    output_text.pack(fill=tk.X, padx=5, pady=5)
    output_text.insert("1.0", "生成后将显示用户码，请复制给用户")
    output_text.config(state='disabled')

    # 生成按钮和复制按钮
    btn_frame = ttk.Frame(gen_frame)
    btn_frame.pack(fill=tk.X, pady=(10, 0))

    def on_copy():
        text = output_text.get("1.0", tk.END).strip()
        if text and text != "生成后将显示用户码，请复制给用户":
            root.clipboard_clear()
            root.clipboard_append(text)
            messagebox.showinfo("成功", "用户码已复制到剪贴板")
        else:
            messagebox.showwarning("提示", "没有可复制的用户码")

    def on_generate():
        machine_code = machine_entry.get().strip()
        if not machine_code:
            messagebox.showwarning("警告", "请输入机器码")
            return

        note = note_entry.get().strip()

        try:
            expiry_date = datetime(year_var.get(), month_var.get(), day_var.get())
        except ValueError:
            messagebox.showerror("错误", "日期无效")
            return

        success, result = create_user_code(machine_code, expiry_date, note)
        if success:
            output_text.config(state='normal')
            output_text.delete("1.0", tk.END)
            output_text.insert("1.0", result)
            output_text.config(state='disabled')
            messagebox.showinfo("成功", "用户码已生成，请复制给用户")
            refresh_records()
        else:
            messagebox.showerror("失败", result)

    ttk.Button(btn_frame, text="生成用户码", command=on_generate).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="复制用户码", command=on_copy).pack(side=tk.LEFT, padx=5)

    # ========== 标签页2：授权记录 ==========
    records_frame = ttk.Frame(notebook, padding="15")
    notebook.add(records_frame, text="  授权记录  ")

    ttk.Label(records_frame, text="授权记录", font=("Arial", 14, "bold")).pack(pady=(0, 10))

    # 创建Treeview显示记录
    columns = ("machine_code", "note", "count", "last_time")
    tree = ttk.Treeview(records_frame, columns=columns, show="headings", height=12)

    tree.heading("machine_code", text="机器码")
    tree.heading("note", text="备注")
    tree.heading("count", text="生成次数")
    tree.heading("last_time", text="最后生成时间")

    tree.column("machine_code", width=220)
    tree.column("note", width=150)
    tree.column("count", width=80, anchor="center")
    tree.column("last_time", width=160, anchor="center")

    # 添加滚动条
    scrollbar = ttk.Scrollbar(records_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh_records():
        """刷新授权记录列表"""
        for item in tree.get_children():
            tree.delete(item)
        records = load_records()
        for record in records:
            tree.insert("", tk.END, values=(
                record.get("machine_code", ""),
                record.get("note", ""),
                record.get("count", 1),
                record.get("last_generate_time", "")
            ))

    def on_copy_code():
        """复制选中的机器码"""
        selection = tree.selection()
        if selection:
            values = tree.item(selection[0])["values"]
            root.clipboard_clear()
            root.clipboard_append(values[0])
            messagebox.showinfo("成功", "机器码已复制到剪贴板")

    def on_delete_record():
        """删除选中的记录"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一条记录")
            return

        if messagebox.askyesno("确认", "确定要删除这条授权记录吗？"):
            values = tree.item(selection[0])["values"]
            machine_code = values[0]
            records = load_records()
            records = [r for r in records if r["machine_code"] != machine_code]
            save_records(records)
            refresh_records()
            messagebox.showinfo("成功", "记录已删除")

    # 记录操作按钮
    record_btn_frame = ttk.Frame(records_frame)
    record_btn_frame.pack(fill=tk.X, pady=(10, 0))

    ttk.Button(record_btn_frame, text="刷新", command=refresh_records).pack(side=tk.LEFT, padx=5)
    ttk.Button(record_btn_frame, text="复制机器码", command=on_copy_code).pack(side=tk.LEFT, padx=5)
    ttk.Button(record_btn_frame, text="删除记录", command=on_delete_record).pack(side=tk.LEFT, padx=5)

    # 底部按钮
    bottom_frame = ttk.Frame(root, padding="10")
    bottom_frame.pack(fill=tk.X)

    records = load_records()
    ttk.Label(bottom_frame, text=f"共 {len(records)} 条授权记录", foreground="#666666").pack(side=tk.LEFT)
    ttk.Button(bottom_frame, text="退出", command=root.destroy).pack(side=tk.RIGHT)

    # 初始加载记录
    refresh_records()

    root.mainloop()


if __name__ == '__main__':
    main()
