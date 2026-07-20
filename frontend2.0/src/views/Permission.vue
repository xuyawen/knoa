<script setup lang="ts">
// 权限管理（对应架构图 #7）：角色权限矩阵 + 部门组织树。
// 界面壳阶段：静态示例数据，未接后端 RBAC。
import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'

const modules = ['知识库查看', '文档上传', '文档编辑', '文档删除', 'AI 问答', '图谱管理', '用户管理', '系统设置']
const roles = [
  { name: '管理员', key: 'admin', perms: [true, true, true, true, true, true, true, true] },
  { name: '编辑者', key: 'editor', perms: [true, true, true, false, true, true, false, false] },
  { name: '访客', key: 'viewer', perms: [true, false, false, false, true, false, false, false] },
]

const deptTree = [
  { name: '技术中心', count: 42, children: [{ name: '后端组', count: 18 }, { name: '前端组', count: 14 }, { name: '算法组', count: 10 }] },
  { name: '产品中心', count: 26, children: [{ name: '产品设计', count: 12 }, { name: '用户研究', count: 14 }] },
  { name: '市场中心', count: 19, children: [{ name: '品牌', count: 8 }, { name: '增长', count: 11 }] },
]
const expanded = ref<Set<number>>(new Set([0]))

function toggle(i: number) {
  const s = new Set(expanded.value)
  s.has(i) ? s.delete(i) : s.add(i)
  expanded.value = s
}
</script>

<template>
  <div class="page perm fade-up">
    <header class="page-head">
      <div class="flex items-center">
        <h1 class="page-title">权限管理</h1>
        <span class="todo-flag"><Icon name="sparkles" :size="12" />界面壳 · 示例数据</span>
      </div>
      <p class="page-sub">基于角色的访问控制（RBAC），按部门与文档粒度下发权限</p>
    </header>

    <div class="perm-body">
      <!-- 部门树 -->
      <aside class="card perm-dept">
        <h3 class="perm-h">部门组织</h3>
        <ul class="tree">
          <li v-for="(d, i) in deptTree" :key="i">
            <div class="tree-row" @click="toggle(i)">
              <Icon name="chevron" :size="14" :style="`transform: rotate(${expanded.has(i) ? 90 : 0}deg); transition: transform .2s`" class="tree-c" />
              <Icon name="folder" :size="16" class="tree-ic" />
              <span class="tree-name">{{ d.name }}</span>
              <span class="tree-cnt">{{ d.count }}</span>
            </div>
            <ul v-if="expanded.has(i)" class="tree sub">
              <li v-for="(c, j) in d.children" :key="j" class="tree-row sub-row">
                <span class="tree-dot" />
                <span class="tree-name">{{ c.name }}</span>
                <span class="tree-cnt">{{ c.count }}</span>
              </li>
            </ul>
          </li>
        </ul>
      </aside>

      <!-- 角色权限矩阵 -->
      <section class="card perm-matrix">
        <h3 class="perm-h">角色权限矩阵</h3>
        <table class="mtx">
          <thead>
            <tr>
              <th>功能模块</th>
              <th v-for="r in roles" :key="r.key">{{ r.name }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(m, mi) in modules" :key="mi">
              <td class="mtx-mod">{{ m }}</td>
              <td v-for="r in roles" :key="r.key">
                <span class="sw" :class="r.perms[mi] ? 'on' : 'off'">
                  <span class="knob" />
                </span>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="perm-note">提示：矩阵为静态示例，功能接入后将与后端 RBAC 角色实时同步。</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.perm-body {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  align-items: start;
}
.perm-h { margin: 0 0 14px; font-size: 15px; font-weight: 600; }
.perm-dept { padding: 18px; }
.tree { list-style: none; padding: 0; margin: 0; }
.tree.sub { padding-left: 22px; margin-top: 2px; }
.tree-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 6px; border-radius: var(--radius-md);
  cursor: pointer; transition: background var(--dur-fast);
}
.tree-row:hover { background: var(--bg-hover); }
.tree-c { color: var(--text-tertiary); flex-shrink: 0; }
.tree-ic { color: var(--brand); flex-shrink: 0; }
.tree-name { flex: 1; font-size: 13px; }
.tree-cnt {
  font-size: 11px; color: var(--text-tertiary);
  background: var(--bg-subtle); border-radius: var(--radius-pill); padding: 1px 8px;
}
.sub-row { cursor: default; padding: 6px; }
.tree-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-tertiary); margin-left: 4px; flex-shrink: 0; }

.perm-matrix { padding: 18px 20px; }
.mtx { width: 100%; border-collapse: collapse; font-size: 13px; }
.mtx th {
  text-align: left; padding: 10px 14px; color: var(--text-tertiary);
  font-weight: 500; border-bottom: 1px solid var(--border);
}
.mtx td { padding: 11px 14px; border-bottom: 1px solid var(--border); }
.mtx tr:last-child td { border-bottom: none; }
.mtx-mod { color: var(--text-secondary); }

.sw {
  display: inline-flex; align-items: center;
  width: 38px; height: 22px; border-radius: var(--radius-pill);
  padding: 2px; transition: background var(--dur-fast);
}
.sw .knob {
  width: 18px; height: 18px; border-radius: 50%;
  background: #fff; transition: transform var(--dur-fast);
}
.sw.on { background: var(--brand); }
.sw.on .knob { transform: translateX(16px); }
.sw.off { background: var(--border-strong); }
.sw.off .knob { transform: translateX(0); }

.perm-note { margin: 14px 0 0; font-size: 12px; color: var(--text-tertiary); }

@media (max-width: 920px) {
  .perm-body { grid-template-columns: 1fr; }
}
</style>
