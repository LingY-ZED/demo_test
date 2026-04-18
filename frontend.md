# 火眼智擎—汽配领域知产保护分析助手 前端开发文档

## 项目概述

后端API服务，精准靶向汽配领域侵犯知识产权犯罪的智能分析。前端基于后端API实现交互界面。

**核心要求：分析结果需展示判断依据和证据出处**（如：命中了哪个关键词、来自哪条聊天记录等）

---

## 基础信息

- **API地址**: `http://localhost:8000`
- **Swagger文档**: `http://localhost:8000/docs`
- **基础路径**: `/api`

---

## 数据结构

### 案件（cases）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 案件ID |
| case_no | string | 案件编号（唯一） |
| suspect_name | string | 嫌疑人姓名 |
| brand | string | 涉案品牌 |
| amount | float | 涉案金额 |
| created_at | datetime | 创建时间 |

### 可疑线索（suspicious_clues）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 线索ID |
| case_id | int | 所属案件ID |
| clue_type | string | 线索类型（价格异常/主观明知/角色异常） |
| evidence_text | string | 证据原文 |
| hit_keywords | string | 命中关键词（逗号分隔） |
| score | int | 评分（0-10） |
| crime_type | string | 涉嫌罪名 |
| severity_level | string | 严重程度（刑事犯罪/民事侵权/行政违法） |

### 资金流水（transactions）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 交易ID |
| case_id | int | 案件ID |
| transaction_time | datetime | 交易时间 |
| payer | string | 打款方 |
| payee | string | 收款方 |
| amount | float | 交易金额 |
| payment_method | string | 支付方式 |
| remark | string | 交易备注 |

### 通讯记录（communications）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 记录ID |
| case_id | int | 案件ID |
| communication_time | datetime | 联络时间 |
| initiator | string | 发起方 |
| receiver | string | 接收方 |
| content | string | 聊天内容（需展示原文） |

### 物流记录（logistics）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 记录ID |
| case_id | int | 案件ID |
| shipping_time | datetime | 发货时间 |
| tracking_no | string | 快递单号 |
| sender | string | 发件人 |
| sender_address | string | 发件地址 |
| receiver | string | 收件人 |
| receiver_address | string | 收件地址 |
| description | string | 物品描述 |
| weight | float | 包裹重量 |

---

## API接口详情

### 1. 数据导入接口

#### 上传资金流水
```
POST /api/upload/transactions
Content-Type: multipart/form-data

参数:
- file: Excel/CSV文件
- case_id: int (可选)
- case_no: string (可选，case_id未提供时使用)

支持字段：交易时间、打款方、收款方、金额、支付方式、备注
```

#### 上传通讯记录
```
POST /api/upload/communications
Content-Type: multipart/form-data

参数:
- file: Excel/CSV文件
- case_id: int (可选)
- case_no: string (可选)

支持字段：联络时间、发起方、接收方、聊天内容
```

#### 上传物流记录
```
POST /api/upload/logistics
Content-Type: multipart/form-data

参数:
- file: Excel/CSV文件
- case_id: int (可选)
- case_no: string (可选)

支持字段：发货时间、快递单号、发件人、发件地址、收件人、收件地址、物品描述、重量
```

**返回示例:**
```json
{
  "success": true,
  "message": "成功导入10条资金流水",
  "case_id": 1,
  "case_no": "CASE001",
  "total_records": 10,
  "saved_records": 10
}
```

---

### 2. 案件管理接口

#### 案件列表
```
GET /api/cases
Query参数:
- case_no: string (可选，模糊匹配)
- suspect_name: string (可选，模糊匹配)
- brand: string (可选，模糊匹配)
- limit: int (默认100，最大500)
- offset: int (默认0)
```

#### 案件详情
```
GET /api/cases/{case_id}

返回: 案件详情包含关联的资金流水、通讯记录、物流记录、可疑线索
```

