# NQI 报表查询接口文档

本文档介绍如何通过即席查询（JXCX）接口获取各类报表数据。

## 1. 接口概述

### 1.1 核心 API

| 用途 | URL | 方法 |
|------|-----|------|
| 进入即席查询 | `{BASE_URL}/pro-portal/pure/urlAction.action` | GET |
| 获取字段配置 | `{BASE_URL}/adhocquery/search` | POST |
| 获取表字段 | `{BASE_URL}/adhocquery/getSelectTable` | POST |
| 查询数据总数 | `{BASE_URL}/adhocquery/getTableCount` | POST |
| 查询数据内容 | `{BASE_URL}/adhocquery/query` | POST |

### 1.2 必要参数

- `CASTGC`: 登录后获取的 Cookie，用于身份认证
- 请求头需包含 `Content-Type: application/x-www-form-urlencoded`

---

## 2. 认证流程

### 2.1 获取访问令牌

```python
# 从 Cookie 中获取 CASTGC
castgc = session.cookies.get('CASTGC', domain='nqi.gmcc.net')

# 构造进入即席查询的请求
params = {
    'url': 'pro-adhoc/index',
    'random': random.random(),
    '__PID': 'JXCX',
    'token': castgc
}
url = f'{BASE_URL}/pro-portal/pure/urlAction.action'
res = session.get(url, params=params)
```

---

## 3. 字段配置获取

### 3.1 使用 search 接口（推荐）

```python
# 通过报表关键字获取字段配置
data = {'key': '报表关键字'}
fields = ['columnname_cn', 'columnname', 'fieldtype', 'datatype',
          'tablename', 'tablename_cn', 'columntype', 'sort']

for field in fields:
    data['field'] = field

res = session.post(f'{BASE_URL}/adhocquery/search',
                   data=data, headers=HEADERS)
configs = res.json().get('CFG_ADHOC_CONF_SEARCH', [])
```

### 3.2 使用 getSelectTable 接口

```python
# 通过数据库表名获取字段配置
data = {'tablename': '数据库表名'}
res = session.post(f'{BASE_URL}/adhocquery/getSelectTable',
                   data=data, headers=HEADERS)
configs = res.json().get('CFG_ADHOC_CONF_TABLE', [])
```

---

## 4. 查询条件构建

### 4.1 条件格式

支持两种格式：

**新格式（推荐）**：
```python
conditions = [
    {'field': 'starttime', 'operator': '>=', 'value': '2026-04-01'},
    {'field': 'starttime', 'operator': '<=', 'value': '2026-04-30'},
    {'field': 'city', 'operator': '=', 'value': '广州'}
]
```

**旧格式（兼容）**：
```python
conditions = [
    {'feild': 'starttime', 'symbol': '>=', 'val': '2026-04-01 00:00:00', 'datatype': 'timestamp'},
    {'feild': 'city', 'symbol': '=', 'val': '广州', 'datatype': 'character'}
]
```

### 4.2 时间字段处理

- 时间字段建议使用 `timestamp` 类型
- 开始时间：`operator: '>='`，格式：`2026-04-01 00:00:00`
- 结束时间：`operator: '<'`，格式：`2026-04-30 23:59:59`（使用 `<` 而非 `<=`）
- 也可使用 `operator: '<='`，值格式：`2026-04-30 23:59:59`

### 4.3 条件转换函数

项目已实现自动转换：

```python
from core.query import convert_where_conditions

# 新格式转旧格式
converted = convert_where_conditions(conditions)
# 返回: [{'datatype': 'timestamp', 'feild': 'starttime', 'symbol': '>=',
#         'val': '2026-04-01 00:00:00', 'whereCon': 'and', 'query': True}, ...]
```

---

## 5. Payload 构建

### 5.1 完整 Payload 结构

```python
payload = {
    'draw': 1,
    'start': 0,
    'length': 200,           # 每页数量
    'total': 0,

    # 维度配置
    'geographicdimension': '小区',  # 地理维度
    'timedimension': '天',         # 时间维度
    'enodebField': 'enodeb_id',
    'cgiField': 'cgi',
    'timeField': 'starttime',
    'cellField': 'cell',
    'cityField': 'city',

    # DataTables 格式
    'columns': [
        {'data': '字段名', 'name': '', 'searchable': True, 'orderable': True,
         'search': {'value': '', 'regex': False}}
    ],
    'order': [{'column': 0, 'dir': 'desc'}],
    'search': {'value': '', 'regex': False},

    # 字段配置
    'result': {
        'result': [
            {'feildtype': '', 'table': '表名', 'tableName': '表中文名',
             'datatype': 'character varying', 'columntype': 1,
             'feildName': '字段中文名', 'feild': '字段英文名',
             'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'}
        ],
        'tableParams': {
            'supporteddimension': '',
            'supportedtimedimension': ''
        },
        'columnname': ''
    },

    # 查询条件
    'where': converted_conditions,

    'indexcount': 0
}
```

### 5.2 使用 JXCXQuery 类

