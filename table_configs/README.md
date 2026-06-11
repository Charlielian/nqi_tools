# YAML表格配置说明

## 目录说明

此目录存放所有内置表格的YAML配置文件。每个表格对应一个 `.yaml` 文件，程序启动时自动加载。

## 添加新表格

### 方法一：添加到本目录

1. 在本目录创建新的 `.yaml` 文件
2. 填写配置（参考已有文件）
3. 重启程序，表格自动出现

### 方法二：添加到 custom_configs 目录（推荐）

用户自定义配置建议放在项目根目录的 `custom_configs/` 目录中：
- 不影响内置配置
- 打包发布时不会覆盖
- 方便用户扩展

### 方法三：使用配置来源切换功能

程序界面提供"配置来源"切换按钮：
- **YAML配置**：使用YAML文件中的配置
- **旧代码**：使用Python代码中的硬编码配置

## 占位符

在 `conditions.where` 的 `val` 字段中可以使用以下占位符：
- `{start_date}` - 开始日期
- `{end_date}` - 结束日期
- `{city}` - 地市

## 配置格式

每个YAML文件包含以下配置项：

```yaml
# 基本信息（必填）
name: 表格显示名称
table_key: 后端API的table_key
table_name: 数据库表名
fieldtype: 字段类型
api_type: search  # 或 table

# 维度配置
dimension:
  geographicdimension: 地理维度
  timedimension: 时间维度
  enodebField: 基站字段
  cgiField: CGI字段
  timeField: 时间字段
  cellField: 小区字段
  cityField: 地市字段

# 字段列表
fields:
  - feild: starttime
    feildName: 数据时间
    datatype: character varying
    columntype: 1

# 查询条件
conditions:
  where:
    - feild: starttime
      datatype: timestamp
      symbol: '>='
      val: '{start_date} 00:00:00'
      whereCon: and
      query: true
```

## 字段属性

`fields` 列表中的每个字段可以包含以下属性：

| 属性 | 必填 | 说明 |
|------|------|------|
| feild | 是 | 字段英文名 |
| feildName | 是 | 字段中文名 |
| datatype | 否 | 数据类型，默认 character varying |
| columntype | 否 | 列类型，默认 1 |
| feildtype | 否 | 字段类型，自动从顶层继承 |
| table | 否 | 表名，自动从顶层继承 |
| tableName | 否 | 表显示名，自动从顶层继承 |

## 工参表格

工参表格需要设置 `is_gongcan: true`，且通常没有时间条件。

## 示例文件

参考以下文件了解不同类型表格的配置：
- `5G干扰小区.yaml` - 标准干扰报表
- `5G小区工参报表.yaml` - 工参表格
- `5G小区容量报表.yaml` - 容量报表
