import React, {useEffect, useRef, useState} from 'react';
import {Search, AlertTriangle, FileText, CheckCircle2, Pencil, XCircle, Clock, Database} from 'lucide-react';
import './HumanReview.css';
import './HumanReviewReference.css';
import './HumanReviewApplicability.css';
import './HumanReviewTab3Shell.css';
import HumanReviewBulkToolbar from './HumanReviewBulkToolbar.jsx';
import HumanReviewQueue from './HumanReviewQueue.jsx';
import './HumanReviewFocus.css';

const label=v=>String(v ?? 'Not stated').replaceAll('_',' ');
const stateLabel=s=>({UNREVIEWED:'Pending review',APPROVED:'Approved',CORRECTED:'Corrected',REJECTED:'Rejected / Needs clarification'}[s] || s);
const title=r=>r.original.requirement_text || r.original.requirement || r.original.description || r.original.name || r.original.location_name || r.original.coordinates_original || label(r.original.variable);
const names={variable:'Parameter / variable',canonical_variable:'Canonical variable',operator:'Comparison',threshold:'Threshold',unit:'Unit',temporal_requirement:'Timing',depth_requirement:'Requested depth',geographic_scope:'Scope',requirement:'Requirement',important_limit:'Important limit',timing:'Timing',description:'Description',restriction:'Restriction',location_name:'Location label',coordinates_original:'Original coordinates',coordinate_system:'Coordinate reference system',latitude:'Normalized latitude',longitude:'Normalized longitude',geometry_type:'Geometry'};
const fields=Object.keys(names);
export function reviewSummary(rows){
  const s={total:rows.length,approved:0,corrected:0,pending:0,rejected:0,notApplicable:0,gaps:0,resolved:0};
  rows.forEach(r=>{s[({APPROVED:'approved',CORRECTED:'corrected',REJECTED:'rejected'}[r.state] || 'pending')]++;if(r.applicability==='NOT_APPLICABLE')s.notApplicable++;if(!r.source?.source_verified || r.conflict)s.gaps++;if(!r.conflict && ['APPROVED','CORRECTED'].includes(r.state) && ['APPLICABLE','NOT_APPLICABLE'].includes(r.applicability) && (r.applicability!=='NOT_APPLICABLE' || r.review?.note?.trim()))s.resolved++;});
  const conditions=rows.filter(r=>r.kind!=='spatial_context');
  s.applicable=conditions.filter(r=>r.applicability==='APPLICABLE').length;
  s.notApplicable=conditions.filter(r=>r.applicability==='NOT_APPLICABLE').length;
  s.unassessed=conditions.filter(r=>r.applicability!=='APPLICABLE'&&r.applicability!=='NOT_APPLICABLE').length;
  return {...s,complete:s.total>0 && s.total===s.resolved};
}
const reviewResolved = row => !row.conflict && ['APPROVED','CORRECTED'].includes(row.state) && ['APPLICABLE','NOT_APPLICABLE'].includes(row.applicability) && (row.applicability !== 'NOT_APPLICABLE' || row.review?.note?.trim());
function unsavedDraft(row,draft){
  if(!row || !draft)return false;
  const original={reviewer:row.review?.reviewer||'Local reviewer',note:row.review?.note||'',applicability:row.applicability,changes:row.review?.corrections||{}};
  return JSON.stringify({reviewer:draft.reviewer||'',note:draft.note||'',applicability:draft.applicability,changes:draft.changes||{}})!==JSON.stringify(original);
}