```python
from core.query import JXCXQuery

query = JXCXQuery(session)

# 方式1：自动从 API 获取字段配置
payload = query.build_payload_from_config(
    table_key='报表关键字',
    fieldtype='类型',
    where_conditions=conditions,
    api_type='search'  # 或 'table'
)

# 方式2：使用预定义的字段配置
payload = query.build_payload_from_config(
    table_key='报表关键字',
    fieldtype='类型',
    where_conditions=conditions,
    fields_override=field_configs,  # 预定义字段配置列表
    dimension_override={'geographicdimension': '小区', 'timedimension': '天'}
)
```

---

## 6. 数据查询

### 6.1 获取数据总数

```python
# 只传递必要的字段
key_list = ['geographicdimension', 'timedimension', 'enodebField', 'cgiField',
            'timeField', 'cellField', 'cityField', 'result', 'where', 'indexcount']
count_payload = {key: value for key, value in payload.items() if key in key_list}

res = session.post(f'{BASE_URL}/adhocquery/getTableCount',
                   data=encode_payload(count_payload), headers=HEADERS)
total_count = res.json().get('count', 0)
```

### 6.2 获取数据内容

```python
# 一次性获取全部数据
data_payload = payload.copy()
data_payload['start'] = 0
data_payload['length'] = total_count  # 全部数据

res = session.post(f'{BASE_URL}/adhocquery/query',
                   data=encode_payload(data_payload), headers=HEADERS)
data_list = res.json().get('data', [])
```

### 6.3 使用 get_table 方法

```python
import pandas as pd
from core.query import JXCXQuery

query = JXCXQuery(session)

# 获取 DataFrame
df = query.get_table(payload, to_df=True, report_name="报表名称")

# 获取原始列表
result = query.get_table(payload, to_df=False)
data_list = result['data']
```

---

## 7. 数据导出

### 7.1 基础导出

```python
from core.export import export_to_excel

filepath = export_to_excel(df, 'report.xlsx', sheet_name='Sheet1')
```

### 7.2 导出并格式化

```python
from core.export import export_with_format

filepath = export_with_format(df, 'report.xlsx',
                              sheet_name='Sheet1',
                              header_color='165DFF')
```

### 7.3 追加到现有文件

```python
export_to_excel(df1, 'report.xlsx', sheet_name='数据1', append=False)
export_to_excel(df2, 'report.xlsx', sheet_name='数据2', append=True)
```

---

## 8. 完整示例

### 8.1 基础报表查询

```python
import requests
from core.query import JXCXQuery, convert_where_conditions
from core.export import export_with_format

# 1. 登录并获取 session
session = requests.Session()
# ... 登录逻辑 ...

# 2. 创建查询对象
query = JXCXQuery(session)

# 3. 构建查询条件
conditions = [
    {'field': 'starttime', 'operator': '>=', 'value': '2026-04-01'},
    {'field': 'starttime', 'operator': '<', 'value': '2026-05-01'},
    {'field': 'city', 'operator': '=', 'value': '广州'}
]

# 4. 构建 Payload
payload = query.build_payload_from_config(
    table_key='4G小区性能',
    fieldtype='4G',
    where_conditions=conditions,
    api_type='search'
)

# 5. 查询数据
df = query.get_table(payload, to_df=True, report_name="4G小区性能报表")

# 6. 导出
if not df.empty:
    filepath = export_with_format(df, '4G小区性能.xlsx')
    print(f"已导出到: {filepath}")
```

### 8.2 4G语音联合报表

```python
# 构建 VoLTE 和 EPSFB 的 Payload
volte_payload = query.build_payload_from_config(...)
epsfb_payload = query.build_payload_from_config(...)

# 联合查询（自动合并）
result = query.get_4g_voice_table(volte_payload, epsfb_payload, to_df=True)
df_merged = result  # 返回合并后的 DataFrame
```

---

## 9. 常见问题

### 9.1 Session 过期

如果查询返回空数据或错误，可能需要重新进入即席查询：

```python
query.enabled = False
if not query.enter_jxcx():
    print("重新登录失败")
```

### 9.2 数据为空

检查以下几点：
1. 日期范围内是否有数据
2. 地市名称是否与数据库匹配（如 "广州" vs "广州市"）
3. 查询条件字段名是否正确
4. 时间字段格式是否正确

### 9.3 超时处理

大数据量查询会自动调整超时时间：
- 数据量 < 50000：60秒超时
- 数据量 < 500000：100秒超时
- 数据量更大：最大 300 秒

---

## 10. API 响应格式

### 10.1 获取总数响应

```json
{"count": 12345}
```

或

```json
{"data": {"count": 12345}}
```

### 10.2 查询数据响应

```json
{
  "data": [
    {"字段1": "值1", "字段2": "值2"},
    {"字段1": "值3", "字段2": "值4"}
  ]
}
```

### 10.3 错误响应

```json
{"message": "表不存在或无权限访问"}
```

---

## 附录：维度配置参考

| 维度 | 常用值 |
|------|--------|
| geographicdimension | 小区、网格、区县、地市 |
| timedimension | 天、小时、15分钟 |
| enodebField | enodeb_id |
| cgiField | cgi |
| timeField | starttime、prb_start_time |
| cellField | cell |
| cityField | city |
