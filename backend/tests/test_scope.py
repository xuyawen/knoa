"""scope 权限掩码端到端验证：private 文档仅上传者本人可检索，admin 全可见。

覆盖 P0-B 改造的核心安全属性：
- 他人 private chunk 对普通用户绝对不可见（向量 + BM25 双路掩码）；
- 上传者本人、KB/超管 admin 可检索到 private chunk；
- public 文档对所有用户可见。
"""
import uuid

import pytest
from sqlalchemy import select

from app.core.rag.ingestor import DocumentIngester
from app.core.rag.retriever import HybridRetriever
from app.core.security import (
    ScopeContext,
    compute_visible_dept_ids,
    ensure_doc_scope_writable,
    get_kb_permission_level,
    is_scope_visible,
)
from app.db import Department, Document, KnowledgeBase, Role, User

from tests._fakes import FakeEmbedder


async def _make_kb(db, name="scope-kb"):
    kb_id = f"kb_{uuid.uuid4().hex[:8]}"
    db.add(KnowledgeBase(id=kb_id, name=name, icon="🔐"))
    await db.commit()
    return kb_id


async def _make_user(db, name: str) -> uuid.UUID:
    """建真实用户（document.uploader_id 外键指向 app_user，role_id 非空）。"""
    role_id = await db.scalar(select(Role.id).where(Role.key == "viewer"))
    uid = uuid.uuid4()
    db.add(User(
        id=uid,
        username=f"{name}_{uuid.uuid4().hex[:6]}",
        password_hash=User.hash_password("test123"),
        display_name=name,
        role_id=role_id,
    ))
    await db.commit()
    return uid


async def test_private_doc_only_visible_to_uploader_and_admin(db_session):
    kb_id = await _make_kb(db_session)
    ingester = DocumentIngester(FakeEmbedder())
    user_a = await _make_user(db_session, "上传者A")  # 上传者

    # A 的私密文档（内容 >50 字，避免被 chunker 丢弃）
    priv = Document(
        kb_id=kb_id,
        title="机密薪资",
        source_path="upload",
        content_md="# 机密薪资\n员工A的薪资属于严格保密信息，月薪五万元，年终奖十万元。"
        "该信息绝对不能泄露给任何其他人，包括同部门同事。",
        status="已复核",
        scope="private",
        uploader_id=user_a,
    )
    db_session.add(priv)
    await db_session.flush()
    await ingester.ingest_existing(priv, db_session)

    # 公开文档（ingest_text 默认 scope=public）
    await ingester.ingest_text(
        kb_id,
        "公开考勤",
        "# 公开考勤\n公司考勤制度公开透明，早上九点打卡上班，下午六点下班，"
        "迟到一次扣当月全勤奖金，请假需提前在系统提交申请。",
        db_session,
    )
    await db_session.commit()

    user_b = await _make_user(db_session, "用户B")  # 其他普通用户
    query = "机密薪资 月薪 五万"

    # 1. 用户 B（非 admin、非上传者）：检索不到私密文档
    r_b = HybridRetriever(FakeEmbedder(), db_session, scope_ctx=ScopeContext(str(user_b), False))
    res_b = await r_b.retrieve(query, kb_id, top_k=5)
    assert all("机密薪资" not in r["title"] for r in res_b), f"私密文档泄露给用户B: {res_b}"

    # 2. 用户 A（上传者、非 admin）：可检索到私密文档
    r_a = HybridRetriever(FakeEmbedder(), db_session, scope_ctx=ScopeContext(str(user_a), False))
    res_a = await r_a.retrieve(query, kb_id, top_k=5)
    assert any("机密薪资" in r["title"] for r in res_a), f"上传者A检索不到私密文档: {res_a}"

    # 3. admin：可检索到私密文档
    r_adm = HybridRetriever(FakeEmbedder(), db_session, scope_ctx=ScopeContext(str(uuid.uuid4()), True))
    res_adm = await r_adm.retrieve(query, kb_id, top_k=5)
    assert any("机密薪资" in r["title"] for r in res_adm), f"admin检索不到私密文档: {res_adm}"

    # 4. 用户 B 可正常检索公开文档
    res_pub = await r_b.retrieve("公开考勤 打卡 迟到", kb_id, top_k=5)
    assert any("公开考勤" in r["title"] for r in res_pub), f"用户B检索不到公开文档: {res_pub}"


async def _make_dept(db, name: str, parent_id=None) -> uuid.UUID:
    d = Department(name=name, parent_id=parent_id)
    db.add(d)
    await db.commit()
    return d.id


