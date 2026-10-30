import React, {useState} from 'react';
import {CheckCircle2} from 'lucide-react';
import './HumanReviewBulk.css';
import './HumanReviewBulkToolbar.css';

export default function HumanReviewBulkToolbar({rows, data, session, onRefresh}) {
  const [approve, setApprove] = useState(true);
  const [applicability, setApplicability] = useState('APPLICABLE');
  const [reviewer, setReviewer] = useState('Local reviewer');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const excluded = rows.filter(row => row.source?.source_verified !== true || row.conflict);
  const eligible = rows.filter(row => row.source?.source_verified === true && !row.conflict);
  const missingJustification = applicability === 'NOT_APPLICABLE' && !note.trim();

  async function apply() {
    if (!eligible.length || busy || !reviewer.trim() || missingJustification) return;
    if (!window.confirm(`Save approval and applicability for ${eligible.length} eligible item(s)? ${excluded.length} item(s) will be skipped.`)) return;
    setBusy(true); setMessage('');
    let succeeded = 0; const failures = [];
    for (const row of eligible) {
      const review = {
        original_fingerprint: row.original_fingerprint,
        state: approve ? (Object.keys(row.review?.corrections || {}).length ? 'CORRECTED' : 'APPROVED') : row.state,
        applicability,
        corrections: row.review?.corrections || {}, reviewer,
        note: applicability === 'NOT_APPLICABLE' ? note : row.review?.note || ''
      };
      try {
        const response = await fetch(`/api/reviews/${encodeURIComponent(row.target_id)}`, {
          method: 'PUT', headers: {'Content-Type': 'application/json', 'X-Session-Id': session.boot_id},
          body: JSON.stringify({analysis_run_id: data.analysis_run_id, document_sha256: data.document_sha256, review})
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
        succeeded += 1; onRefresh(result);
      } catch (error) { failures.push(`Condition ${row.condition_id}: ${error.message}`); }
    }
    setMessage(failures.length ? `${succeeded} applied; ${failures.length} failed. ${failures.join(' · ')}` : `${succeeded} item(s) updated.${excluded.length ? ` ${excluded.length} skipped; review them individually.` : ''}`);
    setBusy(false);
  }

  return <article className="review-panel review-bulk-selection-panel">
    <header className="bulk-review-header"><span className="review-label">MULTI-SELECT REVIEW</span><h2>{rows.length} item{rows.length === 1 ? '' : 's'} selected</h2><p>Review these items together, then save both decisions in one step.</p></header>
    <section className="bulk-combined-form">
      <label className="bulk-approval-check"><input type="checkbox" checked={approve} disabled={busy} onChange={event => setApprove(event.target.checked)}/><span><strong>Approve AI interpretations</strong><small>I have checked the selected interpretations against the permit wording.</small></span></label>
      <div className="bulk-review-fields"><label>Applicability<select aria-label="Bulk Applicability value" disabled={busy} value={applicability} onChange={event => setApplicability(event.target.value)}><option value="APPLICABLE">Applicable to this work</option><option value="NOT_APPLICABLE">Not Applicable to this work</option><option value="UNASSESSED">Unassessed</option></select></label><label>Reviewer<input aria-label="Bulk reviewer" disabled={busy} value={reviewer} onChange={event => setReviewer(event.target.value)}/></label></div>
      {applicability === 'NOT_APPLICABLE' && <label>Justification<textarea aria-label="Bulk Not Applicable justification" disabled={busy} value={note} onChange={event => setNote(event.target.value)} placeholder="Explain why these items do not apply"/></label>}
      {excluded.length > 0 && <div className="bulk-skipped-notice" role="status"><strong>{excluded.length} item(s) excluded from this bulk action</strong><p>You can save the remaining {eligible.length} item(s). Skipped items remain available for individual review.</p><ul>{excluded.map(row=><li key={row.target_id}>Condition {row.condition_id}: {row.conflict ? 'Review conflict' : 'Source verification unresolved'}</li>)}</ul></div>}
    </section>
    <footer className="bulk-review-footer"><span>Changes apply to {eligible.length} eligible item(s).</span><button type="button" className="review-button review-primary" disabled={!eligible.length || busy || !reviewer.trim() || missingJustification} onClick={apply}><CheckCircle2 size={17}/>{busy ? 'Saving…' : 'Save Selected Reviews'}</button></footer>
    {message && <p role="status">{message}</p>}
  </article>;
}
