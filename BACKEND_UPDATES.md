# 后端修改记录 (Backend Modification Records)

## 日期: 2026-04-30

### 1. 上传接口自动触发可疑线索检测 (`api/upload.py`, `services/suspicion_detector.py`)
- **问题**: 可疑线索仅能通过 `GET /api/cases/{id}/suspicious` 手动触发，数据导入后线索表始终为空。
- **修复**:
  - 在三个上传接口（transactions/communications/logistics）保存数据后自动调用 `SuspicionDetector.detect_all(case_id)`。
  - `create_suspicious_clue()` 增加去重逻辑：按 `(case_id, clue_type, evidence_text)` 判重，重复线索不重复插入。
- **前端对接影响**:
  - 导入成功响应新增字段 `clues_generated`: 本次导入新生成的线索总数（number）。
  - 前端可在导入完成后直接刷新线索视图，无需额外触发检测。

### 2. 微信 CSV 导入空时间戳修复 (`services/wechat_parser.py`, `api/upload.py`)
- **问题**: 微信导出的系统消息（`mediaType=其他`）的 `time` 字段为空，导致插入数据库时报 `NOT NULL constraint failed: communications.communication_time`。
- **修复**:
  - `wechat_parser.py`: 解析时跳过 `_parse_datetime` 返回 `None` 的行（`if comm_time is None: continue`）。
  - `upload.py`: 通讯记录保存时增加兜底 `record.get("communication_time") or datetime.now()`。
- **前端对接影响**: 无，兼容性修复。

### 3. Excel 解析日期/数字类型兼容 (`services/upload_service.py`)
- **问题**: `openpyxl` 读取 Excel 日期单元格返回 `datetime` 对象、数字单元格返回 `int/float`，原 `str()` 包裹可能导致日期格式不匹配或精度丢失。
- **修复**:
  - `_parse_datetime`: 增加 `datetime`/`date` 对象直接返回分支，追加 `%Y-%m-%d %H:%M:%S` 格式支持。
  - `_parse_decimal`: 增加 `int/float` 数字类型直接转换分支。
- **前端对接影响**: 无，XLSX 上传解析更稳定。

### 4. 标准导入模板下载接口 (`api/upload.py`)
- **功能**: 提供 3 个 GET 端点下载标准 XLSX 模板，方便用户按模板填充数据后上传。
- **新增端点**:

  | 端点 | 下载文件名 | 模板列 |
  |---|---|---|
  | `GET /api/upload/template/transactions` | 资金流水导入模板.xlsx | 交易发生时间, 打款方 (账号/姓名), 收款方 (账号/姓名), 交易金额 (元), 支付方式, 交易备注 / 转账留言 |
  | `GET /api/upload/template/communications` | 通讯记录导入模板.xlsx | 联络时间, 发起方 (微信号/姓名), 接收方 (微信号/姓名), 聊天内容 |
  | `GET /api/upload/template/logistics` | 物流记录导入模板.xlsx | 发货时间, 快递单号, 发件人/网点, 收件人/地址, 寄件物品描述, 包裹重量(公斤) |

- **模板特性**:
  - 第 1 行：加粗表头（与解析器必填列校验完全一致）。
  - 第 2~3 行：示例数据（展示填写格式）。
  - 自适应列宽，可直接用于上传。
