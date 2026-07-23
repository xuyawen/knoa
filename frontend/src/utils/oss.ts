/** 阿里云 OSS 前端直传工具（PostObject，零 SDK）。
 *
 * 流程：
 *  1. 调后端 /api/oss/sign 拿 policy/signature/host/key
 *  2. 用 FormData 把字段 + 文件 POST 到 host
 *  3. OSS 返回 200/204 即成功，文件可访问地址 = host/key
 *
 * 后端只在 .env 里配置 OSS_*，AccessKey 不落前端。
 */
import { getOssSign } from '@/api'

export interface OssSign {
  accessKeyId: string
  policy: string
  signature: string
  host: string
  key: string
  url: string
  expiresAt: number
}

export interface OssUploadResult {
  url: string
  key: string
}

/** 直接把 File 传到 OSS，返回可访问地址。prefix 区分业务目录（如 uploads/docs）。 */
export async function uploadToOss(file: File, prefix = 'uploads'): Promise<OssUploadResult> {
  let sign: OssSign
  try {
    sign = await getOssSign(prefix, file.name)
  } catch (e: any) {
    throw new Error(`获取 OSS 签名失败：${e?.message || e}`)
  }

  const form = new FormData()
  form.append('key', sign.key)
  form.append('OSSAccessKeyId', sign.accessKeyId)
  form.append('policy', sign.policy)
  form.append('signature', sign.signature)
  form.append('success_action_status', '200')
  form.append('file', file)

  const resp = await fetch(sign.host, { method: 'POST', body: form })
  if (!resp.ok) {
    // OSS 错误体会带 XML，尝试读一下给前端看
    const text = await resp.text().catch(() => '')
    throw new Error(`OSS 上传失败 (${resp.status})${text ? '：' + text : ''}`)
  }
  return { url: sign.url, key: sign.key }
}
