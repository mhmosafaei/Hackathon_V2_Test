import React, {useEffect, useMemo, useState} from 'react';

const isResolved = row => !row.conflict && ['APPROVED', 'CORRECTED'].includes(row.state)
  && ['APPLICABLE', 'NOT_APPLICABLE'].includes(row.applicability)
  && (row.applicability !== 'NOT_APPLICABLE' || row.review?.note?.trim());
const heading = row => {
  const source = row.original || {};
  const shortRequirement = String(source.requirement_text || source.requirement || '').trim();
  return String(source.display_name || source.title || source.name || (shortRequirement.length < 90 && shortRequirement)
    || source.variable || source.canonical_variable || source.requirement_text || source.requirement
    || source.description || 'Review item').replaceAll('_', ' ');
};

export default function HumanReviewQueue({rows, selectedId, onSelect}) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('PENDING');
  const pending = rows.filter(row => !isResolved(row)).length;
  useEffect(() => { if (rows.length && pending === 0) setFilter('ALL'); }, [rows.length, pending]);
  useEffect(() => { const selected = rows.find(row => row.target_id === selectedId); if (selected && isResolved(selected)) setFilter(current => current === 'PENDING' ? 'ALL' : current); }, [rows, selectedId]);
  const shown = useMemo(() => rows.filter(row => {
    const match = `${row.condition_id} ${row.kind} ${heading(row)} ${row.original?.requirement_text || ''} ${row.original?.requirement || ''} ${(row.source?.source_spans || []).map(span => span.page).join(' ')}`.toLowerCase().includes(query.trim().toLowerCase());
    const state = filter === 'ALL' || (filter === 'PENDING' && !isResolved(row))
      || (filter === 'REVIEWED' && isResolved(row)) || (filter === 'SOURCE_GAPS' && (!row.source?.source_verified || row.conflict));
    return match && state;
  }), [rows, query, filter]);
  return <aside className="review-panel review-queue" aria-label="Review item list">
    <div className="review-queue-header"><h2>Review items</h2><span>{pending} to check</span></div>
    <label className="review-queue-search">Search items<input aria-label="Search review items" value={query} onChange={event => setQuery(event.target.value)} placeholder="Number or keyword"/></label>
    <div className="review-queue-tabs" role="group" aria-label="Review list filter">
      {[['PENDING', 'To check'], ['ALL', 'All'], ['REVIEWED', 'Reviewed'], ['SOURCE_GAPS', 'Source gaps']].map(([value, name]) => <button type="button" key={value} className={filter === value ? 'is-active' : ''} aria-pressed={filter === value} onClick={() => setFilter(value)}>{name}</button>)}
    </div>
    <p className="review-queue-count">Showing {shown.length} of {rows.length}</p>
    <div className="review-queue-list">{shown.map(row => <button type="button" key={row.target_id} className="review-queue-item" aria-label={`Review item ${row.condition_id}: ${heading(row)}`} aria-current={selectedId === row.target_id ? 'true' : undefined} onClick={() => onSelect(row.target_id)}>
      <span className="review-queue-number">{row.condition_id}</span><span className="review-queue-copy"><strong>{heading(row)}</strong><small>{row.kind === 'spatial_context' ? 'Location' : 'Condition'} · {isResolved(row) ? 'Reviewed' : 'Needs review'}{!row.source?.source_verified ? ' · Source check' : ''}</small></span>
    </button>)}</div>
    {!shown.length && <p className="review-queue-empty">{filter === 'PENDING' && pending === 0 ? 'All items are reviewed. Choose All to inspect or edit them.' : 'No items match. Try another filter or search.'}</p>}
  </aside>;
}