export default LegacyHumanReview;
function Preview({record:r}){return <strong>{r.threshold!=null && r.operator ? `${label(r.variable || r.canonical_variable)} ${r.operator} ${r.threshold} ${r.unit || ''}` : r.requirement_text || r.requirement || r.description || label(r.variable || r.canonical_variable)}</strong>;}
function Interpretation({record,changes={},original}){return <dl className="review-values">{fields.filter(k=>record[k]!=null || Object.hasOwn(changes,k)).map(k=><div key={k} className={Object.hasOwn(changes,k) ? 'review-changed' : ''}><dt>{names[k]}{Object.hasOwn(changes,k) && <span className="review-badge">Changed</span>}</dt><dd>{Object.hasOwn(changes,k) && <span className="review-was">Original: {String(original[k] ?? 'Not stated')}</span>}{String(record[k] ?? 'Not stated')}</dd></div>)}</dl>;}
function Evidence({row,analysis,session}){
  const results=session?.environmental_result?.analysis_id===analysis.analysis_id ? session.environmental_result.requirements || [] : [];
  return <aside className="review-panel review-evidence"><h2><Database size={17}/>Data & evidence</h2><div><span className="review-label">Interpretation review</span><b>{stateLabel(row.state)}</b></div><div><span className="review-label">Decision role</span><b>{row.decision_relevant_default ? 'Operational constraint' : row.mapping.some(m=>m.routing?.preferred_provider==='EXTERNAL') ? 'Administrative / manual obligation' : 'Informational / non-gating'}</b></div>
    {!row.mapping.length && <p>Environmental evidence method is not specified for this record.</p>}
    {row.mapping.map((m,i)=>{const p=m.routing?.preferred_provider;const found=results.find(r=>String(r.condition_id)===String(m.condition_id) && r.canonical_variable===m.canonical_variable && r.operator===m.operator && r.threshold===m.threshold);return <div key={i} className="review-method"><span className="review-label">Evidence method / source</span><b>{p==='EXTERNAL' ? 'External / manual evidence' : !m.routing?.implemented ? 'Unsupported / unavailable' : p==='COPERNICUS_MARINE' ? 'Marine model evidence' : p==='ECMWF_FORECAST' ? 'Atmospheric forecast evidence' : label(p)}</b><small>{label(p)} · {label(m.canonical_variable)}</small><span className="review-label">Current evidence availability</span><b>{p==='EXTERNAL' ? 'REQUIRED — external/manual evidence' : found ? label(found.retrieval_status || (found.evidence ? 'Retrieved — validity requires inspection' : 'No retrieved evidence')) : 'NOT FETCHED'}</b><p>{m.routing?.notes}</p></div>;})}
    <p className="review-footnote">Review acceptance and evidence availability are separate. This workspace does not fetch evidence.</p></aside>;
}
function Workspace({row,analysis,session,identity,draft,onDraft,onSaved}){
  const raw=row.original;const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const v=draft || {reviewer:row.review?.reviewer || 'Local reviewer',note:row.review?.note || '',applicability:row.applicability,changes:row.review?.corrections || {},editing:false};
  const set=updates=>onDraft({...v,...updates});
  async function save(state){setError('');if(v.applicability==='NOT_APPLICABLE' && !v.note.trim()){setError('A reviewer note is required for Not Applicable.');return;}setBusy(true);try{
    const corrections=state==='CORRECTED' ? Object.fromEntries(Object.entries(v.changes).map(([k,x])=>[k,k==='threshold' ? x==='' ? null : Number(x) : x])) : {};
    if(Object.hasOwn(corrections,'threshold') && corrections.threshold!==null && !Number.isFinite(corrections.threshold))throw new Error('Enter a finite numeric threshold.');
    const applicability = row.kind === 'spatial_context' && state === 'APPROVED' && v.applicability === 'UNASSESSED' ? 'APPLICABLE' : v.applicability;
    const response=await fetch(`/api/reviews/${encodeURIComponent(row.target_id)}`,{method:'PUT',headers:{'Content-Type':'application/json','X-Session-Id':session.boot_id},body:JSON.stringify({...identity,review:{original_fingerprint:row.original_fingerprint,state,applicability,corrections,reviewer:v.reviewer,note:v.note}})});const result=await response.json();if(!response.ok)throw new Error(result.error || 'Review could not be saved.');onSaved(result);
  }catch(e){setError(e.message);}finally{setBusy(false);}}
  return <><article className="review-panel review-workspace"><header><span className="review-label">Selected requirement · {label(row.kind)}</span><h2>Condition {row.condition_id}</h2><p>{title(row)}</p><span className={`review-badge review-${row.state.toLowerCase()}`}>{stateLabel(row.state)}</span><span className={`review-badge review-applicability-${String(row.applicability||'UNASSESSED').toLowerCase()}`}>{row.applicability==='APPLICABLE' ? 'Applicable' : row.applicability==='NOT_APPLICABLE' ? 'Not Applicable' : 'Unassessed'}</span>{row.kind === 'spatial_context' && row.applicability === 'UNASSESSED' && <p className="review-warning">Approving this location also marks it Applicable for this assessment.</p>}</header>
    <div className="review-compare"><section aria-label="Original document evidence"><h3><FileText size={17}/>Permit wording</h3><span className={`review-badge ${row.source.source_verified ? 'review-approved' : 'review-unreviewed'}`}>{row.source.source_verified ? 'Source verified' : 'Source unverified'}</span>{!row.source.source_verified && <p className="review-warning"><AlertTriangle size={16}/>Source verification is unresolved. Human approval does not verify the source.</p>}
      {(row.source.verified_source_spans || row.source.source_spans || []).map((s,i)=><blockquote key={i}><small>Physical page {s.page}{s.model_declared_page!=null && s.model_declared_page!==s.page ? ` · Model-declared page ${s.model_declared_page} · Reconciled page ${s.reconciled_physical_page ?? s.page}` : ''}</small><p>{s.quotation}</p></blockquote>)}{!row.source.source_spans?.length && <p>Source quotation unavailable.</p>}
      {row.source.source_reconciliation && <p>Reconciliation: {label(row.source.source_reconciliation.status)} · Model-declared page {row.source.model_declared_source_page ?? row.source.source_reconciliation.model_declared_source_page ?? 'Not recorded'} · Reconciled pages {(row.source.source_reconciliation.reconciled_physical_pages || []).join(', ') || 'Unresolved'}</p>}
      {row.linked_locations?.map(location=><div className="review-linked-location" key={location.target_id}><h4>Work location used for environmental lookup</h4><p><strong>{label(location.source.location_name)}</strong> · {location.source.latitude}, {location.source.longitude} · {label(location.source.coordinate_system)}</p><small>{location.source.source_verified ? 'Location source verified.' : 'Location source needs verification.'} Reviewed together with this condition; no separate duplicate review item is created.</small></div>)}
    </section>
    <section aria-label="AI / extracted interpretation"><h3>AI interpretation</h3><p>Check this against the permit wording.</p><Interpretation record={raw}/></section></div>
    {(row.effective || row.state==='REJECTED') && <details className="review-previous"><summary>Previously saved interpretation</summary><section aria-label="Effective reviewed interpretation">{row.effective ? <><div className="review-preview"><Preview record={row.effective}/></div><Interpretation record={row.effective} changes={row.review?.corrections || {}} original={raw}/></> : <p>Interpretation rejected. Resolution is required; the source condition remains auditable.</p>}</section></details>}
    <section><h3>Structured correction editor</h3><button className="review-button" onClick={()=>set({editing:!v.editing})}><Pencil size={15}/>{v.editing ? 'Close editor' : 'Edit interpretation'}</button>{v.editing && <><div className="review-form">{row.correction_fields.map(k=><div key={k}><label className="review-enable"><input type="checkbox" checked={Object.hasOwn(v.changes,k)} onChange={e=>{const changes={...v.changes};if(e.target.checked)changes[k]=raw[k] ?? '';else delete changes[k];set({changes});}}/>Correct {names[k] || label(k)}</label>{Object.hasOwn(v.changes,k) && (k==='operator' ? <select aria-label={`Correct ${k}`} value={v.changes[k] ?? ''} onChange={e=>set({changes:{...v.changes,[k]:e.target.value || null}})}>{['','<','<=','>','>=','=','=='].map(x=><option key={x}>{x}</option>)}</select> : <input aria-label={`Correct ${k}`} type={k==='threshold' ? 'number' : 'text'} step="any" value={v.changes[k] ?? ''} onChange={e=>set({changes:{...v.changes,[k]:e.target.value}})}/>)}</div>)}</div><div className="review-preview"><span className="review-label">Unsaved interpretation preview</span><Preview record={{...raw,...v.changes}}/><small>Interpretation preview only; no assessment is performed.</small></div></>}</section>
    <section><h3>Human review decision</h3><div className="review-form"><label>Applicability<select aria-label="Applicability" value={v.applicability} onChange={e=>set({applicability:e.target.value})}><option value="UNASSESSED">Unassessed</option><option value="APPLICABLE">Applicable</option><option value="NOT_APPLICABLE">Not Applicable</option></select></label><label>Reviewer<input value={v.reviewer} onChange={e=>set({reviewer:e.target.value})}/></label></div><p>Rejection does not mean Not Applicable. Explicit Not Applicable requires justification.</p><label className="review-note">Reviewer notes / justification<textarea value={v.note} onChange={e=>set({note:e.target.value})} placeholder="Explain corrections, uncertainty, rejection or applicability…"/></label>{row.review?.reviewed_at && <small>Saved review · {row.review.reviewed_at}</small>}{row.conflict && <p role="alert">{row.conflict} — the review cannot be applied.</p>}{error && <p role="alert">{error}</p>}
      <div className="review-actions">{[['APPROVED','Approve interpretation',CheckCircle2],['CORRECTED','Save correction',Pencil],['REJECTED','Reject interpretation',XCircle],['UNREVIEWED','Keep pending',Clock]].map(([state,text,Icon])=><button key={state} className={`review-button ${state==='APPROVED' ? 'review-primary' : ''}`} disabled={busy || !!row.conflict || state==='CORRECTED' && !Object.keys(v.changes).length} onClick={()=>save(state)}><Icon size={15}/>{text}</button>)}</div>
    </section></article><details className="review-evidence-collapsible"><summary>Evidence routing and provider details</summary><Evidence row={row} session={session} analysis={analysis}/></details></>;
}
function LegacyHumanReview({analysis,session,initialTargetId=null,onUpdated,onLoaded}){
  const [data,setData]=useState(null),[error,setError]=useState(''),[selected,setSelected]=useState(null),[drafts,setDrafts]=useState({}),[saved,setSaved]=useState('');
  const detailRef=useRef(null);
  const [multiSelect,setMultiSelect]=useState(false),[selectedIds,setSelectedIds]=useState([]);
  useEffect(()=>{let active=true;setData(null);setError('');setDrafts({});setSelected(null);setSaved('');setMultiSelect(false);setSelectedIds([]);if(analysis && session)fetch(`/api/reviews?analysis_id=${encodeURIComponent(analysis.analysis_id)}`,{headers:{'X-Session-Id':session.boot_id}}).then(async r=>{const result=await r.json();if(!r.ok)throw new Error(result.error || 'Reviews unavailable');if(result.analysis_run_id!==analysis.analysis_id)throw new Error('REVIEW_IDENTITY_MISMATCH');if(active){setData(result);onLoaded?.(result);}}).catch(e=>{if(active)setError(e.message);});return ()=>{active=false;};},[analysis?.analysis_id,session?.boot_id]);
  if(!analysis)return <div className="empty-state">Select an analysis to review its interpretation.</div>;
  const rows=data?.requirements || [];
  const chosen=rows.find(row=>row.target_id===(selected || initialTargetId)) || rows.find(row=>!reviewResolved(row)) || rows[0];
  const selectTarget=targetId=>{
    if(targetId===chosen?.target_id)return;
    if(unsavedDraft(chosen,drafts[chosen.target_id]) && !window.confirm('Discard unsaved changes?'))return;
    setSelected(targetId);setSaved('');
  };
  const selectedRows=rows.filter(row=>selectedIds.includes(row.target_id));
  const toggleSelection=targetId=>setSelectedIds(previous=>previous.includes(targetId)?previous.filter(id=>id!==targetId):[...previous,targetId]);
  const toggleMultiSelect=()=>{setMultiSelect(value=>!value);setSelectedIds([]);};
  const selectAllVisible=visibleRows=>setSelectedIds(previous=>visibleRows.every(row=>previous.includes(row.target_id))?previous.filter(id=>!visibleRows.some(row=>row.target_id===id)):[...new Set([...previous,...visibleRows.map(row=>row.target_id)])]);
  const savedReview=(result,row)=>{
    setData(result);onUpdated?.(result);
    setDrafts(previous=>{const next={...previous};delete next[row.target_id];return next;});
    const updated=result.requirements || [];
    const currentIndex=updated.findIndex(item=>item.target_id===row.target_id);
    const current=updated[currentIndex];
    const ordered=[...updated.slice(currentIndex+1),...updated.slice(0,currentIndex+1)];
    const next=current && reviewResolved(current) ? ordered.find(item=>item.target_id!==row.target_id && !reviewResolved(item)) : null;
    setSelected(next?.target_id || row.target_id);
    setSaved('Review saved.');
    if(next)window.requestAnimationFrame(()=>detailRef.current?.scrollIntoView?.({behavior:'smooth',block:'start'}));
  };
  return <section className="human-review">
    {error && <p role="alert" className="review-warning">{error}</p>}{saved && <p role="status" className="review-success">{saved}</p>}{!data && !error && <p>Loading reviews…</p>}
    <div className="review-focus-layout">
      <HumanReviewQueue rows={rows} selectedId={chosen?.target_id} onSelect={selectTarget} multiSelect={multiSelect} selectedIds={selectedIds} onMultiSelectToggle={toggleMultiSelect} onToggleSelection={toggleSelection} onSelectAll={visible=>selectAllVisible(visible)}/>
      <div className="review-focus-detail" ref={detailRef}>
        {multiSelect && selectedRows.length ? <HumanReviewBulkToolbar rows={selectedRows} data={data} session={session} onRefresh={updated=>{setData(updated);onUpdated?.(updated);}}/> : chosen ? <Workspace key={chosen.target_id} row={chosen} analysis={analysis} session={session} identity={{analysis_run_id:data.analysis_run_id,document_sha256:data.document_sha256}} draft={drafts[chosen.target_id]} onDraft={draft=>setDrafts(previous=>({...previous,[chosen.target_id]:draft}))} onSaved={result=>savedReview(result,chosen)}/> : <div className="review-panel review-focus-empty">{multiSelect ? 'Select items in the list to choose a bulk action.' : 'Select a review item to begin.'}</div>}
      </div>
    </div>

  </section>;
}
