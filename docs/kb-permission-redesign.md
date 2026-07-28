# 知识库权限系统重构方案（库级：个人 + 部门统一授权）

> 状态：方案草稿，待评审。语义决策点已记录但未定稿。
> 范围：仅涉及**库级权限**（谁能进库、进来能干嘛）。文档级 `scope`（public/department/private）不在此次重构内，但会复用其部门树工具并统一方向语义。

---

## 1. 背景与目标

### 现状
- 库级权限由 `kb_permission` 表承载，结构为 `(kb_id, user_id, level)`，**仅认用户、不认部门**。
- 文档级 `scope` 已有 `department` 维度（`doc_scope_clause` + `compute_visible_dept_ids`），但与库级是两套孤立逻辑。
- 权限计算散落在多个函数，且**完全没有"个人 vs 部门"合并规则**。

### 目标（完美闭环）
1. 统一"授权主体"概念：授权既可给个人，也可给部门。
2. 单一计算函数算出某人对某库的有效权限，所有读路径共用，消除散落。
3. 合并语义明确定义（见 §3.3，待定）。
4. 前端提供"有效权限预览"，把隐式合并显式展示，消除"隐藏逻辑让人困惑"的体感。
5. 部门/人员变动实时生效，无需手动维护。

---

## 2. 当前问题点归纳（隐患清单）

### 2.1 读路径散落，改必漏
权限计算分布在三处，逻辑重复且易不一致：
- `get_kb_permission_level`（security.py:209）：只查 `kb_permission`。
- `get_accessible_kb_ids`（security.py:258）：只查 `kb_permission`。
- `get_knowledge_bases` 列表聚合（bases.py:89-111，`perm_map`/`strict_kbs`）：只算个人记录。
> 后果：任何一处漏改，就会出现"库存在但列表看不见""能进但权限算错"等诡异现象。

### 2.2 库级无部门维度
`KBPermission` 只有 `user_id`，无法"整个部门一键授权"，只能挨个加人，新人入职需手动补。

### 2.3 合并语义缺失（最关键）
个人授权与部门授权冲突时（如个人 view、部门 admin），系统无任何定义。这是产品决策，不是技术问题，必须先定。

### 2.4 覆盖式写入与 admin 校验冲突
`set_kb_members`（bases.py:298）是覆盖式写入（先删后插），且"至少保留 1 个 admin"校验**只查个人列表**。若某库全靠部门授权提供 admin，该校验会误报或绕过。

### 2.5 部门树方向语义不统一
- 文档 `scope=department`：`compute_visible_dept_ids` 是"本人部门 + 所有后代"（**向下**展开）——父部门能看到子部门文档。
- 库级部门授权若复用需明确方向：授权给父部门，应让子部门继承（向上链匹配）。两方向恰好互补但不同，UI 必须标注清楚，否则认知混乱。

### 2.6 部门/人员变动的级联语义不清
- 用户转部门：其在旧部门授权下的库权限是否立即消失？
- 部门被删：其授权记录如何处理？
当前代码无定义。

---

## 3. 重构方案

### 3.1 统一授权模型（取代 `kb_permission`）

新建表 `kb_grant`：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| kb_id | FK → knowledge_base | 知识库 |
| principal_type | str('user'\|'dept') | 授权主体类型 |
| principal_id | UUID | user.id 或 department.id |
| level | str(view\|edit\|admin) | 权限级别 |
| created_at | datetime | |

唯一约束：`(kb_id, principal_type, principal_id)`，防止重复授权。
外键级联：`principal_id` 对应 User/Department 删除时 `ON DELETE CASCADE`，自动清理孤儿授权。

**替代关系**：删除旧 `kb_permission` 表，数据全部迁入 `kb_grant`（`principal_type='user'`）。

### 3.2 统一计算函数 `compute_kb_effective_level(db, kb_id, user) -> str | None`

```
if is_super_admin(user): return 'admin'          # 短路，保持不变

dept_chain = dept_ancestors(user.department_id)  # 本人部门 + 所有祖先（向上链）

grants = SELECT level FROM kb_grant
         WHERE kb_id = ? AND (
           (principal_type='user' AND principal_id = user.id)
           OR (principal_type='dept' AND principal_id IN dept_chain)
         )

if no grants:
    if kb has ANY grant record: return None       # 严格库，未授权
    else: return 'view'                            # 遗留开放库，隐式只读
return effective_merge(grants)                     # 见 §3.3
```

所有读路径（`get_kb_permission_level`、`get_accessible_kb_ids`、列表聚合）统一调用此函数，列表聚合改为一次性 `GROUP BY kb_id` 收集个人 + 部门授权后内存合并，保持 O(1) 查询次数。

### 3.3 合并语义（**待定，两种均记录**）

`effective_merge(grants)` 如何对个人与部门授权取最终 level：

