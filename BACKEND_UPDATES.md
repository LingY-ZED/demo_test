# 后端修改记录 (Backend Modification Records)

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
