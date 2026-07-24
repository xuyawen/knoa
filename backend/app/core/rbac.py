"""角色权限（RBAC）核心定义。

- 权限（permission）是一组固定枚举，由代码定义单一真值（PERMISSIONS）。
- 角色（Role）与「角色→权限」映射（role_permission）存数据库，可由管理员在 UI 配置。
- 内置角色 admin/editor/viewer 不可删除，但其权限集合可被管理员修改。
"""
from dataclasses import dataclass


class Perm:
    """权限 key 常量（与前端角色管理矩阵一一对应）。"""

    KB_VIEW = "kb_view"          # 知识库查看
    DOC_UPLOAD = "doc_upload"    # 文档上传
    DOC_EDIT = "doc_edit"        # 文档编辑
    DOC_DELETE = "doc_delete"    # 文档删除
    AI_QA = "ai_qa"              # AI 问答
    GRAPH_MANAGE = "graph_manage"  # 图谱管理
    USER_MANAGE = "user_manage"  # 用户管理
    SYS_SETTINGS = "sys_settings"  # 系统设置


@dataclass(frozen=True)
class PermissionDef:
    key: str
    label: str
    group: str


# 权限清单（前端矩阵渲染 + 后端校验共用）
PERMISSIONS: list[PermissionDef] = [
    PermissionDef(Perm.KB_VIEW, "知识库查看", "知识库"),
    PermissionDef(Perm.DOC_UPLOAD, "文档上传", "知识库"),
    PermissionDef(Perm.DOC_EDIT, "文档编辑", "知识库"),
    PermissionDef(Perm.DOC_DELETE, "文档删除", "知识库"),
    PermissionDef(Perm.AI_QA, "AI 问答", "问答"),
    PermissionDef(Perm.GRAPH_MANAGE, "图谱管理", "知识图谱"),
    PermissionDef(Perm.USER_MANAGE, "用户管理", "系统"),
    PermissionDef(Perm.SYS_SETTINGS, "系统设置", "系统"),
]

PERMISSION_KEYS = {p.key for p in PERMISSIONS}

# 内置角色及其默认权限（种子数据，可被管理员在 UI 修改）
BUILTIN_ROLES: dict[str, dict] = {
    "admin": {
        "name": "管理员",
        "description": "系统最高权限，可管理用户、知识库与全部系统设置",
        "perms": [p.key for p in PERMISSIONS],
    },
    "editor": {
        "name": "编辑者",
        "description": "可维护知识库内容（上传/编辑文档、管理图谱）",
        "perms": [
            Perm.KB_VIEW,
            Perm.DOC_UPLOAD,
            Perm.DOC_EDIT,
            Perm.AI_QA,
            Perm.GRAPH_MANAGE,
        ],
    },
    "viewer": {
        "name": "访客",
        "description": "仅可查看知识库与进行 AI 问答",
        "perms": [Perm.KB_VIEW, Perm.AI_QA],
    },
}
