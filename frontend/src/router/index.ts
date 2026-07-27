import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 路由表：认证页（Login）在布局外；其余业务页挂在 AppLayout 下。
// auth 守卫以 HttpOnly Cookie 为准：进入受保护页前，若无登录态则尝试用已有
// Cookie 还原（仅一次）；还原失败跳登录页（带 redirect 回跳参数）。
// 每个左侧子菜单项都是一条真实嵌套路由，各自对应一个独立视图组件，
// 因此每个菜单项都对应一个可收藏、URL 独立的完整页面。
//
// 懒加载策略：Login 与 AppLayout 静态导入（首屏必经，避免二次请求闪烁），
// 其余业务视图全部 `() => import(...)` 按路由分包，首包只含登录与布局骨架。
import Login from '@/views/Login.vue'
import AppLayout from '@/components/layout/AppLayout.vue'

const DashboardOverview = () => import('@/views/DashboardOverview.vue')
const DashboardAnalytics = () => import('@/views/DashboardAnalytics.vue')
const DashboardDocs = () => import('@/views/DashboardDocs.vue')
const DashboardUsers = () => import('@/views/DashboardUsers.vue')
const DashboardPopular = () => import('@/views/DashboardPopular.vue')
const Announcements = () => import('@/views/Announcements.vue')
const Search = () => import('@/views/Search.vue')
const SearchHistory = () => import('@/views/SearchHistory.vue')
const Chat = () => import('@/views/Chat.vue')
const RecordsView = () => import('@/views/RecordsView.vue')
const ModelConfig = () => import('@/views/ModelConfig.vue')
const GraphGlobal = () => import('@/views/GraphGlobal.vue')
const GraphNodes = () => import('@/views/GraphNodes.vue')
const GraphRelations = () => import('@/views/GraphRelations.vue')
const GraphStats = () => import('@/views/GraphStats.vue')
const Permission = () => import('@/views/Permission.vue')
const RoleManage = () => import('@/views/RoleManage.vue')
const DepartmentView = () => import('@/views/DepartmentView.vue')
const Profile = () => import('@/views/Profile.vue')
const MemoryManage = () => import('@/views/MemoryManage.vue')
const DocumentsMine = () => import('@/views/DocumentsMine.vue')
const DocumentsPublic = () => import('@/views/DocumentsPublic.vue')
const DocumentsDepartment = () => import('@/views/DocumentsDepartment.vue')
const DocumentsArchive = () => import('@/views/DocumentsArchive.vue')
const NotFound = () => import('@/views/NotFound.vue')

// 子菜单分区 -> 路由段 + 默认 section
const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: Login, meta: { public: true } },
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      // ===== 首页大盘（每个页面一个文件）=====
      { path: 'dashboard', name: 'dashboard', component: DashboardOverview, meta: { title: '首页大盘', icon: 'dashboard' } },
      { path: 'dashboard/analytics', name: 'dash-analytics', component: DashboardAnalytics, meta: { title: '首页大盘', icon: 'chart' } },
      { path: 'dashboard/docs', name: 'dash-docs', component: DashboardDocs, meta: { title: '首页大盘', icon: 'doc' } },
      { path: 'dashboard/users', name: 'dash-users', component: DashboardUsers, meta: { title: '首页大盘', icon: 'users' } },
      { path: 'dashboard/popular', name: 'dash-popular', component: DashboardPopular, meta: { title: '首页大盘', icon: 'fire' } },
      { path: 'dashboard/announcements', name: 'dash-announcements', component: Announcements, meta: { title: '首页大盘', icon: 'bell' } },

      // ===== 文档管理（每个页面一个文件，复用 DocumentLibrary 组件）=====
      { path: 'documents', name: 'documents', component: DocumentsMine, meta: { title: '文档管理', icon: 'doc' } },
      { path: 'documents/public', name: 'docs-public', component: DocumentsPublic, meta: { title: '文档管理', icon: 'globe' } },
      { path: 'documents/department', name: 'docs-department', component: DocumentsDepartment, meta: { title: '文档管理', icon: 'team' } },
      { path: 'documents/archive', name: 'docs-archive', component: DocumentsArchive, meta: { title: '文档管理', icon: 'archive' } },

      // ===== 智能搜索（一个页面一个文件）=====
      { path: 'search', name: 'search', component: Search, meta: { title: '智能搜索', icon: 'search' } },
      { path: 'search/history', name: 'search-history', component: SearchHistory, meta: { title: '智能搜索', icon: 'clock' } },

      // ===== 智能问答（一个页面一个文件）=====
      { path: 'chat', name: 'chat', component: Chat, meta: { title: '智能问答', icon: 'chat' } },
      { path: 'chat/new', name: 'chat-new', component: Chat, meta: { title: '智能问答', icon: 'plus' } },
      { path: 'chat/records', name: 'chat-records', component: RecordsView, meta: { title: '检索记录', icon: 'list' } },
      { path: 'chat/model', name: 'chat-model', component: ModelConfig, meta: { title: '智能问答', icon: 'settings' } },

      // ===== 知识图谱（每个页面一个文件）=====
      { path: 'graph', name: 'graph', component: GraphGlobal, meta: { title: '知识图谱', icon: 'graph' } },
      { path: 'graph/global', name: 'graph-global', component: GraphGlobal, meta: { title: '知识图谱', icon: 'graph' } },
      { path: 'graph/nodes', name: 'graph-nodes', component: GraphNodes, meta: { title: '知识图谱', icon: 'node' } },
      { path: 'graph/relations', name: 'graph-relations', component: GraphRelations, meta: { title: '知识图谱', icon: 'link' } },
      { path: 'graph/stats', name: 'graph-stats', component: GraphStats, meta: { title: '知识图谱', icon: 'chart' } },

      // ===== 系统管理（一个页面一个文件）=====
      { path: 'permission', name: 'permission', component: Permission, meta: { title: '系统管理', icon: 'shield' } },
      { path: 'permission/roles', name: 'perm-roles', component: RoleManage, meta: { title: '系统管理', icon: 'shield' } },
      { path: 'permission/departments', name: 'perm-departments', component: DepartmentView, meta: { title: '系统管理', icon: 'team' } },
      { path: 'profile', name: 'profile', component: Profile, meta: { title: '个人中心', icon: 'user' } },
      { path: 'memories', name: 'memories', component: MemoryManage, meta: { title: '个人中心', icon: 'brain-circuit' } },
      // 原「系统设置」页已并入「模型配置」(/chat/model)，旧路径重定向兼容书签
      { path: 'settings', redirect: '/chat/model' },
    ],
  },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFound },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// 登录态引导：仅一次用 HttpOnly Cookie 尝试还原；失败跳登录页。
let bootstrapped = false

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  // 公开页（登录）无需鉴权
  if (to.meta.public) return true

  if (!auth.isLoggedIn) {
    if (!bootstrapped) {
      await auth.fetchMe()
      bootstrapped = true
    }
    if (!auth.isLoggedIn) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
  return true
})

export default router