#### 创建案件
```
POST /api/cases
Body:
{
  "case_no": "CASE001",
  "suspect_name": "张三",
  "brand": "博世",
  "amount": 50000
}
```

#### 更新案件
```
PUT /api/cases/{case_id}
Body:
{
  "suspect_name": "新名字",
  "brand": "米其林",
  "amount": 60000
}
```

#### 删除案件
```
DELETE /api/cases/{case_id}
```

---

### 3. 可疑线索接口

#### 获取案件可疑线索
```
GET /api/cases/{case_id}/suspicious

返回示例:
[
  {
    "id": 1,
    "clue_type": "主观明知",
    "evidence_text": "这批货你别声张，不是原厂的",
    "hit_keywords": "不是原厂",
    "score": 8,
    "crime_type": "涉嫌销售假冒注册商标的商品罪",
    "severity_level": "刑事犯罪"
  }
]
```

#### 线索详情
```
GET /api/clues/{clue_id}

返回示例:
{
  "id": 1,
  "clue_type": "主观明知",
  "evidence_text": "这批货你别声张，不是原厂的",
  "hit_keywords": ["不是原厂"],
  "score": 8,
  "crime_type": "涉嫌销售假冒注册商标的商品罪",
  "severity_level": "刑事犯罪"
}
```

---

### 4. 智能分析接口

#### 分析单条证据
```
POST /api/analyze/evidence
Body:
{
  "evidence_text": "这批高仿货别声张，老规矩处理",
  "evidence_type": "communication"
}

返回示例:
{
  "price_analysis": {
    "is_anomaly": true,
    "price_ratio": 0.35,
    "suggestion": "价格低于正品50%以上"
  },
  "subjective_knowledge": {
    "score": 8,
    "level": "高度可疑",
    "hit_keywords": ["高仿", "别声张", "老规矩"],
    "category_counts": {
      "直接承认假冒类": 1,
      "回避性话术类": 2
    }
  },
  "key_entities": {
    "names": ["张三"],
    "roles": ["销售者"],
    "contacts": ["13812345678"],
    "amounts": ["28000"]
  },
  "crime_type": "涉嫌销售假冒注册商标的商品罪"
}
```

#### 全案分析
```
POST /api/analyze/case/{case_id}

返回示例:
{
  "case_id": 1,
  "case_no": "CASE001",
  "chain_analysis": {
    "upstream": [...],
    "downstream": [...],
    "core_suspects": [...],
    "role_analysis": {
      "producers": ["李某"],
      "sellers": ["张某"]
    }
  }
}
```

#### 分析关键主体
```
GET /api/analyze/actors/{case_id}
```

---

### 5. 关联分析接口

#### 单案上下游关系图
```
GET /api/relations/chain/{case_id}

返回示例:
{
  "upstream": [
    {"name": "供货商A", "amount": 50000, "role": "上游供货商"}
  ],
  "downstream": [
    {"name": "买家B", "amount": 30000, "role": "下游买家"}
  ],
  "core_suspects": [
    {"name": "张某", "role": "核心嫌疑人", "amount": 80000}
  ],
  "role_analysis": {
    "producers": ["李某"],
    "sellers": ["张某"]
  }
}
```

#### 跨案关联拓扑
```
GET /api/relations/cross-case

返回跨案关联数据，用于多案网络图展示
```

#### 累犯检测
```
GET /api/relations/recidivism/{person_name}

返回示例:
{
  "person_name": "张某",
  "is_recidivist": true,
  "previous_cases": ["CASE001", "CASE003"],
  "suggestion": "两年内同类违法行为"
}
```

