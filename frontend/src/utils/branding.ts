/**
 * 访问方式判定与品牌化。
 *
 * 需求：通过 IP 直连（如 http://8.134.14.177）访问时，隐藏全部备案公示信息、
 * 站点 title 使用 Knoa 品牌名；通过绑定域名访问时，维持备案展示与备案主体 title。
 * 依据：工信部备案号仅需在已备案域名下公示，IP 直连场景不展示。
 *
 * 判定规则（hostname）：
 * - localhost / 127.0.0.1 / ::1 视为 IP 直连（非域名）
 * - 命中 IPv4 四段点分格式视为 IP
 * - 含 ':' 视为 IPv6 字面量
 * - 其余（含 . 的普通主机名）视为域名
 */

const IPV4_RE = /^(?:\d{1,3}\.){3}\d{1,3}$/

/** 当前是否以 IP 地址（含 localhost）方式访问。 */
export function isIpAccess(hostname: string = window.location.hostname): boolean {
  if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1') return true
  if (IPV4_RE.test(hostname)) return true
  if (hostname.includes(':')) return true // IPv6 字面量
  return false
}

/** 是否展示备案公示信息（仅域名访问展示）。 */
export function showBeian(): boolean {
  return !isIpAccess()
}

/** IP 直连时的站点 title。 */
export const TITLE_IP = 'Knoa企业智能知识库系统'
/** 域名访问时的站点 title（备案主体名）。 */
export const TITLE_DOMAIN = '惠聚创智能知识库'

/** 按访问方式返回站点 title。 */
export function siteTitle(): string {
  return isIpAccess() ? TITLE_IP : TITLE_DOMAIN
}
