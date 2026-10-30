import React, {useState, useRef, useEffect} from 'react';
import {MapPin, LocateFixed, Waves, Wind, Thermometer, Droplets, Database, Maximize2, Minimize2} from 'lucide-react';
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
  const [expanded,setExpanded]=useState(false);
  const containerRef=useRef(null);
  useEffect(()=>{
    if (!expanded) return;
    const previous=document.activeElement;
    const oldOverflow=document.body.style.overflow;
    document.body.style.overflow='hidden';
    containerRef.current?.querySelector('[data-map-expand]')?.focus();
    const onKey=event=>{
      if (event.key==='Escape') {event.preventDefault();setExpanded(false);}
      if (event.key==='Tab') {
        const controls=[...containerRef.current.querySelectorAll('button,select,summary,a[href]')].filter(node=>!node.disabled && node.getClientRects().length);
        if (!controls.length) {event.preventDefault();return;}
        const first=controls[0],last=controls.at(-1);
        if (event.shiftKey && document.activeElement===first) {event.preventDefault();last.focus();}
        else if (!event.shiftKey && document.activeElement===last) {event.preventDefault();first.focus();}
      }
    };
    document.addEventListener('keydown',onKey);
    return ()=>{document.body.style.overflow=oldOverflow;document.removeEventListener('keydown',onKey);if(previous?.isConnected) previous.focus();};
  },[expanded]);
  const active=variables.includes(selected) ? selected : variables[0];
  const matching=rows.filter(row=>row.canonical_variable===active);
  const row=matching.find(row=>row.evidence?.points?.length) || matching[0];
  const evidence=row?.evidence;
  const reference=row?.historical_reference;
  const referenceOnly=reference?.reference_only===true && reference.qualifies_for_decision===false && reference.unit==='FNU' && typeof reference.raw_value==='number' && Number.isFinite(reference.raw_value) && reference.raw_value>=0 && Number.isFinite(Date.parse(reference.data_time));
  const displayEvidence=referenceOnly ? {...reference,temporal_coverage_status:'HISTORICAL_REFERENCE_ONLY'} : evidence;
  const points=referenceOnly ? [{raw_value:reference.raw_value,unit:reference.unit,data_time:reference.data_time}] : evidence?.points || [];
  const firstUsable=points.findIndex(point=>usablePoint(point,evidence));
  const index=timeIndex != null && timeIndex<points.length ? timeIndex : Math.max(firstUsable,0);
  const point=points[index];
  const usable=referenceOnly || usablePoint(point,evidence);
  const value=usable ? `${num(point.raw_value)} ${point.unit || ''}`.trim() : 'Unavailable';
  const position=queryPosition(rows,query);
  const sample=validPosition([displayEvidence?.latitude,displayEvidence?.longitude]) ? [displayEvidence.latitude,displayEvidence.longitude] : null;
  const geometry=validGeometry(result.geometry || result.query_geometry || query.geometry);
  const Icon=iconFor(active || '');
  return <section ref={containerRef} className={`environment-results-map ${expanded ? 'is-expanded' : ''}`} role={expanded ? 'dialog' : 'region'} aria-modal={expanded ? true : undefined} aria-label="Map and environmental variables">
    <div className="environment-map-stage"><EnvironmentalMapCanvas position={position} sample={sample} geometry={geometry} valueLabel={`${referenceOnly ? 'Historical reference · ' : ''}${pretty(active)}: ${value}${point?.data_time ? ` · ${point.data_time}` : ''}`} focusToken={focusToken}/>
      <div className="environment-map-location"><MapPin size={17}/><div><strong>{geometry ? 'Work area' : 'Work location'}</strong><span>{position ? `${position[0]}, ${position[1]}` : geometry ? 'Verified GeoJSON boundary' : 'No confirmed coordinates attached to this result'}</span></div></div>
      <button className="environment-map-recenter" type="button" onClick={()=>setFocusToken(value=>value+1)} aria-label="Recenter map"><LocateFixed size={18}/></button>
      <button className="environment-map-expand" data-map-expand type="button" aria-expanded={expanded} onClick={()=>setExpanded(value=>!value)}>{expanded ? <Minimize2 size={15}/> : <Maximize2 size={15}/>} {expanded ? 'Collapse map' : 'Expand map'}</button>
      <div className="environment-map-value" aria-live="polite"><span>{pretty(active)}</span><div className="environment-map-reading"><output>{value}</output>{points.length>1 && <label className="environment-map-time">Evidence time (UTC)<select value={index} onChange={event=>setTimeIndex(Number(event.target.value))}>{points.map((point,index)=><option key={index} value={index}>{point.data_time || `Undated point ${index+1}`}</option>)}</select></label>}</div><small>{point?.data_time ? `${point.data_time} · UTC` : 'No valid data timestamp'}</small>{referenceOnly && <small className="environment-reference-label">Historical observation · not a forecast</small>}</div>
      <div className="environment-map-legend"><span><i/>Work location</span><span><i/>Provider sample / grid point</span>{geometry && <span>Outline: work area, not area-wide evidence</span>}</div>
    </div>
    <aside className="environment-map-sidebar"><div className="environment-map-sidebar-heading"><h3>Environmental Variables</h3><p>Select a variable to display its value on the map.</p></div>
      <div className="environment-variable-buttons" role="group" aria-label="Select environmental variable">{variables.map(variable=>{const VariableIcon=iconFor(variable);const available=rows.some(row=>row.canonical_variable===variable && row.evidence?.points?.some(point=>usablePoint(point,row.evidence)));const historical=rows.some(row=>row.canonical_variable===variable && row.historical_reference?.reference_only);return <button type="button" key={variable} aria-pressed={active===variable} onClick={()=>{setSelected(variable);setTimeIndex(null);}}><VariableIcon size={17}/><span>{pretty(variable)}</span><i className={available ? 'has-data' : historical ? 'reference-data' : 'no-data'} aria-label={available ? 'Value available' : historical ? 'Historical reference only' : 'Evidence unavailable'}/></button>;})}</div>
      {row ? <div className="environment-selected-variable"><h3><Icon size={18}/>{pretty(active)}</h3>
        <p className="environment-map-assessment">{referenceOnly || row.status==='INSUFFICIENT_DATA' || !usable ? 'NOT DETERMINED' : row.threshold == null ? pointScreening?.(row) || 'INFORMATIONAL' : screening?.(row) || 'Retrieved value'}</p>
        {!usable && <p className="environment-map-missing">{row.provider_diagnostic?.provider_error_message || row.notes_for_evaluation || 'No usable evidence was returned for this variable.'}</p>}
        {row.status==='INSUFFICIENT_DATA' && usable && <p className="environment-map-missing">{referenceOnly ? reference.note : blocker?.(row) || 'Evidence does not establish coverage for the requested period.'}</p>}
        {referenceOnly && <p className="environment-reference-age">Observation time: {reference.data_time} · {num(reference.age_hours / 24,1)} days before the planned start. Decision & Work Windows uses this historical value as a constant planning assumption; future turbidity forecasting will be improved.</p>}
        <details className="environment-map-source-details"><summary>Source & Coverage</summary><dl><dt>Source</dt><dd>{displayEvidence?.provider || row.routing?.preferred_provider || 'Unavailable'}{displayEvidence?.dataset_name && <small>{evidence.dataset_name}</small>}</dd><dt>Evidence type</dt><dd>{pretty(displayEvidence?.data_type || 'unavailable')}</dd><dt>Data timestamp (UTC)</dt><dd>{point?.data_time || 'Unavailable'}</dd><dt>Retrieved (UTC)</dt><dd>{displayEvidence?.retrieved_at || 'Unavailable'}</dd><dt>Sample location</dt><dd>{sample ? sample.join(', ') : 'Unavailable'}</dd><dt>Depth</dt><dd>{(displayEvidence?.selected_depth_m ?? displayEvidence?.depth) == null ? 'Not applicable' : `${num(displayEvidence.selected_depth_m ?? displayEvidence.depth)} m`}</dd><dt>Coverage</dt><dd>{displayEvidence?.temporal_coverage_status || 'Not established'}</dd></dl><p className="environment-map-qualification">{displayEvidence?.qualification || 'Point / model evidence only. Not an operational authorization.'}</p></details>
        <details className="environment-map-conditions"><summary>Threshold details · {matching.length}</summary>{matching.map((check,index)=><div key={index}><strong>Condition {check.condition_id ?? 'not stated'}</strong><p>{check.threshold == null ? 'Informational / no numerical threshold' : `${check.operator || ''} ${check.manual_comparison_threshold?.value ?? check.threshold} ${check.manual_comparison_threshold?.unit || check.unit || ''}`}</p></div>)}</details>
      </div> : <p className="environment-map-empty">No environmental variables returned.</p>}
    </aside>
  </section>;
}
