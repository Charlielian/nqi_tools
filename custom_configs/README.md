# 自定义表格配置

此目录用于存放用户自定义的表格YAML配置文件。

## 使用方法

1. 在本目录创建新的 `.yaml` 文件
2. 参考下方模板填写配置
3. 重启程序，表格自动出现

## 配置模板

```yaml
# 表格显示名称（必填且唯一）
name: 我的自定义表格

# API配置
table_key: 后端API的table_key
table_name: 数据库表名
fieldtype: 字段类型
api_type: search  # 或 table

# 维度配置
dimension:
  geographicdimension: 小区
  timedimension: 天
  enodebField: enodeb_id
  cgiField: cgi
  timeField: starttime
  cellField: cell
  cityField: city

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

## 占位符

在 conditions.where 的 val 字段中可使用：
- `{start_date}` - 开始日期
- `{end_date}` - 结束日期
- `{city}` - 地市

## 注意事项

- 文件名建议使用英文
- name 字段必须唯一
- 字段名必须与API返回的字段名一致
