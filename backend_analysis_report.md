# 火眼智擎 (FireEye) 后端项目分析报告

该报告针对位于 `d:\backEnd\demo_test` 的后端项目进行了全面的架构、功能和数据层面分析。

## 1. 核心架构与技术栈

该项目是一个专门针对**汽配领域侵犯知识产权犯罪的智能分析平台**。
- **框架**: Python 3.8+ / FastAPI
- **ORM**: Peewee
- **数据库**: SQLite (位于 `data/intellectual_property.db`)
- **服务器**: Uvicorn
- **核心组件依赖**: `pydantic-settings` (配置), `pandas` & `openpyxl` (数据处理/Excel), `python-docx` (报告生成)。

## 2. 核心功能模块

系统主要包括以下业务功能：
- **数据导入**: 支持通过 Excel/CSV 导入大批量涉案数据（资金流水、通讯记录、物流记录等）。
- **案件管理**: 提供案件信息的基础 CRUD 维护。
- **智能分析**: 包括主观明知评分计算（基于假冒承认、回避、暗示等关键词计分）、敏感词全库比对（7大类233+敏感词汇）以及角色推断等。
- **关联分析**: 支持案件上下游产业链链路追踪、跨案人员关联侦查及累犯监测。
- **数据台账**: 聚合生成人员台账与高频交易台账。
- **报告与导出**: 提供 CSV 格式的数据导出以及详尽的分析报告（Word/TXT）自动生成。

## 3. 数据库结构 (Schema) 与状态

数据模型存放在 `models/database.py` 中，定义了 6 张核心数据表：

### 3.1 实体表与字段

1. **`Case` (案件表)**
   - 字段: `id`, `case_no` (案件编号), `suspect_name` (嫌疑人), `brand` (涉案品牌), `amount` (涉案金额), `created_at` (创建时间)
2. **`Person` (人员表)**
   - 字段: `id`, `name`, `role` (角色), `is_authorized` (是否授权), `authorization_proof` (授权证明), `subjective_knowledge_score` (主观明知评分), `illegal_business_amount` (非法经营数额), `linked_cases` (关联案件数)
3. **`Transaction` (资金流水表)**
   - 字段: `id`, `case_id` (外键), `transaction_time`, `payer` (打款方), `payee` (收款方), `amount`, `payment_method`, `remark`
4. **`Communication` (通讯记录表)**
   - 字段: `id`, `case_id` (外键), `communication_time`, `initiator` (发起方), `receiver` (接收方), `content` (聊天内容)
5. **`Logistics` (物流记录表)**
   - 字段: `id`, `case_id` (外键), `shipping_time`, `tracking_no` (单号), `sender`, `sender_address`, `receiver`, `receiver_address`, `description`, `weight`
6. **`SuspiciousClue` (可疑线索表)**
   - 字段: `id`, `case_id` (外键), `clue_type` (线索类型), `evidence_text` (证据原文), `hit_keywords` (命中关键词), `score` (评分), `crime_type` (涉嫌罪名), `severity_level` (严重程度)

### 3.2 现有数据状态验证

通过扫描 `data/intellectual_property.db` 证实数据库文件已创建（约 48KB），当前包含的数据如下：
- `cases` (案件记录): **3 条**
- `persons` (人员), `transactions` (资金), `communications` (通讯), `logistics` (物流), `suspicious_clues` (线索): **均为 0 条**

> **结论**: 系统已经进行了部分初始化并录入了几个测试案件主体，但尚未导入任何相关的明细线索、资金或物流数据。

## 4. API 接口映射表

路由模块通过 `main.py` 注册，功能接口分发在不同的 `api/` 子路由文件中。完整的端点分类如下：

| 模块分类 | 路径路由前缀 | 主要功能描述 |
| --- | --- | --- |
| **基础服务** | `/`, `/health` | 服务存活检测、健康检查 |
| **数据导入** | `/api/upload/*` | 接收各类型 Excel/CSV 文件的批量上传解析 |
| **案件管理** | `/api/cases/*` | 案件的创建、读取、更新、删除操作 |
| **线索查询** | `/api/clues/*` | 查询和管理独立线索 |
| **智能分析** | `/api/analyze/*` | 提交证据分析任务、运行全案智能扫描分析 |
| **关联侦查** | `/api/relations/*` | 分析关系链(上下游、跨案联系、核心嫌疑人) |
| **数据台账** | `/api/ledger/*` | 获取人员明细、交易汇总、高频联系人及证据清单 |
| **数据导出** | `/api/export/*` | 结构化台账数据的 CSV 文件下载 |
| **报告生成** | `/api/report/*` | 触发报告生成任务、查询状态并下载归档文件 |

## 5. 其他关注点
- **数据脱敏规范**: 系统核心算法部分要求在前端或导出时对姓名、手机号、身份证、银行卡及邮箱等进行 `*` 号脱敏。
- **跨域策略 (CORS)**: `main.py` 内部已配置放行所有域名 `allow_origins=["*"]`，这使得可以从独立的纯静态前端进行调用。

## 6. 数据流转深度剖析 (以通讯记录上传为例)
针对 `POST /api/upload/communications` 接口的数据流动机制如下：

1. **存储机制 (Storage)**
   - 文件上传后，内容将通过 `await file.read()` 以字节流形式**直接驻留于服务器内存**。
   - 系统不会在硬盘上持久化（如存储到 `uploads/` 等目录）任何原始上传的 Excel 或 CSV 文件，有效节约了磁盘空间并规避敏感文件残留风险。

