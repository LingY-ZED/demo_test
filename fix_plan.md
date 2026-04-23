# 数据持久化问题修复计划

**制定时间**: 2026-04-23

## 概述

当前项目存在三个主要的数据持久化问题：
1. 级联删除未正确实现
2. Case表的amount字段应计算而非手动输入  
3. 嫌疑人、涉案品牌应由数据推导而非手动输入

---

## 问题详细分析

### 问题 1: 级联删除失效

**现象**：删除案件时，关联的Transaction、Communication、Logistics等表数据未被删除

**根本原因**：
- 数据库schema中设置了`on_delete="CASCADE"`（正确✓）
- delete_case()方法逻辑正确（正确✓）
- **但SQLite默认未启用外键约束支持** ❌
- 需要在数据库连接时启用外键支持

**影响范围**：
- `models/database.py` - db初始化
- 所有关联表：Transaction、Communication、Logistics、SuspiciousClue

**修复方案**：
```
修改database.py中的SqliteDatabase初始化：
- 添加init参数启用外键约束: `db = SqliteDatabase(..., pragmas={'foreign_keys': 1})`
- 确保所有数据库操作都在外键支持下执行
```

---

### 问题 2: Case.amount 字段设计错误

**现象**：
- API允许手动指定amount（`CaseCreate`中包含amount参数）
- 创建案件时需要预知涉案金额，但实际上应该从资金流水自动计算
- 导致amount与实际交易数据不一致

**当前流程**（错误）：
```
创建案件 → 手动输入amount → 添加交易流水
                          ↓
        amount值与实际交易数据无关
```

**正确流程**（应该）：
```
创建案件(amount=0或null) → 添加交易流水 → 自动汇总计算amount
```

**影响文件**：
- `models/database.py` - Case表设计
- `services/case_service.py` - create_case()、update_case()
- `api/cases.py` - CaseCreate、CaseUpdate、update端点

**修复方案**：
```
1. 修改models/database.py:
   - 将amount字段设为computed field或derived field
   - 或改为nullable，允许NULL表示需要重新计算

2. 修改services/case_service.py:
   - create_case()：移除amount参数或设为默认0
   - 新增方法：recalculate_case_amount(case_id) 
     * 从Transaction表求和所有case_id的金额
     * 更新Case.amount
   - 在添加transaction后自动调用recalculate_case_amount()

3. 修改api/cases.py:
   - CaseCreate：移除amount字段
   - CaseUpdate：移除amount字段
   - 新增端点：POST /api/cases/{case_id}/recalculate-amount

4. 修改Transaction相关的API和Service：
   - 在创建/更新/删除transaction时，自动调用recalculate_case_amount()
```

**实现细节**：
```python
# 伪代码示例
def recalculate_case_amount(case_id: int) -> Decimal:
    """从资金流水重新计算案件总金额"""
    transactions = Transaction.select().where(Transaction.case == case_id)
    total = sum(t.amount for t in transactions)
    case = Case.get_by_id(case_id)
    case.amount = total
    case.save()
    return total
```

---

### 问题 3: Case.suspect_name 和 brand 字段逻辑错误

**现象**：
- 需要在创建案件时手动指定suspect_name和brand
- 但实际上这些信息应该从业务数据推导而来（如从Person表或Transaction表）
- 导致数据源不统一，容易出现不一致

**当前流程**（错误）：
```
手动输入嫌疑人 → 创建案件 → 添加流水数据
  ↓
嫌疑人名称可能与实际交易人员不符
```

**正确流程**（应该）：
```
创建案件(默认值) → 添加交易/人员数据 → 自动推导嫌疑人和品牌信息
```

**推导规则**（需要明确）：

| 字段 | 推导源 | 推导规则 |
|------|------|---------|
| `suspect_name` | Person表 或 Transaction表 | 待定：是否有特定的角色标记？是否选择交易量最大的人？ |
| `brand` | Transaction/Logistics表 | 待定：从商品描述中提取？需要关键词匹配？ |

**影响文件**：
- `models/database.py` - Case表设计
- `services/case_service.py` - create_case()、update_case()
- `api/cases.py` - CaseCreate、CaseUpdate端点
- `services/` - 可能需要新增推导逻辑服务

