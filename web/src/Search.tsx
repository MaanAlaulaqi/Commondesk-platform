import {useContext,useState} from 'react'
import {Image as Photo,Search as SearchIcon} from 'lucide-react'
import {type CaseList,type Filters,post,upload,pretty} from './client'
import {Locale,useWords} from './locale'
import {Busy,CaseRow,Field,FilterBar,Notice,SourceSelect,useLoad,type Facets} from './ui'
export default function Search(){
 const t=useWords(),locale=useContext(Locale),[text,setText]=useState(''),[file,setFile]=useState<File|null>(null),[f,set]=useState<Filters>({source:'seed'}),[rows,load]=useState<CaseList|null>(null),[busy,setBusy]=useState(false),[error,err]=useState('')
 const facets=useLoad<Facets>('/facets?source='+f.source)
 async function run(){
  setBusy(true);err('');load(null)
  try{const photo=file?await upload(file):undefined;const {source,...filters}=f;load(await post<CaseList>('/search',{text,photo,source,filters,locale}))}
  catch(e){err((e as Error).message)}finally{setBusy(false)}
 }
 return <><div className="page-head"><h1>{t('search')}</h1><SourceSelect value={f.source} onChange={s=>{set({source:s});load(null)}}/></div>
 <form className="search-form" onSubmit={e=>{e.preventDefault();void run()}}><Field label={t('searchHint')}><input type="search" dir="auto" value={text} onChange={e=>setText(e.target.value)}/></Field><div className="search-actions"><Field label={t('reference')+' · '+t('optional')}><input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>setFile(e.target.files?.[0]||null)}/></Field><button className="primary" disabled={busy||(!text.trim()&&!file)}><SearchIcon size={17}/>{t('searchCases')}</button></div></form>
 <FilterBar f={f} set={v=>{set(v);load(null)}} facets={facets.data}/><Notice error={error}/>{busy&&<Busy/>}{rows&&<><h2 className="section-heading">{t('results')} <small>{rows.total??rows.items.length}</small></h2>{rows.items.length?<div className="search-grid">{rows.items.map(c=><CaseRow item={c} key={c.id}/>)}</div>:<p>{t('empty')}</p>}</>}</>
}
