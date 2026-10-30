import React, {useState, useRef, useEffect} from 'react';
import PermitContext from './PermitContext.jsx';
import RequirementProviders from './RequirementProviders.jsx';
import EnvironmentalResultsMap from './EnvironmentalResultsMap.jsx';
import {environmentDefaults, boundedPeriod} from './environmentDefaults.js';
import './EnvironmentalWorkflow.css';
import environmentalLimits from '../../config/environmental_limits.json';
import {FileText, Waves, Wind, Database, Cloud, Eye, Droplets, Thermometer, Gauge, ArrowRight, ArrowUp, MoveHorizontal, Clock3, AlertTriangle, CheckCircle2, Info, MapPin, CalendarDays, Search, Filter, Download, Shield} from 'lucide-react';
import {num} from './formatNumber.js';

const ENVIRONMENTAL_MAX_FETCH_HOURS = environmentalLimits.max_fetch_hours;
const utcInput = value => value ? `${value.length === 16 ? `${value}:00` : value}Z` : null;

const label = value => (value || '').replaceAll('_', ' ');
const environmentIcon = value => {
  const name = String(value || '').toLowerCase();
  if (name.includes('wave') && name.includes('period')) return Clock3;
  if (name.includes('wave')) return Waves;
  if (name.includes('wind')) return Wind;
  if (name.includes('eastward')) return ArrowRight;
  if (name.includes('northward')) return ArrowUp;
  if (name.includes('current speed')) return MoveHorizontal;
  if (name.includes('visibility')) return Eye;
  if (name.includes('turbidity')) return Droplets;
  if (name.includes('temperature')) return Thermometer;
  if (name.includes('precipitation')) return Cloud;
  return Gauge;
};
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
export default function Environmental({analysis, session, reviewData, onQueryConfirmed, active=true}) {
  const defaults = environmentDefaults(analysis, reviewData);
  const edited = useRef(new Set());
  const dateAdjustmentKey=JSON.stringify([defaults.start,defaults.end,defaults.originalEnd]);
  const seenDateAdjustment=useRef(dateAdjustmentKey);
  const [dateAdjustment,setDateAdjustment]=useState(()=>defaults.rangeAdjusted ? {start:defaults.start,originalEnd:defaults.originalEnd,end:defaults.end,testWindow:defaults.testWindow} : null);
  useEffect(()=>{
    if (seenDateAdjustment.current===dateAdjustmentKey || edited.current.has('start') || edited.current.has('end')) return;
    seenDateAdjustment.current=dateAdjustmentKey;
    setDateAdjustment(defaults.rangeAdjusted ? {start:defaults.start,originalEnd:defaults.originalEnd,end:defaults.end,testWindow:defaults.testWindow} : null);
  },[dateAdjustmentKey]);
  const [latitude, setLatitude] = useState(defaults.latitude);
  const [longitude, setLongitude] = useState(defaults.longitude);
  const [start, setStart] = useState(defaults.start);
  const [end, setEnd] = useState(defaults.end);
  const [depth, setDepth] = useState('0');
  const [scopeType, setScopeType] = useState('point');
  const pointOnly = scopeType === 'point';
  const dataSourceRef = useRef(null);
  const resultsRef = useRef(null);
  const [confirmedKey, setConfirmedKey] = useState(null);
  const inputKey = JSON.stringify([latitude,longitude,start,end,depth,pointOnly]);
  const confirmed = confirmedKey === inputKey;
  const canFetch = confirmed;
  useEffect(() => {
    for (const [key,setter] of [['latitude',setLatitude],['longitude',setLongitude],['start',setStart],['end',setEnd]]) {
      if (!edited.current.has(key) && defaults[key] !== '') setter(defaults[key]);
    }
  }, [defaults.latitude, defaults.longitude, defaults.start, defaults.end]);
  useEffect(() => {
    if (!confirmed || !dataSourceRef.current) return;
    const section = dataSourceRef.current;
    section.style.scrollMarginTop = `${(document.querySelector('.header')?.getBoundingClientRect().height || 0) + 16}px`;
    section.scrollIntoView?.({behavior:'smooth',block:'start'});
  }, [confirmed]);
  const sessionResult = session?.environmental_result;
  const [result, setResult] = useState(() =>
    sessionResult?.analysis_id === analysis?.analysis_id ? sessionResult : null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [manualFnu, setManualFnu] = useState({});
  const alive = useRef(true);
  useEffect(() => {alive.current = true; return () => {alive.current = false;};}, []);
  useEffect(() => {
    if (edited.current.size) return;
    if (sessionResult?.analysis_id === analysis?.analysis_id) setResult(sessionResult);
    else if (!sessionResult) setResult(null);
  }, [sessionResult, analysis?.analysis_id]);
  const hasResult = !!result;
  useEffect(() => {
    if (!active || !hasResult || !resultsRef.current) return;
    resultsRef.current.style.scrollMarginTop = `${(document.querySelector('.header')?.getBoundingClientRect().height || 0) + 16}px`;
    resultsRef.current.scrollIntoView?.({behavior:'smooth',block:'start'});
  }, [hasResult, active]);
  const rows = result?.requirements || analysis?.environmental_mapping || [];
  const evidenceCards = result?.evidence_groups || rows.filter(r => r.evidence?.points?.length);
  const unavailable = result ? rows.filter(r => !r.evidence?.points?.length
    && r.canonical_variable !== 'dissolved_oxygen'
    && (r.provider_diagnostic || r.status === 'INSUFFICIENT_DATA')) : [];
  const extracted = analysis?.environmental_requirements || [];
  const diagnostics = result?.diagnostic_groups?.length ? result.diagnostic_groups : rows.filter(r=>r.provider_diagnostic);
  const providers = result?.provider_status || session?.provider_status || {};
  const capabilities = session?.environmental_capabilities || [];
  const permitContext = <PermitContext key={analysis?.analysis_id} analysis={{...analysis,...reviewData?.decision_context}} session={session}
    onLocation={(lat,lon)=>{edited.current.add('latitude');edited.current.add('longitude');setLatitude(String(lat));setLongitude(String(lon));setResult(null);}}
    onDates={(from,until)=>{edited.current.add('start');edited.current.add('end');setStart(from);setEnd(until);setResult(null);}}/>;
  function confirmInputs() {
    const hours=(Date.parse(utcInput(end))-Date.parse(utcInput(start)))/3600000;
    if (latitude === '' || longitude === '' || !Number.isFinite(Number(latitude)) || Math.abs(Number(latitude))>90 || !Number.isFinite(Number(longitude)) || Math.abs(Number(longitude))>180) {setError('Enter valid WGS84 latitude and longitude.');return;}
    if (hours>ENVIRONMENTAL_MAX_FETCH_HOURS) {const period=boundedPeriod(start,end);setEnd(period.end);edited.current.add('end');setError('');setDateAdjustment({start,originalEnd:end,end:period.end});return;}
    if (!start || !end || !(hours>0 && hours<=ENVIRONMENTAL_MAX_FETCH_HOURS)) {setError(`Select a positive UTC period of at most ${ENVIRONMENTAL_MAX_FETCH_HOURS} hours.`);return;}
    if (depth !== '' && (!Number.isFinite(Number(depth)) || Number(depth)<0 || Number(depth)>10000)) {setError('Enter a depth between 0 and 10000 metres, or leave it blank.');return;}
    if (!pointOnly) {setError('Polygon retrieval is not available yet. Select Point to continue.');return;}
    edited.current.add('confirmed');setError('');setConfirmedKey(inputKey);setResult(null);onQueryConfirmed?.({analysis_id:analysis.analysis_id,start_time:utcInput(start),end_time:utcInput(end)});
  }
  async function fetchEvidence() {
    if (loading || !session || !canFetch) return;
    setLoading(true); setError(''); setResult(null);
    try {
      if (start && end) {
        const hours=(Date.parse(utcInput(end))-Date.parse(utcInput(start)))/3600000;
        if (!(hours>0 && hours<=ENVIRONMENTAL_MAX_FETCH_HOURS)) throw new Error(`Select an end time after the start time, within ${ENVIRONMENTAL_MAX_FETCH_HOURS} hours`);
      }
      const response = await fetch('/api/environmental', {method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Session-Id': session.boot_id},
        body: JSON.stringify({analysis_id: analysis.analysis_id,
          latitude: latitude === '' ? null : Number(latitude), longitude: longitude === '' ? null : Number(longitude),
          start_time: utcInput(start), end_time: utcInput(end),
          depth: depth === '' ? null : Number(depth), point_scope_confirmed: pointOnly,
          manual_fnu_thresholds:Object.fromEntries(Object.entries(manualFnu).filter(([,value])=>value.trim()!=='' && Number.isFinite(Number(value)) && Number(value)>0).map(([key,value])=>[key,Number(value)]))})});
      if (!response.ok) {
        let detail = '';
        try {
          const payload = await response.json();
          const reason = payload.detail ?? payload.error ?? payload.message;
          if (Array.isArray(reason)) {
            detail = reason.map(item => {
              const location = Array.isArray(item.loc) ? `${item.loc.join('.')}: ` : '';
              return `${location}${item.msg || JSON.stringify(item)}`;
            }).join('; ');
          } else if (typeof reason === 'string') detail = reason;
        } catch { /* Non-JSON server errors are reported by HTTP status. */ }
        throw new Error(`HTTP ${response.status}${detail ? ` — ${detail}` : ''}`);
      }
      const evidence = await response.json();
      if (alive.current) setResult(evidence);
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Unknown request error';
      if (alive.current) setError(`Environmental request failed: ${message}. No automatic retry.`);
    } finally {if (alive.current) setLoading(false);}
  }
  const renderVariableDetails = matching => <>{matching.map((r,i)=><React.Fragment key={i}>
              {r.canonical_variable === 'turbidity' && r.unit?.toUpperCase() === 'NTU' && r.provider_evidence_unit === 'FNU' && <div>
                <p>Original permit threshold: {r.operator} {r.threshold} NTU · Copernicus evidence unit: FNU.</p>
                <p>Automatic NTU→FNU conversion is not performed. Enter a manually verified FNU threshold to continue. This value is user supplied, not derived by PermitPulse.</p>
                <label>Manual FNU threshold · condition {r.condition_id}<input type="number" min="0" step="any"
                  value={manualFnu[r.requirement_index] ?? ''} onChange={e=>setManualFnu(previous=>({...previous,[r.requirement_index]:e.target.value}))}/></label>
                {manualFnu[r.requirement_index] != null && !(Number.isFinite(Number(manualFnu[r.requirement_index])) && Number(manualFnu[r.requirement_index])>0) && <p role="alert">Enter a finite positive FNU value.</p>}
                <p>Use Fetch Environmental Data to apply. Fresh cached evidence is reused; editing alone never fetches data.</p>
                {r.manual_comparison_threshold && <p>Manual comparison threshold: {r.manual_comparison_threshold.value} FNU · Source: user supplied / manually verified. Original NTU threshold unchanged.</p>}
              </div>}
  </React.Fragment>)}</>;
  if (!analysis) return <div className="empty-state"><h2>Environmental Intelligence</h2><p>Analyze a permit to identify its environmental evidence requirements.</p></div>;
  return <div className="environment-panel">
    {analysis.mode === 'MOCK' && <p className="notice warning">Offline preview · Any fetched values are synthetic mocked test evidence.</p>}
    {!extracted.length ? <>{permitContext}<div className="empty-state"><p>No explicit environmental data requirements were identified in this permit.</p></div></> : <>
      <section className="card environment-controls environment-setup-step"><div className="environment-step-label">1 · LOCATION & TIME</div><h2>Confirm Location & Time</h2><p className="environment-prefill-note"><span className="environment-prefill-intro">Confirm where and when you plan to work, then fetch the environmental data required by your permit.</span></p>{!defaults.latitude && permitContext}
        {!!analysis.geofences?.length && <details><summary>Source geographic restrictions · {analysis.geofences.length}</summary>{analysis.geofences.map((g,i) => <p key={i}><b>{g.name}</b> · {g.type}<br/>{g.coordinates_or_boundary || g.restriction}<br/>Physical pages {g.source_pages.join(', ')}</p>)}</details>}
        <label className="environment-scope-selector">Assessment Geometry<select value={scopeType} onChange={e=>{edited.current.add('scopeType');setScopeType(e.target.value);setResult(null);}}><option value="point">Point</option><option value="polygon">Polygon (coming soon)</option></select></label>
        {!pointOnly && <p role="status" className="environment-polygon-placeholder">Polygon input will be supported here in a future update. Select Point to retrieve data for one confirmed location.</p>}
        {pointOnly && <div className="environment-form">
          <label>Latitude<input type="number" min="-90" max="90" step="any" value={latitude} onChange={e => {edited.current.add('latitude');setLatitude(e.target.value);setResult(null);}}/></label>
          <label>Longitude<input type="number" min="-180" max="180" step="any" value={longitude} onChange={e => {edited.current.add('longitude');setLongitude(e.target.value);setResult(null);}}/></label>
          <label>Planned start (UTC)<input type="datetime-local" aria-label="Planned start (UTC)" aria-describedby={defaults.start ? 'environment-start-source' : undefined} value={start} onInput={e => {edited.current.add('start');setStart(e.target.value);setResult(null);}} onChange={e => {edited.current.add('start');setStart(e.target.value);setResult(null);}}/>{defaults.start && <small id="environment-start-source">{defaults.timingSource}</small>}</label>
          <label>Planned end (UTC)<input type="datetime-local" aria-label="Planned end (UTC)" aria-describedby={defaults.end ? 'environment-end-source' : undefined} value={end} onInput={e => {edited.current.add('end');setEnd(e.target.value);setResult(null);}} onChange={e => {edited.current.add('end');setEnd(e.target.value);setResult(null);}}/>{defaults.end && <small id="environment-end-source">{defaults.rangeAdjusted ? 'Query end: start + 72 hours' : defaults.timingSource}</small>}</label>
          <label>Depth (m, when applicable)<input type="number" min="0" step="any" value={depth} onChange={e => {edited.current.add('depth');setDepth(e.target.value);setResult(null);}}/></label>
        </div>}
        {dateAdjustment && <div className="environment-date-adjustment" role="alert"><div><strong>Query window adjusted to {ENVIRONMENTAL_MAX_FETCH_HOURS} hours</strong><p>{dateAdjustment.testWindow && 'Using the configured test query start. '}The original end was {dateAdjustment.originalEnd.replace('T',' ')} UTC. The query now ends at {dateAdjustment.end.replace('T',' ')} UTC, exactly {ENVIRONMENTAL_MAX_FETCH_HOURS} hours after {dateAdjustment.start.replace('T',' ')} UTC. The permit dates are unchanged. Confirm or edit the query period before continuing.</p></div><button type="button" onClick={()=>setDateAdjustment(null)} aria-label="Dismiss date adjustment">×</button></div>}
        <button className="button primary" onClick={confirmInputs} disabled={loading || !pointOnly}>{confirmed ? 'Location & Time Confirmed' : 'Confirm Location & Time'}</button>
      </section>
      {confirmed && <section ref={dataSourceRef} className="environment-connection-step" aria-label="Environmental data sources"><div className="environment-step-header"><div><div className="environment-step-label">2 · DATA SOURCES</div><h2>Environmental Data Sources</h2></div></div>
        <RequirementProviders rows={rows} providers={providers} configuration={session?.provider_status} capabilities={capabilities} mock={analysis.mode === 'MOCK'} renderVariableDetails={renderVariableDetails}/>
      </section>}
      {canFetch && <section className="card environment-fetch-step"><div className="environment-step-label">3 · RETRIEVE EVIDENCE</div><h2>Fetch Environmental Data</h2><p>Retrieve permit-required variables for the confirmed point and UTC period above.</p><button className="button primary" onClick={fetchEvidence} disabled={loading || !session}>{loading ? 'Fetching evidence…' : 'Fetch Environmental Data'}</button></section>}
      {error && <p role="alert" className="notice warning">{error}</p>}
      {result && <><div ref={resultsRef} className="environment-results-heading"><div className="environment-step-label">4 · RESULTS</div><h2>Retrieved Environmental Evidence</h2></div>
      {result.reused_downloaded_period && <p className="notice" role="status">Using previously downloaded data for this period. Original source timestamps are preserved; unavailable variables have not been downloaded again.</p>}
      <EnvironmentalResultsMap rows={rows} result={result} query={{latitude:latitude === '' ? null : Number(latitude),longitude:longitude === '' ? null : Number(longitude)}} screening={comparisonLabel} pointScreening={displayedPointLabel} blocker={blockerLabel}/>
      <details className="environment-full-audit"><summary>Full Evidence & Audit Details</summary>
      {diagnostics.filter(r=>r.canonical_variable==='dissolved_oxygen' && r.provider_diagnostic).map((r,i)=><section className="card evidence-card" key={`oxygen-diagnostic-${i}`} data-testid="provider-diagnostic-card"><h2>Dissolved oxygen · provider diagnostic</h2><p>{blockerLabel(r)}</p><dl><dt>Provider / product / dataset / variable</dt><dd>{r.provider_metadata?.provider || r.provider_diagnostic.provider} · {r.provider_metadata?.dataset_name || 'Product metadata unavailable'} · {r.provider_diagnostic.dataset_id} · {r.provider_diagnostic.variable}</dd><dt>Requested nominal depth / mode / tolerance</dt><dd>{num(r.provider_metadata?.requested_depth_m ?? r.request?.depth) ?? 'Unavailable'} m · {r.provider_metadata?.requested_depth_mode || r.request?.requested_depth_mode || 'Unavailable'} · {num(r.provider_metadata?.depth_tolerance_m) ?? 'Unavailable'} m</dd><dt>Native unit / returned UTC range (coverage not established)</dt><dd>{r.provider_metadata?.native_unit || 'Unavailable'} · {r.provider_metadata?.returned_time_start || 'Unavailable'} → {r.provider_metadata?.returned_time_end || 'Unavailable'}</dd><dt>Normalized unit (no screened value)</dt><dd>{r.provider_metadata?.normalized_unit || 'Not established'}</dd><dt>Requested / selected model coordinates</dt><dd>{r.provider_metadata?.requested_coordinates?.join(', ') || 'Unavailable'} · selected {r.provider_metadata?.selected_coordinates?.join(', ') || 'Not determined before depth rejection'}</dd><dt>Depth axis convention</dt><dd>{r.provider_metadata?.depth_axis_unit || 'Unavailable'} · positive {r.provider_metadata?.depth_axis_positive || 'Unavailable'}</dd><dt>Requested / provider query UTC period</dt><dd>{r.request?.start_time || 'Unavailable'} → {r.request?.end_time || 'Unavailable'} · query {r.request?.provider_query_start || 'Unavailable'} → {r.request?.provider_query_end || 'Unavailable'}</dd><dt>Returned provider depth levels</dt><dd>{r.provider_metadata?.returned_depth_levels_m?.map(v=>num(v)).join(', ') || 'Unavailable'}</dd><dt>Selected provider depth / difference</dt><dd>{num(r.provider_metadata?.selected_depth_m) ?? 'Unavailable'} / {num(r.provider_metadata?.depth_difference_m) ?? 'Unavailable'} m</dd></dl><p>No usable evidence or threshold result is claimed. Modelled supportive evidence is not an in-situ measurement.</p></section>)}
      {unavailable.map((r,i)=><section className="card evidence-card" key={`unavailable-${i}`} data-testid="unavailable-requirement"><h2>Condition {r.condition_id} · {label(r.canonical_variable)}</h2><p>NOT DETERMINED · evidence unavailable</p><p>Provider mapping: {label(r.routing?.preferred_provider)}</p><p>{r.provider_diagnostic?.provider_error_category}</p><p>{r.provider_diagnostic?.provider_error_message || r.notes_for_evaluation || 'Required evidence unavailable.'}</p>{r.provider_diagnostic && <p>Dataset: {r.provider_diagnostic.dataset_id || 'Unavailable'} · Variable: {r.provider_diagnostic.variable || 'Unavailable'}</p>}{r.canonical_variable==='turbidity' && <p>Turbidity evidence unavailable — an applicable mandatory requirement remains UNKNOWN until compatible evidence is available. Not a passing threshold result; source/review safeguards remain required.</p>}</section>)}
      <div className="environment-evidence">{evidenceCards.filter(r => r.evidence?.points?.length).map((r,i) => <section className="card evidence-card" key={i} data-testid="evidence-card">
        <h2>{label(r.canonical_variable)}</h2><p>{r.evidence.data_type === 'MODEL_FORECAST' ? 'Retrieved point / representative model value (not a compliance conclusion)' : r.evidence.data_type === 'REANALYSIS' ? 'Reanalysis value' : 'Satellite observation'}</p>
        <strong className="evidence-value">{num(r.evidence.points[0].raw_value) ?? 'Missing'} {r.evidence.points[0].unit}</strong>
        <dl><dt>Source threshold check</dt><dd>{r.threshold == null ? 'No structured threshold · inspect source for interpretation' : `${r.operator || ''} ${r.threshold} ${r.unit || ''}`}</dd>
          {r.manual_comparison_threshold && <><dt>Manual comparison threshold (not permit value)</dt><dd>{r.manual_comparison_threshold.value} FNU · USER SUPPLIED / manually verified</dd></>}
          <dt>Provider / dataset</dt><dd>{label(r.evidence.provider)} · {r.evidence.dataset_name} · {r.evidence.dataset_id}</dd>
          <dt>Data timestamp (UTC)</dt><dd>{r.evidence.points[0].data_time}</dd><dt>Retrieved</dt><dd>{r.evidence.retrieved_at}</dd>
          {r.evidence.recency_policy && <><dt>Reference-evidence recency policy</dt><dd>Historical/reference evidence, not contemporaneous continuous validity · actual source time {r.evidence.recency_policy.source_timestamp || 'Unavailable'} · assessed at {r.evidence.recency_policy.assessed_time || 'Unavailable'} · age {num(r.evidence.recency_policy.age_hours) ?? 'Unknown'} hours · maximum {num(r.evidence.recency_policy.max_age_hours)} hours · {r.evidence.recency_policy.reason_code || 'Within recency policy'}</dd><dt>Native / normalized unit</dt><dd>{r.evidence.points[0].unit} / {r.evidence.points[0].normalized_unit || 'Unavailable'}</dd><dt>Provider variable / evidence mode</dt><dd>{r.evidence.dataset_variable} · {r.evidence.data_type}</dd></>}
          <dt>Requested coordinates</dt><dd>{r.evidence.requested_coordinates?.join(', ') || 'Unavailable'}</dd>
          <dt>Selected model grid coordinates / depth</dt><dd>{r.evidence.latitude}, {r.evidence.longitude} · {(r.evidence.selected_depth_m ?? r.evidence.depth) == null ? 'Not applicable' : `${num(r.evidence.selected_depth_m ?? r.evidence.depth)} m`}{r.evidence.requested_depth_m != null && <> · requested {num(r.evidence.requested_depth_m)} m · difference {num(r.evidence.depth_difference_m) ?? 'unknown'} m</>}</dd>
          {r.canonical_variable === 'dissolved_oxygen' && <><dt>Model oxygen depth interpretation</dt><dd>{r.evidence.requested_depth_mode || 'Not supplied'} · tolerance {num(r.evidence.depth_tolerance_m) ?? 'Not supplied'} m · modelled supportive evidence, not an in-situ measurement.</dd></>}
          <dt>Spatial resolution / distance</dt><dd>{r.evidence.spatial_resolution || 'Unavailable'} · {num(r.evidence.distance_km) ?? 'Unknown'} km</dd>
          <dt>Spatial representativeness</dt><dd>{label(r.evidence.quality_status)} · Conservative maximum distance: {num(r.evidence.max_representative_distance_km) ?? 'Unavailable'} km</dd>
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
        {(r.checks || [r]).filter(check=>check.evidence?.canonical_variable === 'surface_current_direction').map((check,j)=><div key={`direction-${j}`} data-testid="current-direction-details"><h3>Current direction · DERIVED FROM COPERNICUS U/V</h3><p>{check.status} · {num(check.evidence.points?.[0]?.raw_value) ?? 'Unavailable'} degrees · {check.evidence.direction_convention}</p><p>Native timestamp: {check.evidence.points?.[0]?.data_time || 'Unavailable'}. Derivation: {check.evidence.points?.[0]?.derivation?.method || 'Unavailable'}. Retained signed components: U {num(check.evidence.points?.[0]?.component_values?.uo) ?? 'Unavailable'}, V {num(check.evidence.points?.[0]?.component_values?.vo) ?? 'Unavailable'}. Informational only; not an independent decision gate.</p></div>)}
        <p className="notice">{r.evidence.qualification || 'Not a compliance conclusion or operational authorization.'}</p>
        <p>{r.notes_for_evaluation}</p><p className="muted">{r.evidence.comparison_scope}</p>
        <details><summary>All retrieved points · {r.evidence.points.length}</summary><div className="table-scroll"><table className="retrieved-points"><thead><tr><th>UTC time</th><th>Source value</th></tr></thead><tbody>{r.evidence.points.map((p,j) => <tr key={j} data-testid="retrieved-point"><td>{p.data_time || 'Unavailable timestamp'}</td><td>{num(p.raw_value) ?? 'Missing'} {p.unit}
          <details><summary>Evaluation details</summary><p>Normalized: {num(p.normalized_value) ?? 'Unavailable'} {p.normalized_unit}</p><p>{p.status === 'INSUFFICIENT_DATA' ? 'INSUFFICIENT DATA' : p.comparison === true ? 'Threshold comparison true' : p.comparison === false ? 'Threshold comparison false' : label(p.status)}</p>{p.validation_notes?.map((note,k)=><p key={k}>{note}</p>)}</details></td></tr>)}</tbody></table></div></details>
      </section>)}</div></details></>}
    </>}
  </div>;
}