- **方案 A：个人显式优先**
  若存在个人直接授权，直接采用（哪怕低于部门最高）；否则取部门最高。
  - 利：显式意图压过隐式继承，更安全；可精确把某人从部门继承的高权限压下来。
  - 弊：若默认全员靠部门为 admin，想让某人仅 view，需显式给他一条 view（有意的、可预期）。

- **方案 B：取最高级**
  个人与部门授权取 level 最大值。
  - 利：部门提权顺畅，无需逐人降权。
  - 弊：无法单独压制个体——只要他在被授权部门，管理员就压不住他。

> **决策状态：未定。** 待评审确认。倾向方案 A（权限治理上"显式 > 隐式继承"更安全）。

### 3.4 部门树方向统一

抽出部门树工具（集中、避免方向写错）：
- `dept_ancestors(dept_id)`：本人部门 + 所有祖先（**向上**）——库授权匹配用。
- `dept_descendants(dept_id)`：本人部门 + 所有后代（**向下**）——文档 `scope=department` 复用。

库授权语义：授权给部门 D → D 及其**下级**用户可进（查询时用 `dept_ancestors` 匹配）。与文档 scope 方向互补但各自自洽，前端文案明确标注。

### 3.5 有效权限预览（前端闭环关键）

管理成员弹窗新增"有效权限预览"区：
- 列出库内所有可访问用户（个人直接授权 ∪ 部门授权覆盖的人）。
- 每行展示最终 `level` + 来源标签（「直接」/「部门继承：XX部」）。
- 让管理员直观看到合并结果，消灭隐藏逻辑。

---

## 4. 数据迁移

1. Alembic（或项目现有手动迁移机制，参照 `u10dropcompany.py`）新建 `kb_grant` 表。
2. 迁移脚本：将 `kb_permission` 全部行改写为 `kb_grant(principal_type='user', principal_id=user_id)`，保留 level。
3. 删除旧 `kb_permission` 表。
4. **上线前必须备份数据库**；提供回滚脚本（重建 `kb_permission` + 反向写入）。
5. 迁移属上生产动作，需用户许可后执行。

---

## 5. 写路径改造

- 新增/改造接口，区分个人与部门授权维度，避免覆盖式写入误删另一维度：
  - `PUT /knowledge-bases/{kb_id}/members`：仅覆盖**个人**授权。
  - `PUT /knowledge-bases/{kb_id}/dept-grants`：仅覆盖**部门**授权。
  - 或统一 `PUT .../grants` 带 `principal_type` 列表，按 type 分维度覆盖。
- admin 校验改为合计个人 admin + 部门 admin，任一方存在即满足"至少 1 个 admin"。
- 删除部门/用户时由外键 CASCADE 自动清理对应 `kb_grant`。

---

## 6. 前端改造

管理成员弹窗（KbMembersModal.vue）重构为两区：
1. **直接授权（个人）**：搜索加人、设级别、可移除（现有交互保留）。
2. **部门授权**：复用 `DepartmentTree` 组件选部门、设级别、可移除。
3. **有效权限预览**（§3.5）：展示最终合并结果 + 来源。

归档 / 公共 / 部门视图的"管理成员"按钮可见性保持当前逻辑（归档隐藏）。

---

## 7. 测试用例（边界）

- 个人 view + 部门 admin → 按 §3.3 语义得预期 level。
- 用户转部门 → 旧部门授权库权限立即消失，新部门授权库立即生效。
- 部门被删 → 其授权记录级联清除，相关用户权限实时变化。
- 库仅有部门 admin（无个人 admin）→ admin 校验通过。
- 严格库（有授权记录但当前用户无个人/部门匹配）→ 返回 None（不可见/403）。
- 遗留开放库（无任何授权记录）→ 隐式 view。
- super admin → 始终 admin，不受 grant 影响。
- 列表页：通过部门授权的库对个人可见；严格库对个人不可见。

---

## 8. 工作量与风险

- **工作量**：后端（新表 + 迁移 + 统一函数 + 写接口 + admin 校验）约 2-3 天；前端（弹窗分区 + 预览区 + 复用 DepartmentTree）约 1-2 天；测试约 0.5-1 天。**总计约 4-6 天**。
- **风险**：
  - 迁移出错可能导致权限数据丢失 → 必须备份 + 回滚脚本。
  - 合并语义写错 → 越权（看到不该看的）或误锁（该看的不显示）→ 必须配 §7 全套边界测试。
  - 权限模块高危，改动必须上生产（服务器 + 迁移），不可本地验证完就罢手。

---

## 9. 待确认决策点

1. **合并语义**：方案 A（个人显式优先）vs 方案 B（取最高）。—— **待定**。
2. **动工时机**：先出本方案对齐 → 排期上生产；或直接本地实现验证。
3. **写接口形态**：双接口（members / dept-grants）vs 单接口带 type。
4. **模型**：统一单表 `kb_grant` vs 个人/部门双表。—— 倾向单表（更干净，推荐）。
