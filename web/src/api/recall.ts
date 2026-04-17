import { api } from './http'
import type { RecallRequest, RecallResponse } from './types'

/**
 * \u8c03\u7528 `POST /v1/context/recall`\u3002
 * \u670d\u52a1\u7aef\u5e26\u67094 \u4fe1\u53f7\u878d\u5408 + recall cache + degraded \u964d\u7ea7\u3002
 */
export async function recall(
  request: RecallRequest,
  opts: { timeoutMs?: number } = {}
): Promise<RecallResponse> {
  return api.post<RecallResponse>('/v1/context/recall', request, {
    timeoutMs: opts.timeoutMs ?? 20000
  })
}