- **前端对接建议**:
  - 在导入页面增加"下载模板"按钮，调用对应端点下载。
  - 响应为 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`，前端可用 `window.open` 或 `<a download>` 触发下载。

### 5. 附带修复
- **上传端点 `case_no` 分支 `UnboundLocalError`**：删除了函数体内冗余的 `from models.database import Case`（顶层已导入），修复通过 `case_no` 参数上传时报错的问题。

---

## 日期: 2026-04-23

### 1. 数据一致性修复：删除案件时级联删除已生效 (`models/database.py`)
- **问题**: 删除案件后，关联流水/通讯/物流/线索可能残留。
- **修复**:
  - SQLite 连接已启用外键约束：`pragmas={"foreign_keys": 1}`。
  - 现有外键 `on_delete="CASCADE"` 现在可真正生效。
- **前端对接影响**:
  - 删除接口 `DELETE /api/cases/{case_id}` 的调用方式不变。
  - 行为变化：删除案件后，其关联数据会同步删除，前端应同步清理关联视图缓存。

### 2. 案件金额改为自动汇总，不再手工输入 (`services/case_service.py`, `api/cases.py`, `api/upload.py`)
- **问题**: `case.amount` 允许手工写入，可能与真实交易流水不一致。
- **修复**:
  - 新建案件时 `amount` 固定初始化为 `0`。
  - 新增金额重算逻辑：`CaseService.recalculate_case_amount(case_id)`，按当前 `transactions.amount` 求和回写案件金额。
  - 在交易导入接口中自动执行金额重算。
- **前端对接影响**:
  - `POST /api/cases` 和 `PUT /api/cases/{case_id}` 不再接收 `amount`。
  - 交易导入 `POST /api/upload/transactions` 成功响应新增：
    - `case_amount`: 重算后的案件金额（number）
  - 前端展示案件金额时，应以后端返回值为准，不再本地输入或缓存计算。

### 3. 嫌疑人/品牌改为自动推导，不再手工维护 (`services/case_service.py`, `api/cases.py`, `api/upload.py`)
- **问题**: `suspect_name`、`brand` 手工维护导致与证据数据易不一致。
- **修复**:
  - 新增推导逻辑：
    - `CaseService.infer_suspect_name(case_id)`
    - `CaseService.infer_brand(case_id)`
    - `CaseService.auto_update_inferred_fields(case_id)`
  - 嫌疑人推导策略：
    - 优先基于交易记录（收款方权重高于打款方，金额参与加权）；
    - 无交易时回退到通讯/物流主体高频统计。
  - 品牌推导策略：
    - 从交易备注、物流描述、通讯内容提取文本；
    - 使用品牌关键词库匹配，按命中次数选主品牌。
  - 创建案件时默认 `suspect_name = "待推导"`，后续由数据驱动更新。
  - 三类导入接口在保存后都会自动执行推导更新。

### 4. API 契约变化（前端重点）
- **案件创建** `POST /api/cases`
  - **旧请求体**: 可带 `case_no/suspect_name/brand/amount`
  - **新请求体**: 仅支持 `case_no`
  - 若传入未定义字段会被拒绝（`extra=forbid`，返回 422）。

- **案件更新** `PUT /api/cases/{case_id}`
  - `amount/suspect_name/brand` 不再允许通过该接口手工修改。
  - 当前接口用于保持兼容占位（存在性校验），推导字段请走自动推导链路。

- **新增手动触发推导接口** `POST /api/cases/{case_id}/infer-fields`
  - 用途：前端可在导入后主动触发一次推导刷新。
  - 返回：`case`（最新案件信息）+ `inference`（推导结果）。

- **导入接口成功响应新增字段**
  - `POST /api/upload/transactions`:
    - 新增 `case_amount`、`case_suspect_name`、`case_brand`
  - `POST /api/upload/communications`:
    - 新增 `case_suspect_name`、`case_brand`
  - `POST /api/upload/logistics`:
    - 新增 `case_suspect_name`、`case_brand`

### 5. 前端联调建议
- 创建案件页：提交字段改为仅 `case_no`。
- 导入完成后：直接使用导入响应中的 `case_amount/case_suspect_name/case_brand` 刷新页面。
- 列表/详情刷新策略：在导入后追加调用 `GET /api/cases/{case_id}`，避免页面与推导结果不同步。
- 对 422 统一提示："请求字段与最新后端契约不一致，请更新前端请求体"。

## 日期: 2026-04-22

### 0. 全站单账号密码保护（方案一） (`main.py`, `config/settings.py`)
- **功能**: 为后端接口增加统一密码保护，防止未授权直接访问 API。
- **修改**:
  - 新增 HTTP Basic 鉴权中间件（全局生效）。
  - 新增配置项：`auth_enabled`、`auth_username`、`auth_password`。
  - 默认放行白名单路径：`/`、`/health`、`/docs`、`/openapi.json`、`/redoc`。
  - 非白名单请求在未授权时返回 `401`，并带 `WWW-Authenticate: Basic` 头。
- **前端对接影响**:
  - 除白名单接口外，前端请求需统一携带 `Authorization: Basic <base64(username:password)>`。
  - 收到 `401` 时应提示重新输入账号密码。

### 1. 数据导入格式校验增强 (`services/upload_service.py`, `api/upload.py`, `streamlit_app.py`)
- **功能**: 当上传表格格式错误（缺少必填列、仅有表头无有效数据）时，向用户返回明确可读提示，避免笼统“导入失败”。
- **修改**:
  - 在 `services/upload_service.py` 新增 `TableFormatError` 异常类型。
  - 为三类导入（资金流水/通讯记录/物流记录）新增必填列校验：
    - 资金流水必填列：`交易发生时间`、`打款方`/`打款方 (账号/姓名)`、`收款方`/`收款方 (账号/姓名)`、`交易金额`/`交易金额 (元)`
    - 通讯记录必填列：`联络时间`、`发起方 (微信号/姓名)`、`接收方 (微信号/姓名)`、`聊天内容`
    - 物流记录必填列：`发货时间`、`发件人/网点`、`收件人/地址`
  - 增加“空数据校验”：表格有表头但无可解析有效行时，抛出格式错误提示。
  - 在 `api/upload.py` 将 `TableFormatError` 统一映射为 `HTTP 400`，`detail` 返回具体错误原因。
  - 在 `streamlit_app.py` 捕获 `TableFormatError`，前端页面展示：
    - `st.error("导入失败：...")`
    - `st.info("请按系统模板字段上传，确保表头列名与模板一致。")`
- **影响范围**:
  - 上传接口路径：`/api/upload/transactions`、`/api/upload/communications`、`/api/upload/logistics`
  - 前端导入页可直接基于错误文本进行用户提示，无需解析复杂异常栈。

### 2. 对前端的兼容性说明
- **成功场景**: 返回结构不变（`success/message/case_id/case_no/total_records/saved_records`），前端无需改动成功逻辑。
- **失败场景新增约定**:
  - 当为模板/列名/数据内容问题时，后端固定返回 `400`，且 `detail` 包含“表格格式错误”。
  - 前端可按以下规则处理：
    - `status === 400 && detail.includes("表格格式错误")` -> 显示“请检查模板列名/必填列”类提示。
    - 其他状态码继续走通用异常处理。

## 日期: 2026-04-20

### 1. 证据清单逻辑增强 (`services/ledger_service.py`)
- **功能**: 为证据清单汇总增加了深度的风险评估数据。
- **修改**:
  - 在 `get_evidence_inventory` 接口中，为通讯记录、交易备注、物流记录增加了 `score` (评分)、`severity_level` (风险等级) 和 `crime_type` (涉嫌罪名) 字段。
  - 引入了自动风险判定逻辑：
    - 评分 >= 8: **刑事犯罪**
    - 评分 >= 5: **民事侵权**
    - 评分 < 5: **行政违法**
  - 为所有证据项补齐了 `case_no` (案件编号)，方便前端进行跨案件索引。

### 2. 人员台账关联优化 (`services/ledger_service.py`)
- **功能**: 解决了人员台账中案件信息缺失的问题。
- **修改**:
  - 优化了 `get_person_ledger` 接口，通过全量扫描资金、通讯、物流记录，为每个人员自动匹配其涉及的最新案件编号。

### 3. 报告生成系统完善 (`api/report.py` & `services/ledger_service.py`)
- **功能**: 提高了分析报告的数据完整性。
- **修改**:
  - 优化了报告生成的内容模板，确保能正确拉取案件摘要、可疑线索计数和详细的证据分类清单。

### 4. 前后端接口适配 (`api/analyze.py`)
- **功能**: 确保 AI 分析结果在前端的正确展示。
- **修改**:
  - 调整了 `analyze_evidence` 接口的返回结构，统一了字段命名（如 `hit_keywords`），确保前端高亮插件能正常解析。

### 5. 数据库模型与数据安全
- **功能**: 标准化数据脱敏处理。
- **修改**:
  - 在后端逻辑中统一应用了手机号、身份证、银行卡的脱敏规则，确保展示层面的隐私合规。