**修复方案**：
```
1. 明确推导规则（需要与业务方确认）
   示例规则：
   - suspect_name：从Transaction中选择出现最频繁的payer或payee
   - brand：从Logistics的description字段中提取，或从Transaction的remark中提取
   - 或从Person表中查找角色为"嫌疑人"的记录

2. 修改models/database.py:
   - suspect_name改为nullable
   - brand改为nullable

3. 新增服务方法 services/case_service.py:
   - infer_suspect_name(case_id) → str or None
   - infer_brand(case_id) → str or None
   - auto_update_inferred_fields(case_id)

4. 修改API:
   - CaseCreate：移除suspect_name和brand（或设为可选）
   - 新增端点：POST /api/cases/{case_id}/infer-fields
   - 在添加transaction/logistics/person后自动调用

5. 实现逻辑示例：
   ```
   def infer_suspect_name(case_id):
       # 统计各人员出现次数
       transactions = Transaction.select().where(...)
       persons_count = Counter()
       for t in transactions:
           persons_count[t.payer] += 1
           persons_count[t.payee] += 1
       # 选择频率最高的作为嫌疑人
       if persons_count:
           return persons_count.most_common(1)[0][0]
       return None
   ```
```

---

## 修复优先级

| 优先级 | 问题 | 工作量 | 风险 |
|------|------|------|-----|
| **P0** | 级联删除失效 | 小 | 高 |
| **P1** | Amount字段计算逻辑 | 中 | 中 |
| **P2** | Suspect_name和brand推导 | 中 | 低 |

---

## 修复步骤清单

### 阶段1：修复级联删除 (P0)

- [ ] 修改 `models/database.py`
  - [ ] SqliteDatabase初始化添加foreign_keys pragma
  - [ ] 验证所有外键关系

- [ ] 测试删除逻辑
  - [ ] 单元测试：删除Case后检查Transaction是否被删除
  - [ ] 单元测试：删除Case后检查所有关联表数据

---

### 阶段2：修复Amount字段 (P1)

- [ ] 修改 `models/database.py`
  - [ ] 确认amount字段设计

- [ ] 修改 `services/case_service.py`
  - [ ] 修改create_case()方法
  - [ ] 修改update_case()方法  
  - [ ] 新增recalculate_case_amount()方法
  - [ ] 修改transaction创建/删除逻辑

- [ ] 修改 `api/cases.py`
  - [ ] 更新CaseCreate模型
  - [ ] 更新CaseUpdate模型
  - [ ] 移除amount相关参数

- [ ] 修改 `services/` 中的transaction相关服务
  - [ ] 在add_transaction时调用recalculate
  - [ ] 在delete_transaction时调用recalculate

- [ ] 更新测试
  - [ ] 修改test_case_service.py
  - [ ] 修改test_integration.py

---

### 阶段3：推导嫌疑人和品牌 (P2)

- [ ] 明确推导规则（与业务方沟通）
  - [ ] 确定suspect_name的推导算法
  - [ ] 确定brand的推导算法

- [ ] 修改 `models/database.py`
  - [ ] 更新Case表字段nullable设置

- [ ] 新增 `services/case_infer_service.py`（或在case_service中添加方法）
  - [ ] 实现infer_suspect_name()
  - [ ] 实现infer_brand()
  - [ ] 实现auto_update_inferred_fields()

- [ ] 修改 `api/cases.py`
  - [ ] 更新CaseCreate模型
  - [ ] 更新CaseUpdate模型
  - [ ] 新增推导端点

- [ ] 修改相关的添加数据API
  - [ ] transaction API中添加自动推导调用
  - [ ] logistics API中添加自动推导调用

- [ ] 更新测试

---

## 潜在影响

### 数据库迁移
- 新增字段nullable：需要迁移现有数据
- 建议：删除现有intellectual_property.db，重新初始化

### API变更（Breaking Changes）
- CaseCreate不再接受amount、suspect_name、brand
- 现有客户端要更新请求体

### 前端适配
- 案件创建流程可能需要调整（可能需要两步：先创建案件，后添加数据）
- 或延迟显示嫌疑人、品牌等信息直到数据完整

---

## 关键技术点

1. **SQLite外键支持**
   ```python
   db = SqliteDatabase(path, pragmas={'foreign_keys': 1})
   ```

2. **Peewee级联删除**
   ```python
   case = ForeignKeyField(Case, backref="transactions", on_delete="CASCADE")
   ```

3. **事务处理**
   - 更新amount字段时考虑事务一致性
   - 修改多条关联数据时使用transaction

4. **触发器替代方案**
   - SQLite支持触发器，可考虑用触发器自动更新amount
   - 或在应用层实现

---

## 审查清单

修复完成后须验证：

- [ ] 级联删除正常工作
- [ ] Amount字段自动计算准确
- [ ] Suspect_name和brand正确推导
- [ ] API文档已更新
- [ ] 单元测试通过率100%
- [ ] 集成测试通过
- [ ] 数据一致性检查无误

---

## 参考文档

- Peewee ORM: https://docs.peewee-orm.com/
- SQLite Foreign Keys: https://www.sqlite.org/foreignkeys.html
- Project: `c:\Code\Site\demo_test`
- Current DB: `data/intellectual_property.db`
