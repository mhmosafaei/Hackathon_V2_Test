import React, { useState } from 'react';
import { CheckCircle2, ShieldCheck, Search } from 'lucide-react';
import './HumanReviewBulk.css';
import './HumanReviewBulkToolbar.css';

const title = row => row.original?.requirement_text || row.original?.requirement || row.original?.description || `Condition ${row.condition_id}`;
const reviewLabel = value => ({ APPROVED: 'Approved', REJECTED: 'Rejected', CORRECTED: 'Corrected', UNREVIEWED: 'Pending' }[value] || 'Pending');
const applicabilityLabel = value => ({ APPLICABLE: 'Applicable', NOT_APPLICABLE: 'Not Applicable', UNASSESSED: 'Unassessed' }[value] || 'Unassessed');

function BulkMenu({ mode, rows, data, session, onRefresh, close }) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(new Set());
  const [reviewStatus, setReviewStatus] = useState('APPROVED');
  const [applicability, setApplicability] = useState('UNASSESSED');
  const [note, setNote] = useState('');
  const [message, setMessage] = useState('');
  const eligible = rows.filter(row => row.kind !== 'spatial_context' && !row.conflict && (mode === 'review' ? Boolean(row.source?.source_verified) : true));
  const displayed = rows.filter(row => row.kind !== 'spatial_context' && `${row.condition_id} ${title(row)}`.toLowerCase().includes(query.toLowerCase()));
  const toggle = id => setSelected(previous => { const next = new Set(previous); next.has(id) ? next.delete(id) : next.add(id); return next; });
  async function submit() {
    if (!selected.size || (mode === 'app' && applicability === 'UNASSESSED' && !note.trim() && false)) return;
    const action = mode === 'review' ? reviewLabel(reviewStatus) : applicabilityLabel(applicability);
    if (!window.confirm(`${mode === 'review' ? action + ' interpretations' : 'Set conditions to ' + action} for ${selected.size} selected condition(s)?`)) return;
    let succeeded = 0; const failed = [];
    for (const id of selected) {
      const row = rows.find(item => item.target_id === id);
      const payload = { analysis_run_id: data.analysis_run_id, document_sha256: data.document_sha256, review: { original_fingerprint: row.original_fingerprint, state: mode === 'review' ? reviewStatus : row.state, applicability: mode === 'review' ? row.applicability : applicability, corrections: row.review?.corrections || {}, reviewer: row.review?.reviewer || 'Local reviewer', note: mode === 'app' && applicability === 'NOT_APPLICABLE' ? note : row.review?.note || '' } };
      try { const response = await fetch(`/api/reviews/${encodeURIComponent(id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-Session-Id': session.boot_id }, body: JSON.stringify(payload) }); if (!response.ok) throw new Error(`HTTP ${response.status}`); const updated = await response.json(); succeeded += 1; onRefresh(updated); } catch (error) { failed.push(`${row.condition_id}: ${error.message}`); }
    }
    setMessage(failed.length ? `${succeeded} succeeded; ${failed.length} failed — ${failed.join(' · ')}` : `${succeeded} operation(s) succeeded.`);
    setSelected(new Set());
  }
  return <div className="bulk-popover" role="dialog">
    <label className="bulk-search"><Search size={15} /><input aria-label="Search conditions" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search conditions…" /></label>
    <div className="bulk-list">{displayed.map(row => { const canSelect = eligible.includes(row); return <label key={row.target_id}><input type="checkbox" disabled={!canSelect} checked={selected.has(row.target_id)} onChange={() => canSelect && toggle(row.target_id)} /><span><b>#{row.condition_id} · {title(row)}</b><small>Review: {reviewLabel(row.state)} · Applicability: {applicabilityLabel(row.applicability)}</small><small>{canSelect ? 'Eligible' : row.kind === 'spatial_context' ? 'Spatial review required' : row.conflict ? 'Review conflict' : row.state !== 'UNREVIEWED' && mode === 'review' ? 'Already reviewed' : !row.source?.source_verified ? 'Source unverified' : 'Ineligible'}</small></span></label>; })}</div>
    <div className="bulk-controls"><button type="button" onClick={() => setSelected(new Set(eligible.map(row => row.target_id)))}>Select All Eligible</button><button type="button" onClick={() => setSelected(new Set())}>Clear Selection</button><span>{selected.size} selected · {displayed.length} conditions</span></div>
    {mode === 'review' ? <select aria-label="Bulk review status" value={reviewStatus} onChange={event => setReviewStatus(event.target.value)}><option value="APPROVED">Approve interpretations</option><option value="REJECTED">Reject interpretations</option><option value="UNREVIEWED">Keep pending</option></select> : <><select aria-label="Bulk applicability" value={applicability} onChange={event => setApplicability(event.target.value)}><option value="UNASSESSED">Unassessed</option><option value="APPLICABLE">Applicable</option><option value="NOT_APPLICABLE">Not Applicable</option></select>{applicability === 'NOT_APPLICABLE' && <textarea aria-label="Justification" required value={note} onChange={event => setNote(event.target.value)} placeholder="Justification required" />}</>}
    <button className="review-button review-primary" disabled={!selected.size || (mode === 'app' && applicability === 'NOT_APPLICABLE' && !note.trim())} onClick={submit}>{mode === 'review' ? 'Apply Review Status' : 'Apply Applicability'} ({selected.size})</button>{message && <p role="status">{message}</p>}<button type="button" className="bulk-close" onClick={close}>Close</button>
  </div>;
}

export default function HumanReviewBulkToolbar({ rows, data, session, onRefresh }) {
  const [open, setOpen] = useState(null);
  return <div className="review-bulk-toolbar"><button className="review-button" onClick={() => setOpen(open === 'review' ? null : 'review')}><CheckCircle2 size={15} />Bulk Review</button><button className="review-button" onClick={() => setOpen(open === 'app' ? null : 'app')}><ShieldCheck size={15} />Bulk Applicability</button>{open && <BulkMenu mode={open} rows={rows} data={data} session={session} onRefresh={onRefresh} close={() => setOpen(null)} />}</div>;
}