2. **数据处理流 (Data Pipeline)**
   - **载入与提取**：内存中的字节流由 `pandas` 直接读取为 DataFrame。
   - **标准化解析**：由业务逻辑层 `UploadService` 将千奇百怪的表头清洗映射为内部标准字段（联络时间、发起方、接收方、内容）。
   - **清洗脱敏**：由 `CleanService` 进行去重、脏数据清洗。
   - **入库存储**：绑定前端指定的 `case_id`，利用 Peewee ORM 将所有条目逐一写入 SQLite `communications` 通讯记录表中。

3. **数据应用场景 (Output & Utilization)**
   该接口本身不输出记录明细，只返回成功条数的统计。录入的通讯数据将在以下模块中被“输出”和应用：
   - **智能研判** (`/api/analyze/*`)：使用系统关键词库检索聊天记录（如“逼真”、“高仿”等词），命中的条目会被提取保存到 `suspicious_clues` (可疑线索表)。
   - **关系链推演** (`/api/relations/*`)：提取发起方与接收方信息，描绘出犯罪团伙的上下游人员网状图。
   - **研判报告生成** (`/api/report/*`)：作为核心电子证据，随同案件信息一并被打包打印到自动生成的 Word/TXT 报告中供执法人员查阅。

## 7. 全局数据生命周期与流转架构 (接口 -> 程序 -> 表 -> 输出)

为了彻底厘清系统的运作逻辑，我们将从宏观角度梳理整个系统的“输入、流转/处理、输出”生命周期：

### 7.1 数据输入层 (Input)
数据进入系统的途径主要分为两大类：结构化文件导入与业务表单提交。

1. **大批量数据导入 (`/api/upload/*`)**
   - **输入数据**: 含有资金流水、通讯记录或物流发货信息的 Excel/CSV 文件。
   - **程序侧逻辑**: 接收文件流后直接驻留内存，由 `pandas` 引擎进行预解析，通过 `UploadService` 将差异化的表头重组为系统标准字段，随后由 `CleanService` 执行去重、空值过滤等清洗动作。
   - **落库目标表**: 流向 `transactions`（资金流水表）、`communications`（通讯记录表）以及 `logistics`（物流记录表）。
2. **案件与手工线索创建 (`/api/cases`, `/api/clues`)**
   - **输入数据**: JSON 格式的案件基本要素（嫌疑人、品牌、涉案金额等）以及办案人员手工补充的独立线索。
   - **程序侧逻辑**: `FastAPI` 直接接收并校验 Pydantic Schema，通过 ORM 直接映射为数据库对象。
   - **落库目标表**: 流向 `cases`（案件表）、`persons`（人员表，此时初始化核心嫌疑人）以及 `suspicious_clues`（可疑线索表）。

### 7.2 数据处理与流转层 (Processing & Internal Flow)
数据入库后，处于静止状态，真正让数据流动起来产生业务价值的是“智能分析”模块。

1. **智能研判流转 (`/api/analyze/*`)**
   - **数据抓取**: `AnalyzeService` 从数据库中提取上述静止的 `transactions`、`communications` 和 `logistics` 数据。
   - **计算与判定机制**:
     - **NLP与关键词匹配**: 遍历通讯录音或文本，与系统内置的 233+ 敏感词库进行全量比对。
     - **金融逻辑校验**: 累加资金流水中非正规渠道的支付金额，结合品牌正品价，计算是否属于“远低于市场价”。
     - **评分流转**: 根据命中情况，按照“主观明知评分体系”进行权重打分（例如命中“直接承认假冒”加 5 分）。
   - **处理后落库**: 分析结果**不直接输出给用户**，而是沉淀回流到 `suspicious_clues` 表（固化为新的可疑线索）并更新 `persons` 表中对应人员的 `subjective_knowledge_score` (主观明知评分) 和 `illegal_business_amount` (非法经营金额)。

### 7.3 数据输出层 (Output)
经过处理与结构化关联的数据，在以下四大场景对外输出，赋能办案研判：

1. **关系网络输出 (`/api/relations/*`)**
   - **流出源**: `transactions`（通过打款/收款方）、`communications`（通过发起/接收方）。
   - **输出形式**: 在程序内通过 Graph 算法合并重叠的节点（人员），最后以 JSON 格式输出点、边拓扑数据，供前端渲染“上下游资金/通讯网状图”。
2. **数据台账输出 (`/api/ledger/*`)**
   - **流出源**: `persons` 以及聚合统计后的明细表。
   - **输出形式**: 对人员和高频交易者进行 `GROUP BY` 与 `SUM` 统计，输出人员角色结构清单、高频交易监控名单等 JSON 数据给前端表格展示。
3. **明细导出 (`/api/export/*`)**
   - **流出源**: 任意明细表与台账视图。
   - **输出形式**: 程序利用 `pandas` 将数据库查询集重新逆向转化为 CSV/Excel 二进制流，通过 `FileResponse` 触发浏览器的文件下载机制。
4. **结案报告输出 (`/api/report/*`)**
   - **流出源**: 基于 `case_id` 抓取该案件下的基本信息 (`cases`)、关键人物涉案金额及主观明知评分 (`persons`) 以及被系统抓取到的所有高价值证据 (`suspicious_clues`)。
   - **输出形式**: `ReportService` 提取这些核心数据后，注入到预设的 `python-docx` 模板中。这标志着系统数据的最终形态输出——一份排版完整、可直接用作审查起诉辅助材料的 Word/TXT 研判报告文件（以文件下载形式给到办案人员）。
