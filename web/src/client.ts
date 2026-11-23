export const apiBase = (import.meta.env.VITE_API_ORIGIN || '').replace(/\/$/, '').replace(/\/api$/, '') + '/api'
export function mediaUrl(id: string) {
  return apiBase + '/media/' + encodeURIComponent(id)
}
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiBase + path, init)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const message = typeof body.detail === 'string' ? body.detail : typeof body.error === 'string' ? body.error : typeof body.message === 'string' ? body.message : 'Request failed (' + res.status + '). Please retry.'
    throw new Error(message)
  }
  const data = await res.text()
  try { return JSON.parse(data) } catch { throw new Error('The workspace API is unavailable. Please retry.') }
}
export function post<T>(path: string, body: unknown) {
  return request<T>(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})
}
export async function upload(file: File) {
  const form = new FormData()
  form.append('file', file)
  const result = await request<{id:string}>('/media', {method:'POST',body:form})
  return result.id
}
export type Case = {
  id:string; text:string; source:string; language:string; category:string; urgency:string|null; status:string; district:string|null; latitude:number|null; longitude:number|null; created_at:string; photo?:string; media_id?:string; intent?:string;
  urgency_suggested?:string; urgency_confirmed?:string|null; selected_service?:string|null; provenance?:string; index_status?:string;
  translations?:Record<string,string>|{language:string;text:string}[]; events?:{event_id:string;at:string;status:string;type?:string;detail?:string}[]; proposal?:Record<string,unknown>;
}
export type CaseList={items:Case[];total:number}
export type Filters=Record<string,string>
export type Coordinate={latitude:number;longitude:number;location_source:string;accuracy?:number}
export const langs:Record<string,string>={en:'English',ar:'العربية',hi:'हिन्दी',th:'ไทย',ur:'اردو'}
export function pretty(s:unknown) {return typeof s === 'string' ? s.replace(/[_-]+/g,' ').replace(/^./, c=>c.toUpperCase()) : ''}
export function url(page:string, params:Filters={}) {
  const qs=new URLSearchParams(Object.entries(params).filter(([,v])=>v)).toString()
  return '#/'+page+(qs?'?'+qs:'')
}
export function route() {
  const [path,query='']=location.hash.replace(/^#\/?/,'').split('?')
  return {page:path||'explore', params:Object.fromEntries(new URLSearchParams(query))}
}
export function caseUrl(c:Case){return url('case/'+encodeURIComponent(c.id),{source:c.source})}