async def _make_user_in_dept(db, name: str, department_id) -> uuid.UUID:
    """建带部门归属的真实用户（department_id 可为 None 表示无部门）。"""
    role_id = await db.scalar(select(Role.id).where(Role.key == "viewer"))
    uid = uuid.uuid4()
    db.add(User(
        id=uid,
        username=f"{name}_{uuid.uuid4().hex[:6]}",
        password_hash=User.hash_password("test123"),
        display_name=name,
        role_id=role_id,
        department_id=department_id,
    ))
    await db.commit()
    return uid


async def test_department_doc_visible_to_dept_subtree_only(db_session):
    """department 文档仅对归属部门及其子树可见，其他部门/无部门用户不可见。"""
    kb_id = await _make_kb(db_session, name="dept-kb")
    ingester = DocumentIngester(FakeEmbedder())

    # 部门树：parent ← child；another 为无关部门
    parent = await _make_dept(db_session, "研发中枢")
    child = await _make_dept(db_session, "后端组", parent_id=parent)
    another = await _make_dept(db_session, "市场部")

    # 部门文档：归属 child 部门
    dept_doc = Document(
        kb_id=kb_id,
        title="后端规范",
        source_path="upload",
        content_md="# 后端规范\n后端组内部开发规范文档，规定接口命名与代码审查流程，"
        "仅后端组成员可见，其他部门不应检索到本文档内容。",
        status="已复核",
        scope="department",
        department_id=child,
    )
    db_session.add(dept_doc)
    await db_session.flush()
    await ingester.ingest_existing(dept_doc, db_session)
    await db_session.commit()

    user_parent = await _make_user_in_dept(db_session, "父部门用户", parent)
    user_child = await _make_user_in_dept(db_session, "子部门用户", child)
    user_other = await _make_user_in_dept(db_session, "其他部门用户", another)
    user_nodept = await _make_user_in_dept(db_session, "无部门用户", None)
    query = "后端规范 接口命名 代码审查"

    async def can_see(uid: uuid.UUID) -> bool:
        u = await db_session.get(User, uid)
        dept_ids = await compute_visible_dept_ids(db_session, u)
        r = HybridRetriever(
            FakeEmbedder(), db_session,
            scope_ctx=ScopeContext(str(uid), False, dept_ids),
        )
        res = await r.retrieve(query, kb_id, top_k=5)
        return any("后端规范" in x["title"] for x in res)

    assert await can_see(user_child), "子部门用户应可见本部门文档"
    assert await can_see(user_parent), "父部门用户应可见子部门文档（含子树）"
    assert not await can_see(user_other), "其他部门用户不应可见部门文档"
    assert not await can_see(user_nodept), "无部门用户不应可见部门文档"


async def test_open_kb_denied_under_fail_close(db_session):
    """fail-close：无任何权限记录的库对非超管不可见（返回 None）。

    即使是 editor 角色（角色权限含 doc_edit）也不被隐式授予任何库级权限，
    访问/写操作都必须显式授权——从"开放库隐式 view"收紧为"未授权即拒绝"。
    """
    kb_id = await _make_kb(db_session, name="open-kb")  # 不写任何 KBPermission
    editor_role = await db_session.scalar(select(Role.id).where(Role.key == "editor"))
    uid = uuid.uuid4()
    db_session.add(User(
        id=uid, username=f"editor_{uuid.uuid4().hex[:6]}",
        password_hash=User.hash_password("test123"),
        display_name="编辑", role_id=editor_role,
    ))
    await db_session.commit()
    user = await db_session.get(User, uid)
    level = await get_kb_permission_level(db_session, kb_id, user)
    assert level is None, f"fail-close 下开放库应拒绝（None），实际 {level}"


async def test_write_path_scope_blocks_non_uploader(db_session):
    """#1 写路径 scope 校验：非 admin 非上传者对他人 private 文档的写操作被 403 拦下。

    读路径早已拦，这里补齐删除/审核共用的 ensure_doc_scope_writable：
    攻击者 B（有库级权限但非上传者）删/审 A 的 private 文档 → 403；上传者本人放行。
    """
    from fastapi import HTTPException

    kb_id = await _make_kb(db_session, name="write-scope-kb")
    user_a = await _make_user(db_session, "上传者A")
    priv = Document(
        kb_id=kb_id, title="机密薪资", source_path="upload",
        content_md="# 机密薪资\n员工A的薪资严格保密，月薪五万元。",
        status="已复核", scope="private", uploader_id=user_a,
    )
    db_session.add(priv)
    await db_session.commit()

    # 攻击者 B：viewer 角色（非超管）、非上传者 → 写操作应 403
    user_b = await _make_user(db_session, "攻击者B")
    b = await db_session.get(User, user_b)
    with pytest.raises(HTTPException) as ei:
        await ensure_doc_scope_writable(db_session, priv, b)
    assert ei.value.status_code == 403, "非上传者应被拦下（403）"

    # 上传者 A 本人：写操作放行（不抛异常）
    a = await db_session.get(User, user_a)
    await ensure_doc_scope_writable(db_session, priv, a)


