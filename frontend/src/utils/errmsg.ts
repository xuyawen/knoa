/** 从任意抛出值中提取用户可读的错误文案。
 *  配合 `catch (e: unknown)` 使用，替代散落各处的 `e?.message || e` 样板，
 *  避免 catch (e: any) 绕过类型检查。 */
export function errMsg(e: unknown, fallback = '未知错误'): string {
  if (e instanceof Error && e.message) return e.message
  if (typeof e === 'string' && e) return e
  return fallback
}