#### 获取上下游列表
```
GET /api/relations/upstream/{case_id}
GET /api/relations/downstream/{case_id}
GET /api/relations/core-suspects/{case_id}

返回示例 (以upstream为例):
[
  {
    "name": "某供货商",
    "total_out_amount": 50000.0,
    "counterparties": ["核心嫌疑人A"],
    "evidence": {
      "transactions": [
        {"type": "付款", "counterparty": "核心嫌疑人A", "amount": 20000.0, "time": "2024-01-15 10:30:00"}
      ],
      "logistics": [
        {"type": "发货", "counterparty": "核心嫌疑人A", "description": "制动片一批", "time": "2024-01-16 14:00:00"}
      ]
    }
  }
]

返回示例 (core-suspects):
[
  {
    "name": "核心嫌疑人A",
    "role": "销售者",
    "crime_type": "涉嫌销售假冒注册商标的商品罪",
    "behavior_role": "销售者",
    "keyword_roles": ["销售者"],
    "evidence": {
      "transactions": [...],
      "logistics": [...],
      "communications": [
        {
          "type": "发起",
          "counterparty": "下游买家B",
          "content": "这批货是高仿的，质量没问题",
          "hit_keywords": ["高仿"],
          "role_hint": "销售者"
        }
      ]
    }
  }
]
```

---

### 6. 数据台账接口

#### 人员台账
```
GET /api/ledger/persons
Query参数:
- role: string (可选，角色筛选)
- limit: int (默认100)
- offset: int (默认0)

返回示例:
[
  {
    "id": 1,
    "name": "张三",
    "role": "核心销售商",
    "is_authorized": false,
    "subjective_knowledge_score": 8,
    "illegal_business_amount": 85000,
    "linked_cases": 2
  }
]
```

#### 交易台账
```
GET /api/ledger/transactions
Query参数:
- case_no: string (可选)
- payer: string (可选)
- payee: string (可选)
- start_date: string (可选)
- end_date: string (可选)
- limit: int
- offset: int
```

#### 证据清单
```
GET /api/ledger/evidence/{case_id}

返回示例:
{
  "evidence_list": [
    {
      "type": "通讯记录",
      "id": 1,
      "time": "2024-01-15 10:30:00",
      "initiator": "张某",
      "receiver": "李某",
      "content": "这批高仿货别声张",
      "hit_keywords": ["高仿", "别声张"],
      "score": 8,
      "crime_type": "涉嫌销售假冒注册商标的商品罪"
    }
  ],
  "communication_evidence_count": 5,
  "price_anomaly_evidence_count": 2,
  "logistics_evidence_count": 3
}
```

---

### 7. 数据导出接口

#### 导出CSV
```
GET /api/export/csv
Query参数:
- type: string (必填，transactions/persons/evidence)
- case_id: int (可选，evidence类型必填)
- case_no: string (可选)

返回: CSV文件下载
```

---

### 8. 报告生成接口

#### 生成分析报告
```
POST /api/report/generate
Body:
{
  "case_id": 1
}

返回示例:
{
  "success": true,
  "report_id": "report_CASE001_20240115103000.txt",
  "download_url": "/api/report/download/report_CASE001_20240115103000.txt",
  "message": "报告生成成功"
}
```

#### 下载报告
```
GET /api/report/download/{filename}
```

#### 获取报告状态
```
GET /api/report/{case_id}
```

---

## 页面功能映射

### 1. 数据看板页面

**统计卡片** (调用 `/api/cases` 汇总统计):
- 案件总数
- 可疑线索数
- 累计涉案金额
- 重点布控人员

**图表**:
- 案件趋势 - 从 `/api/cases` 按时间统计
- 品牌分布 - 从 `/api/cases` 按brand分组
- 金额走势 - 从 `/api/ledger/transactions` 汇总

### 2. 案件管理页面

**搜索** - 调用 `/api/cases`:
- 案件编号
- 嫌疑人姓名
- 涉案品牌

**案件详情弹窗** - 调用 `/api/cases/{id}`:
- 顶部信息区：嫌疑人、涉案产品、涉案金额、线索数、关联案件数
- 聊天记录：来自 `communications`，命中关键词高亮
- 交易记录：来自 `transactions`，金额高亮
- 人物关系：来自 `/api/relations/chain/{case_id}`
- 导出报告按钮：调用 `/api/report/generate`

