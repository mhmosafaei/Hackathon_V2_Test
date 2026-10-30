import React, {useState} from 'react';
import {MapPin, LocateFixed, Waves, Wind, Thermometer, Droplets, Database} from 'lucide-react';
import EnvironmentalMapCanvas, {validPosition,validGeometry} from './EnvironmentalMapCanvas.jsx';
import {num} from './formatNumber.js';
import './EnvironmentalResultsMap.css';

const pretty=value=>String(value || 'Unknown variable').replaceAll('_',' ');
const iconFor=variable=>/wind|gust/.test(variable) ? Wind : /temperature/.test(variable) ? Thermometer : /turbidity|oxygen|precipitation/.test(variable) ? Droplets : /wave|current/.test(variable) ? Waves : Database;
export function usablePoint(point,evidence) {
  return !!point && typeof point.raw_value==='number' && Number.isFinite(point.raw_value) && !point.validation_notes?.length && point.status!=='INSUFFICIENT_DATA' && evidence?.retrieval_status!=='FAILED';
}
export function queryPosition(rows,query) {
  for (const row of rows) {
    const candidate=row.evidence?.requested_coordinates || row.request?.coordinates;
    if(validPosition(candidate)) return candidate;
  }
  const position=[query?.latitude,query?.longitude];
  return validPosition(position) ? position : null;
}
export default function EnvironmentalResultsMap({rows=[],result={},query={},screening,pointScreening,blocker}) {
  const variables=[...new Set(rows.map(row=>row.canonical_variable).filter(Boolean))];
  const [selected,setSelected]=useState(variables[0] || '');
  const [timeIndex,setTimeIndex]=useState(null);
  const [focusToken,setFocusToken]=useState(0);
  const active=variables.includes(selected) ? selected : variables[0];
  const matching=rows.filter(row=>row.canonical_variable===active);
  const row=matching.find(row=>row.evidence?.points?.length) || matching[0];
  const evidence=row?.evidence;
  const points=evidence?.points || [];
  const firstUsable=points.findIndex(point=>usablePoint(point,evidence));
  const index=timeIndex != null && timeIndex<points.length ? timeIndex : Math.max(firstUsable,0);
  const point=points[index];
  const usable=usablePoint(point,evidence);
  const value=usable ? `${num(point.raw_value)} ${point.unit || ''}`.trim() : 'Unavailable';
  const position=queryPosition(rows,query);
  const sample=validPosition([evidence?.latitude,evidence?.longitude]) ? [evidence.latitude,evidence.longitude] : null;
  const geometry=validGeometry(result.geometry || result.query_geometry || query.geometry);
  const Icon=iconFor(active || '');
  return <section className="environment-results-map" aria-label="Map and environmental variables">
    <div className="environment-map-stage"><EnvironmentalMapCanvas position={position} sample={sample} geometry={geometry} valueLabel={`${pretty(active)}: ${value}${point?.data_time ? ` · ${point.data_time}` : ''}`} focusToken={focusToken}/>
      <div className="environment-map-location"><MapPin size={17}/><div><strong>{geometry ? 'Work area' : 'Work location'}</strong><span>{position ? `${position[0]}, ${position[1]}` : geometry ? 'Verified GeoJSON boundary' : 'No confirmed coordinates attached to this result'}</span></div></div>
      <button className="environment-map-recenter" type="button" onClick={()=>setFocusToken(value=>value+1)} aria-label="Recenter map"><LocateFixed size={18}/></button>
      <div className="environment-map-value" aria-live="polite"><span>{pretty(active)}</span><output>{value}</output><small>{point?.data_time ? `${point.data_time} · UTC` : 'No valid data timestamp'}</small></div>
      <div className="environment-map-legend"><span><i/>Work location</span><span><i/>Provider sample / grid point</span>{geometry && <span>Outline: work area, not area-wide evidence</span>}</div>
    </div>
    <aside className="environment-map-sidebar"><div className="environment-map-sidebar-heading"><h3>Environmental Variables</h3><p>Select a variable to display its value on the map.</p></div>
      <div className="environment-variable-buttons" role="group" aria-label="Select environmental variable">{variables.map(variable=>{const VariableIcon=iconFor(variable);const available=rows.some(row=>row.canonical_variable===variable && row.evidence?.points?.some(point=>usablePoint(point,row.evidence)));return <button type="button" key={variable} aria-pressed={active===variable} onClick={()=>{setSelected(variable);setTimeIndex(null);}}><VariableIcon size={17}/><span>{pretty(variable)}</span><i className={available ? 'has-data' : 'no-data'} aria-label={available ? 'Value available' : 'Evidence unavailable'}/></button>;})}</div>
      {row ? <div className="environment-selected-variable"><h3><Icon size={18}/>{pretty(active)}</h3>
        {points.length>1 && <label>Evidence time (UTC)<select value={index} onChange={event=>setTimeIndex(Number(event.target.value))}>{points.map((point,index)=><option key={index} value={index}>{point.data_time || `Undated point ${index+1}`}</option>)}</select></label>}
        <p className="environment-map-assessment">{row.status==='INSUFFICIENT_DATA' || !usable ? 'NOT DETERMINED' : row.threshold == null ? pointScreening?.(row) || 'INFORMATIONAL' : screening?.(row) || 'Retrieved value'}</p>
        {!usable && <p className="environment-map-missing">{row.provider_diagnostic?.provider_error_message || row.notes_for_evaluation || 'No usable evidence was returned for this variable.'}</p>}
        {row.status==='INSUFFICIENT_DATA' && usable && <p className="environment-map-missing">{blocker?.(row) || 'Evidence does not establish coverage for the requested period.'}</p>}
        <dl><dt>Source</dt><dd>{evidence?.provider || row.routing?.preferred_provider || 'Unavailable'}{evidence?.dataset_name && <small>{evidence.dataset_name}</small>}</dd><dt>Evidence type</dt><dd>{pretty(evidence?.data_type || 'unavailable')}</dd><dt>Data timestamp (UTC)</dt><dd>{point?.data_time || 'Unavailable'}</dd><dt>Retrieved (UTC)</dt><dd>{evidence?.retrieved_at || 'Unavailable'}</dd><dt>Sample location</dt><dd>{sample ? sample.join(', ') : 'Unavailable'}</dd><dt>Depth</dt><dd>{(evidence?.selected_depth_m ?? evidence?.depth) == null ? 'Not applicable' : `${num(evidence.selected_depth_m ?? evidence.depth)} m`}</dd><dt>Coverage</dt><dd>{evidence?.temporal_coverage_status || 'Not established'}</dd></dl>
        <details className="environment-map-conditions"><summary>Conditions & thresholds · {matching.length}</summary>{matching.map((check,index)=><div key={index}><strong>Condition {check.condition_id}</strong><p>{check.threshold == null ? 'Informational / no numerical threshold' : `${check.operator || ''} ${check.manual_comparison_threshold?.value ?? check.threshold} ${check.manual_comparison_threshold?.unit || check.unit || ''}`}</p><p>{check.requirement_text}</p>{check.source_spans?.map((span,i)=><blockquote key={i}>Page {span.page}: {span.quotation}</blockquote>)}</div>)}</details>
        <p className="environment-map-qualification">{evidence?.qualification || 'Point / model evidence only. Not an operational authorization.'}</p>
      </div> : <p className="environment-map-empty">No environmental variables returned.</p>}
    </aside>
  </section>;
}