async def test_scope_three_impls_contract(db_session):
    """#3 契约测试：SQL doc_scope_clause / Python is_scope_visible / ES _build_scope_filter
    三套平行实现，对同一批文档 × 同一批用户必须产出完全一致的可见集合。

    任一路将来改错（如 ES 漏了 department、Python 改了 private 语义），本测试立刻红。
    ES 过滤不依赖真实 ES——用一个解释器对 _build_scope_filter 产出的 DSL 子集求值。
    """
    from app.core.rag.es_retriever import ESRetriever
    from app.core.security import doc_scope_clause

    kb_id = await _make_kb(db_session, name="contract-kb")
    dept_x = await _make_dept(db_session, "X部门")
    dept_y = await _make_dept(db_session, "Y部门")

    uploader = await _make_user(db_session, "上传者")
    other = await _make_user(db_session, "另一上传者")
    dept_user = await _make_user_in_dept(db_session, "X部门用户", dept_x)
    outsider = await _make_user_in_dept(db_session, "外人", dept_y)

    # 五档 scope 组合（覆盖 public / private 本人与他人 / department 子树内外）
    specs = [
        ("d_public", "public", None, None),
        ("d_priv_own", "private", uploader, None),
        ("d_priv_other", "private", other, None),
        ("d_dept_in", "department", None, dept_x),
        ("d_dept_out", "department", None, dept_y),
    ]
    docs = []
    for title, scope, upl, dept in specs:
        d = Document(kb_id=kb_id, title=title, source_path="upload",
                     content_md=f"# {title}\n契约测试可见性占位内容。",
                     status="已复核", scope=scope, uploader_id=upl, department_id=dept)
        db_session.add(d)
        docs.append(d)
    await db_session.commit()
    for d in docs:
        await db_session.refresh(d)

    def field(d, name):
        if name == "scope":
            return d.scope
        if name == "uploader_id":
            return str(d.uploader_id) if d.uploader_id else None
        if name == "department_id":
            return str(d.department_id) if d.department_id else None
        return None

    def es_match(node, d) -> bool:
        """解释 _build_scope_filter 的 ES DSL 子集（term/terms/bool.must/bool.should）。"""
        if node is None:
            return True
        if "term" in node:
            (k, v), = node["term"].items()
            return field(d, k) == v
        if "terms" in node:
            (k, vs), = node["terms"].items()
            return field(d, k) in vs
        if "bool" in node:
            b = node["bool"]
            if "must" in b:
                return all(es_match(m, d) for m in b["must"])
            if "should" in b:
                return any(es_match(s, d) for s in b["should"])  # minimum_should_match=1
        return False

    for uid in (uploader, other, dept_user, outsider):
        user = await db_session.get(User, uid)
        dept_ids = await compute_visible_dept_ids(db_session, user)
        ctx = ScopeContext(str(user.id), False, dept_ids)  # 四人均非超管

        # 路 1：SQL doc_scope_clause
        clause = doc_scope_clause(user, False, dept_ids)
        q = select(Document).where(Document.kb_id == kb_id)
        if clause is not None:
            q = q.where(clause)
        sql_set = {d.title for d in (await db_session.execute(q)).scalars().all()}

        # 路 2：Python is_scope_visible
        py_set = {d.title for d in docs
                  if is_scope_visible(d.scope, d.uploader_id, ctx,
                                      str(d.department_id) if d.department_id else None)}

        # 路 3：ES _build_scope_filter（解释求值，不连真实 ES）
        flt = ESRetriever(FakeEmbedder(), None, scope_ctx=ctx)._build_scope_filter()
        es_set = {d.title for d in docs if es_match(flt, d)}

        assert sql_set == py_set, f"用户{user.display_name}: SQL{sql_set} != Python{py_set}"
        assert sql_set == es_set, f"用户{user.display_name}: SQL{sql_set} != ES{es_set}"
