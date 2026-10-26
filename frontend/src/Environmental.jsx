import React, {useState, useRef, useEffect} from 'react';
import PermitContext from './PermitContext.jsx';
import environmentalLimits from '../../config/environmental_limits.json';

const ENVIRONMENTAL_MAX_FETCH_HOURS = environmentalLimits.max_fetch_hours;
const utcInput = value => value ? `${value.length === 16 ? `${value}:00` : value}Z` : null;

const label = value => (value || '').replaceAll('_', ' ');
export const displayedPointLabel = row => {
  const evidence=row.evidence, point=evidence?.points?.[0];
  if (row.threshold == null) {
    const valid = row.status === 'INFORMATIONAL' && point?.status === 'INFORMATIONAL'
      && typeof point.raw_value === 'number' && Number.isFinite(point.raw_value)
      && !point.validation_notes?.length && !evidence.validation_notes?.length
      && ['COVERED','REFERENCE_EVIDENCE_ONLY'].includes(evidence.temporal_coverage_status)
      && evidence.retrieval_status !== 'FAILED';
    return valid ? 'INFORMATIONAL' : 'NOT DETERMINED';
  }
  return row.status === 'INSUFFICIENT_DATA' ? 'NOT DETERMINED'
    : point?.comparison === true ? 'TRIGGERED' : point?.comparison === false ? 'NOT TRIGGERED' : 'NOT DETERMINED';
};
export const blockerLabel = row => {
  if (row.provider_diagnostic) return `NOT DETERMINED — ${row.provider_diagnostic.provider_error_category}: ${row.provider_diagnostic.provider_error_message}`;
  const notes = (row.evidence?.validation_notes || [row.notes_for_evaluation || '']).join('; ');
  if (/period not fully covered/i.test(notes)) return 'NOT DETERMINED — requested period not fully covered';
  if (/spatial|representativeness|location mismatch/i.test(notes)) return 'NOT DETERMINED — spatial representativeness not established';
  if (/unit/i.test(notes)) return 'NOT DETERMINED — provider unit incompatible with permit requirement';
  if (/depth/i.test(notes)) return 'NOT DETERMINED — explicit compatible depth required';
  if (/source verification required|source quotation.*verification/i.test(notes)) return 'NOT DETERMINED — source verification required';
  if (/threshold|source|interpretation/i.test(notes)) return 'NOT DETERMINED — threshold interpretation requires review';
  return `NOT DETERMINED — ${notes || 'required evidence unavailable'}`;
};
// The extracted operator can describe a trigger rather than an acceptable limit.
// Display literal comparisons; never turn a false trigger into a compliance failure.
const comparisonLabel = row => {
  if (row.comparison_status === 'MANUAL_FNU_REQUIRED') return 'MANUAL FNU REQUIRED';
  if (row.status === 'INSUFFICIENT_DATA') return blockerLabel(row);
  if (!row.evidence || row.threshold == null) return label(row.status);
  if (row.evidence.recency_policy) {
    // Qualification already selected one native reference. Masked/rejected
    // audit points must not turn its valid comparison into a series failure.
    return ({TRIGGERED:'TRIGGERED',NOT_TRIGGERED:'NOT TRIGGERED'})[row.evidence.threshold_evaluation] || 'NOT DETERMINED';
  }
  const values = new Set(row.evidence.points.map(p => p.comparison));
  return values.has(true) ? 'TRIGGERED' :
    values.size === 1 && values.has(false) ? 'NOT TRIGGERED' : 'NOT DETERMINED';
};
export default function Environmental({analysis, session}) {
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [depth, setDepth] = useState('');
  const [pointOnly, setPointOnly] = useState(false);
  const sessionResult = session?.environmental_result;
  const [result, setResult] = useState(() =>
    sessionResult?.analysis_id === analysis?.analysis_id ? sessionResult : null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [manualFnu, setManualFnu] = useState({});
  const alive = useRef(true);
  useEffect(() => {alive.current = true; return () => {alive.current = false;};}, []);
  useEffect(() => {
    if (sessionResult?.analysis_id === analysis?.analysis_id) setResult(sessionResult);
    else if (!sessionResult) setResult(null);
  }, [sessionResult, analysis?.analysis_id]);
  const rows = result?.requirements || analysis?.environmental_mapping || [];
  const evidenceCards = result?.evidence_groups || rows.filter(r => r.evidence?.points?.length);
  const unavailable = result ? rows.filter(r => !r.evidence?.points?.length
    && r.canonical_variable !== 'dissolved_oxygen'
    && (r.provider_diagnostic || r.status === 'INSUFFICIENT_DATA')) : [];
  const extracted = analysis?.environmental_requirements || [];
  const diagnostics = result?.diagnostic_groups?.length ? result.diagnostic_groups : rows.filter(r=>r.provider_diagnostic);
  const providers = result?.provider_status || session?.provider_status || {};
  const capabilities = session?.environmental_capabilities || [];
  const count = name => new Set(rows.filter(r => r.routing.preferred_provider === name).map(r => r.canonical_variable)).size;
  const authoritativeRequirementCount = new Set(rows.map(r => String(r.condition_id)).filter(Boolean)).size;
  const permitContext = <PermitContext key={analysis?.analysis_id} analysis={analysis || {}} session={session}
    onLocation={(lat,lon)=>{setLatitude(String(lat));setLongitude(String(lon));setResult(null);}}
    onDates={(from,until)=>{setStart(from);setEnd(until);setResult(null);}}/>;
  async function fetchEvidence() {
    if (loading || !session) return;
    setLoading(true); setError(''); setResult(null);
    try {
      if (start && end) {
        const hours=(Date.parse(utcInput(end))-Date.parse(utcInput(start)))/3600000;
        if (!(hours>0 && hours<=ENVIRONMENTAL_MAX_FETCH_HOURS)) throw new Error('Invalid requested period');
      }
      const response = await fetch('/api/environmental', {method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Session-Id': session.boot_id},
        body: JSON.stringify({analysis_id: analysis.analysis_id,
          latitude: latitude === '' ? null : Number(latitude), longitude: longitude === '' ? null : Number(longitude),
          start_time: utcInput(start), end_time: utcInput(end),
          depth: depth === '' ? null : Number(depth), point_scope_confirmed: pointOnly,
          manual_fnu_thresholds:Object.fromEntries(Object.entries(manualFnu).filter(([,value])=>value.trim()!=='' && Number.isFinite(Number(value)) && Number(value)>0).map(([key,value])=>[key,Number(value)]))})});
      if (!response.ok) throw new Error('Request failed');
      const evidence = await response.json();
      if (alive.current) setResult(evidence);
    } catch {
      if (alive.current) setError(`Environmental request could not be completed. Check coordinates and UTC period (maximum ${ENVIRONMENTAL_MAX_FETCH_HOURS} hours). No automatic retry.`);
    } finally {if (alive.current) setLoading(false);}
  }
  if (!analysis) return <div className="empty-state"><h2>Environmental Intelligence</h2><p>Analyze a permit to identify its environmental evidence requirements.</p></div>;
  return <div className="environment-panel">
    <div className="page-heading"><div><div className="eyebrow">ENVIRONMENTAL INTELLIGENCE</div><h1>Required environmental evidence</h1><p>{analysis.filename}</p></div></div>
    <p className="notice">Environmental evidence is not operational authorization. All extracted requirements remain unreviewed.</p>
    {analysis.mode === 'MOCK' && <p className="notice warning">Offline preview · Any fetched values are synthetic mocked test evidence.</p>}
    <div className="environment-metrics">{[['Environmental Requirements', authoritativeRequirementCount], ['Copernicus Variables', count('COPERNICUS_MARINE')],
      ['ECMWF Variables', count('ECMWF_FORECAST')], ['Historical / ERA5', count('ERA5')], ['External Evidence', count('EXTERNAL')]].map(([name, value]) =>
      <section className="card metric" key={name}><div className="eyebrow">{name}</div><strong>{value}</strong></section>)}</div>
    <section className="card provider-status"><h2>Provider availability</h2>{Object.entries(providers).map(([name, status]) => <p key={name}><b>{label(name)}</b> · {status}</p>)}</section>
    {!!capabilities.length && <section className="card provider-status" data-testid="capability-coverage"><h2>Environmental capability coverage</h2><div className="capability-grid">{['SUPPORTED','PARTIAL','UNAVAILABLE'].map(status => <div key={status}><div className="eyebrow">{label(status)}</div>{capabilities.filter(c=>c.implementation_status===status).map(c=><p key={c.canonical_variable}><b>{c.display_name}</b> · {c.unit}{c.derived ? ' · derived' : ''}</p>)}</div>)}</div><p className="muted">Informational capability catalogue only; variables are fetched only when required by the permit and explicitly requested.</p></section>}
    {!extracted.length ? <>{permitContext}<div className="empty-state"><p>No explicit environmental data requirements were identified in this permit.</p></div></> : <>
      <section className="card conditions"><div className="section-heading"><h2>Required by Permit / Contract</h2></div>
        <div className="table-scroll"><table><thead><tr>{['Condition', 'Environmental Requirement', 'Variable', 'Provider', 'Threshold', 'Status'].map(h => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i} data-testid="environment-row"><td>{r.condition_id}</td><td className="requirement">{r.requirement_text}
            <details><summary>Source and retrieval notes</summary><p>Physical page {r.source_page} · {r.source_verified ? 'Source quote verified; interpretation unreviewed' : 'Source verification required'}</p>
              {r.source_spans?.map((s,j) => <blockquote key={j}>Page {s.page}: {s.quotation}</blockquote>)}
              <p>{r.notes_for_evaluation}</p>
              {r.canonical_variable === 'turbidity' && r.unit?.toUpperCase() === 'NTU' && r.provider_evidence_unit === 'FNU' && <div>
                <p>Original permit threshold: {r.operator} {r.threshold} NTU · Copernicus evidence unit: FNU.</p>
                <p>Automatic NTU→FNU conversion is not performed. Enter a manually verified FNU threshold to continue. This value is user supplied, not derived by PermitPulse.</p>
                <label>Manual FNU threshold · condition {r.condition_id}<input type="number" min="0" step="any"
                  value={manualFnu[r.requirement_index] ?? ''} onChange={e=>setManualFnu(previous=>({...previous,[r.requirement_index]:e.target.value}))}/></label>
                {manualFnu[r.requirement_index] != null && !(Number.isFinite(Number(manualFnu[r.requirement_index])) && Number(manualFnu[r.requirement_index])>0) && <p role="alert">Enter a finite positive FNU value.</p>}
                <p>Use Fetch Environmental Data to apply. Fresh cached evidence is reused; editing alone never fetches data.</p>
                {r.manual_comparison_threshold && <p>Manual comparison threshold: {r.manual_comparison_threshold.value} FNU · Source: user supplied / manually verified. Original NTU threshold unchanged.</p>}
              </div>}
              {r.provider_diagnostic && <p>Retrieval: Failed · {r.provider_diagnostic.provider_error_category} · {r.provider_diagnostic.provider_error_message}<br/>Dataset: {r.provider_diagnostic.dataset_id || 'Not available'} · Variable: {r.provider_diagnostic.variable}<br/>Requested UTC: {r.provider_diagnostic.request_start} → {r.provider_diagnostic.request_end}</p>}
              <p>Time: {r.temporal_requirement || 'Not stated'} · Depth: {r.depth_requirement || 'Not stated'} · Scope: {r.geographic_scope || 'Not stated'}</p>
              {!!r.routing.potential_source_variables?.length && <p>Potential derived inputs (not automatically fetched): {r.routing.potential_source_variables.join(', ')}</p>}
            </details></td><td>{label(r.canonical_variable)}</td><td>{label(r.routing.preferred_provider)}</td><td>{r.threshold == null ? 'Not stated' : `${r.operator || ''} ${r.threshold} ${r.unit || ''}`}</td><td><span className="category">{comparisonLabel(r)}</span></td></tr>)}</tbody></table></div>
      </section>
      {permitContext}
      <section className="card environment-controls"><h2>Retrieve relevant evidence</h2><p>Additional location or operational timing is required to retrieve environmental evidence. Enter a confirmed point and UTC period; no arbitrary current-time comparison is made.</p>
        {!!analysis.geofences?.length && <details><summary>Source geographic restrictions · {analysis.geofences.length}</summary>{analysis.geofences.map((g,i) => <p key={i}><b>{g.name}</b> · {g.type}<br/>{g.coordinates_or_boundary || g.restriction}<br/>Physical pages {g.source_pages.join(', ')}</p>)}</details>}
        <div className="environment-form">
          <label>Latitude<input type="number" min="-90" max="90" step="any" value={latitude} onChange={e => setLatitude(e.target.value)}/></label>
          <label>Longitude<input type="number" min="-180" max="180" step="any" value={longitude} onChange={e => setLongitude(e.target.value)}/></label>
          <label>Planned start (UTC)<input type="datetime-local" value={start} onInput={e => setStart(e.target.value)} onChange={e => setStart(e.target.value)}/></label>
          <label>Planned end (UTC)<input type="datetime-local" value={end} onInput={e => setEnd(e.target.value)} onChange={e => setEnd(e.target.value)}/></label>
          <label>Depth (m, when applicable)<input type="number" min="0" step="any" value={depth} onChange={e => setDepth(e.target.value)}/></label>
        </div>
        <label className="point-confirm"><input type="checkbox" checked={pointOnly} onChange={e => setPointOnly(e.target.checked)}/> Evaluate this confirmed point only, not an entire route or polygon.</label>
        <p className="muted">Routes and large areas: spatial sampling strategy required. No midpoint is inferred.</p>
        <button className="button primary" onClick={fetchEvidence} disabled={loading || !session}>{loading ? 'Fetching evidence…' : 'Fetch Environmental Data'}</button>
        {error && <p role="alert">{error}</p>}
      </section>
      {diagnostics.filter(r=>r.canonical_variable==='dissolved_oxygen' && r.provider_diagnostic).map((r,i)=><section className="card evidence-card" key={`oxygen-diagnostic-${i}`} data-testid="provider-diagnostic-card"><h2>Dissolved oxygen · provider diagnostic</h2><p>{blockerLabel(r)}</p><dl><dt>Provider / product / dataset / variable</dt><dd>{r.provider_metadata?.provider || r.provider_diagnostic.provider} · {r.provider_metadata?.dataset_name || 'Product metadata unavailable'} · {r.provider_diagnostic.dataset_id} · {r.provider_diagnostic.variable}</dd><dt>Requested nominal depth / mode / tolerance</dt><dd>{r.provider_metadata?.requested_depth_m ?? r.request?.depth ?? 'Unavailable'} m · {r.provider_metadata?.requested_depth_mode || r.request?.requested_depth_mode || 'Unavailable'} · {r.provider_metadata?.depth_tolerance_m ?? 'Unavailable'} m</dd><dt>Native unit / returned UTC range (coverage not established)</dt><dd>{r.provider_metadata?.native_unit || 'Unavailable'} · {r.provider_metadata?.returned_time_start || 'Unavailable'} → {r.provider_metadata?.returned_time_end || 'Unavailable'}</dd><dt>Normalized unit (no screened value)</dt><dd>{r.provider_metadata?.normalized_unit || 'Not established'}</dd><dt>Requested / selected model coordinates</dt><dd>{r.provider_metadata?.requested_coordinates?.join(', ') || 'Unavailable'} · selected {r.provider_metadata?.selected_coordinates?.join(', ') || 'Not determined before depth rejection'}</dd><dt>Depth axis convention</dt><dd>{r.provider_metadata?.depth_axis_unit || 'Unavailable'} · positive {r.provider_metadata?.depth_axis_positive || 'Unavailable'}</dd><dt>Requested / provider query UTC period</dt><dd>{r.request?.start_time || 'Unavailable'} → {r.request?.end_time || 'Unavailable'} · query {r.request?.provider_query_start || 'Unavailable'} → {r.request?.provider_query_end || 'Unavailable'}</dd><dt>Returned provider depth levels</dt><dd>{r.provider_metadata?.returned_depth_levels_m?.join(', ') || 'Unavailable'}</dd><dt>Selected provider depth / difference</dt><dd>{r.provider_metadata?.selected_depth_m ?? 'Unavailable'} / {r.provider_metadata?.depth_difference_m ?? 'Unavailable'} m</dd></dl><p>No usable evidence or threshold result is claimed. Modelled supportive evidence is not an in-situ measurement.</p></section>)}
      {unavailable.map((r,i)=><section className="card evidence-card" key={`unavailable-${i}`} data-testid="unavailable-requirement"><h2>Condition {r.condition_id} · {label(r.canonical_variable)}</h2><p>NOT DETERMINED · evidence unavailable</p><p>Provider mapping: {label(r.routing?.preferred_provider)}</p><p>{r.provider_diagnostic?.provider_error_category}</p><p>{r.provider_diagnostic?.provider_error_message || r.notes_for_evaluation || 'Required evidence unavailable.'}</p><p>{r.requirement_text}</p>{r.provider_diagnostic && <p>Dataset: {r.provider_diagnostic.dataset_id || 'Unavailable'} · Variable: {r.provider_diagnostic.variable || 'Unavailable'}</p>}{r.canonical_variable==='turbidity' && <p>Turbidity evidence unavailable — an applicable mandatory requirement remains UNKNOWN until compatible evidence is available. Not a passing threshold result; source/review safeguards remain required.</p>}</section>)}
      <div className="environment-evidence">{evidenceCards.filter(r => r.evidence?.points?.length).map((r,i) => <section className="card evidence-card" key={i} data-testid="evidence-card">
        <h2>{label(r.canonical_variable)}</h2><p>{r.evidence.data_type === 'MODEL_FORECAST' ? 'Retrieved point / representative model value (not a compliance conclusion)' : r.evidence.data_type === 'REANALYSIS' ? 'Reanalysis value' : 'Satellite observation'}</p>
        <strong className="evidence-value">{r.evidence.points[0].raw_value ?? 'Missing'} {r.evidence.points[0].unit}</strong>
        <dl><dt>Source threshold check</dt><dd>{r.threshold == null ? 'No structured threshold · inspect source for interpretation' : `${r.operator || ''} ${r.threshold} ${r.unit || ''}`}</dd>
          {r.manual_comparison_threshold && <><dt>Manual comparison threshold (not permit value)</dt><dd>{r.manual_comparison_threshold.value} FNU · USER SUPPLIED / manually verified</dd></>}
          <dt>Provider / dataset</dt><dd>{label(r.evidence.provider)} · {r.evidence.dataset_name} · {r.evidence.dataset_id}</dd>
          <dt>Data timestamp (UTC)</dt><dd>{r.evidence.points[0].data_time}</dd><dt>Retrieved</dt><dd>{r.evidence.retrieved_at}</dd>
          {r.evidence.recency_policy && <><dt>Reference-evidence recency policy</dt><dd>Historical/reference evidence, not contemporaneous continuous validity · actual source time {r.evidence.recency_policy.source_timestamp || 'Unavailable'} · assessed at {r.evidence.recency_policy.assessed_time || 'Unavailable'} · age {r.evidence.recency_policy.age_hours ?? 'Unknown'} hours · maximum {r.evidence.recency_policy.max_age_hours} hours · {r.evidence.recency_policy.reason_code || 'Within recency policy'}</dd><dt>Native / normalized unit</dt><dd>{r.evidence.points[0].unit} / {r.evidence.points[0].normalized_unit || 'Unavailable'}</dd><dt>Provider variable / evidence mode</dt><dd>{r.evidence.dataset_variable} · {r.evidence.data_type}</dd></>}
          <dt>Requested coordinates</dt><dd>{r.evidence.requested_coordinates?.join(', ') || 'Unavailable'}</dd>
          <dt>Selected model grid coordinates / depth</dt><dd>{r.evidence.latitude}, {r.evidence.longitude} · {(r.evidence.selected_depth_m ?? r.evidence.depth) == null ? 'Not applicable' : `${r.evidence.selected_depth_m ?? r.evidence.depth} m`}{r.evidence.requested_depth_m != null && <> · requested {r.evidence.requested_depth_m} m · difference {r.evidence.depth_difference_m ?? 'unknown'} m</>}</dd>
          {r.canonical_variable === 'dissolved_oxygen' && <><dt>Model oxygen depth interpretation</dt><dd>{r.evidence.requested_depth_mode || 'Not supplied'} · tolerance {r.evidence.depth_tolerance_m ?? 'Not supplied'} m · modelled supportive evidence, not an in-situ measurement.</dd></>}
          <dt>Spatial resolution / distance</dt><dd>{r.evidence.spatial_resolution || 'Unavailable'} · {r.evidence.distance_km ?? 'Unknown'} km</dd>
          <dt>Spatial representativeness</dt><dd>{label(r.evidence.quality_status)} · Conservative maximum distance: {r.evidence.max_representative_distance_km ?? 'Unavailable'} km</dd>
          <dt>Evidence retrieval</dt><dd>{r.evidence.retrieval_status || r.retrieval_status || 'Available'}</dd>
          <dt>Temporal coverage</dt><dd>{r.evidence.temporal_coverage_status || 'Not established'}</dd>
          {r.canonical_variable === 'mean_wave_direction' && <><dt>Wave direction convention</dt><dd>{r.evidence.direction_convention || 'Provider convention unavailable'} · {r.evidence.direction_metadata?.long_name} · {r.evidence.direction_metadata?.standard_name} · Native unit {r.evidence.direction_metadata?.units || r.evidence.points[0].unit}. No FROM/TOWARDS conversion.</dd></>}
          <dt>Spatial distance check</dt><dd>{label(r.evidence.spatial_distance_status) || 'Not established'}</dd>
          {r.evidence.cell_selection && <><dt>Cell selection / grid check</dt><dd>{r.evidence.cell_selection} · {r.evidence.spatial_check_basis}</dd></>}
          {r.evidence.fallback_reason && <><dt>Coarse model fallback</dt><dd>{r.evidence.fallback_reason}</dd></>}
          <dt>Period evidence status</dt><dd>{r.status === 'INSUFFICIENT_DATA' ? 'INSUFFICIENT DATA' : 'Available for point comparisons only'}</dd>
          {r.canonical_variable === 'dissolved_oxygen' && <><dt>Evidence qualification</dt><dd>MODELLED SUPPORTIVE EVIDENCE · Modelled dissolved oxygen is not equivalent to in-situ monitoring.</dd></>}
          {r.canonical_variable === 'precipitation' && <><dt>Precipitation semantics</dt><dd>Hourly accumulated precipitation; values are not rates.</dd></>}
          {r.canonical_variable === 'sea_surface_height' && <><dt>Sea-surface-height limitation</dt><dd>Model water-level context only; not a chart datum, harbour tide gauge or navigational clearance.</dd></>}
          <dt>Threshold screening</dt><dd>{r.status === 'INSUFFICIENT_DATA' ? blockerLabel(r) : 'Threshold screening available; no operational authorization'}</dd>
          {r.evidence.coverage && <><dt>Requested UTC period</dt><dd>{r.evidence.coverage.requested_start} → {r.evidence.coverage.requested_end}</dd>
            <dt>Provider query UTC period</dt><dd>{r.evidence.coverage.provider_query_start} → {r.evidence.coverage.provider_query_end}</dd>
            <dt>Temporal resolution</dt><dd>{r.evidence.coverage.temporal_resolution_seconds ?? 'Unavailable'} seconds</dd>
            <dt>Actual evidence UTC period</dt><dd>{r.evidence.coverage.actual_start || 'Unavailable'} → {r.evidence.coverage.actual_end || 'Unavailable'}</dd></>}</dl>
        {!!r.checks?.length && <div><h3>Threshold checks</h3><p>Shared retrieval supports Conditions {[...new Set(r.checks.map(check=>check.condition_id))].join(', ')}.</p><p>Literal screening across returned points; any true point triggers. Not a compliance conclusion or operational authorization.</p>{r.checks.map((check,j)=><p key={j} data-testid="threshold-check">Condition {check.condition_id} · {check.operator} {check.manual_comparison_threshold?.value ?? check.threshold ?? 'Not stated'} {check.manual_comparison_threshold?.unit || check.unit}{check.manual_comparison_threshold && ' (USER SUPPLIED; not permit threshold)'} — Series: {comparisonLabel(check)} · Displayed point: {displayedPointLabel(check)}{check.derivation && <> · {label(check.derivation.method)}</>}</p>)}</div>}
        {(r.checks || [r]).filter(check=>check.evidence?.canonical_variable === 'surface_current_direction').map((check,j)=><div key={`direction-${j}`} data-testid="current-direction-details"><h3>Current direction · DERIVED FROM COPERNICUS U/V</h3><p>{check.status} · {check.evidence.points?.[0]?.raw_value ?? 'Unavailable'} degrees · {check.evidence.direction_convention}</p><p>Native timestamp: {check.evidence.points?.[0]?.data_time || 'Unavailable'}. Derivation: {check.evidence.points?.[0]?.derivation?.method || 'Unavailable'}. Retained signed components: U {check.evidence.points?.[0]?.component_values?.uo ?? 'Unavailable'}, V {check.evidence.points?.[0]?.component_values?.vo ?? 'Unavailable'}. Informational only; not an independent decision gate.</p></div>)}
        <p className="notice">{r.evidence.qualification || 'Not a compliance conclusion or operational authorization.'}</p>
        <p>{r.notes_for_evaluation}</p><p className="muted">{r.evidence.comparison_scope}</p>
        <details><summary>All retrieved points · {r.evidence.points.length}</summary><div className="table-scroll"><table className="retrieved-points"><thead><tr><th>UTC time</th><th>Source value</th></tr></thead><tbody>{r.evidence.points.map((p,j) => <tr key={j} data-testid="retrieved-point"><td>{p.data_time || 'Unavailable timestamp'}</td><td>{p.raw_value ?? 'Missing'} {p.unit}
          <details><summary>Evaluation details</summary><p>Normalized: {p.normalized_value ?? 'Unavailable'} {p.normalized_unit}</p><p>{p.status === 'INSUFFICIENT_DATA' ? 'INSUFFICIENT DATA' : p.comparison === true ? 'Threshold comparison true' : p.comparison === false ? 'Threshold comparison false' : label(p.status)}</p>{p.validation_notes?.map((note,k)=><p key={k}>{note}</p>)}</details></td></tr>)}</tbody></table></div></details>
      </section>)}</div>
    </>}
  </div>;
}