### 3. 智能证据解析页面

**输入区** - 调用 `POST /api/analyze/evidence`:
- 输入待分析文本
- 选择证据类型

**输出区**:
- 价格异常判定（返回 `price_analysis`）
- 主观明知证据（返回 `subjective_knowledge`，包含原文引用和命中关键词）
- 关键主体提取（返回 `key_entities`）

**底部按钮**:
- "生成初步分析报告" - 调用 `POST /api/report/generate`
- "转入关联图谱分析" - 跳转到关联分析页面

### 4. 关联分析页面

**上下游关系图** - 调用 `/api/relations/chain/{case_id}`:
- 节点：上游供货商、核心嫌疑人、下游买家、仓储/物流
- 连线：供货、销售、资金、物流

**跨案关联拓扑** - 调用 `/api/relations/cross-case`:
- 多案件网络图

**右侧情报面板** - 调用 `/api/relations/chain/{case_id}` 和 `/api/ledger/persons`:
- 节点点击后显示详细信息

### 5. 数据台账页面

**人员台账** - 调用 `/api/ledger/persons`:
- 表格展示
- 联系方式脱敏显示（前端需调用 `utils/masking.py` 中的脱敏函数）

**交易台账** - 调用 `/api/ledger/transactions`:
- 表格展示

**导出功能** - 调用 `/api/export/csv`:
- 导出CSV/Excel

---

## 敏感信息脱敏规则

前端需对以下信息进行脱敏展示：

| 类型 | 原始示例 | 脱敏后 |
|------|----------|--------|
| 手机号 | 13812345678 | 138****5678 |
| 身份证号 | 110101199001011234 | 110101**********1234 |
| 银行卡号 | 6225123456789012345 | 6225****1234 |
| 邮箱 | zhangsan@example.com | z***@example.com |
| 姓名 | 张三 | 张*（保留首字） |

后端 `utils/masking.py` 提供脱敏函数，前端可直接调用或参考实现。

---

## 敏感词分类（用于高亮显示）

| 类别 | 说明 | 权重 |
|------|------|------|
| 直接承认假冒类 | 高仿、一比一、复刻、原单 | ×5 |
| 回避性话术类 | 别声张、老规矩、心里有数 | ×4 |
| 暗示非正品类 | 特殊渠道、原厂品质、剪标、水货 | ×2 |
| 销售行为类 | 出货、拿货、批发、代理 | ×1 |
| 生产/贴牌类 | 贴牌、打标、代工、仿制 | ×1 |
| 授权状态类 | 没授权、没有授权书 | ×1 |

---

## 主观明知评分规则

评分公式：
- 类别1命中 × 5（上限10分）
- 类别2命中 × 4（上限8分）
- 类别3命中 × 2（上限4分）
- 类别4-6命中各 ×1
- 价格低于正品50%以上 +3分
- 无授权证明 +3分
- 无正规进货凭证 +2分

评分等级：
- 8-10分：高度可疑
- 5-7分：中度可疑
- 0-4分：低度可疑

---

## 刑事门槛参考

| 罪名 | 违法所得门槛 | 非法经营门槛 |
|------|-------------|-------------|
| 假冒注册商标罪 | ≥3万 | ≥5万 |
| 假冒两种以上商标 | ≥2万 | ≥3万 |
| 情节特别严重 | ≥15万 | ≥25万 |

---

## 错误码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 注意事项

1. **证据展示**：分析结果必须展示判断依据和证据出处，如命中关键词、原文引用
2. **数据脱敏**：联系方式等敏感信息必须脱敏展示
3. **文件上传**：支持Excel(.xlsx/.xls)和CSV格式
4. **分页查询**：列表接口支持limit/offset分页
5. **关联数据**：案件详情包含完整的资金流水、通讯记录、物流记录
