import React, {useState, useRef} from 'react';

// No geocoding, timezone guessing or date-only midnight defaults.
function explicitUtc(value) {
  if (!value || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::00)?(?:Z|\+00:00)$/.test(value)) return null;
  const parsed = new Date(value);
  return Number.isFinite(parsed.valueOf()) && parsed.toISOString().slice(0,16) === value.slice(0,16) ? value.slice(0,16) : null;
}
function Source({value}) {
  return <details><summary>Original source</summary>{value.source_reference && <p>{value.source_reference}</p>}
    {value.source_spans?.map((s,i)=><blockquote key={i}>Page {s.page}: {s.quotation}</blockquote>)}
    <small>{value.source_verified ? 'Quotation verified · review before use' : 'Source verification required'}</small></details>;
}
export default function PermitContext({analysis, session, onLocation, onDates}) {
  const [selected, setSelected] = useState('');
  const [conversions, setConversions] = useState({});
  const pending = useRef(false);
  const [loading, setLoading] = useState(false);
  const locations = analysis.spatial_context?.length ? analysis.spatial_context : (analysis.geofences || []).map(g=>({
    location_name:g.name,coordinates_original:g.coordinates_or_boundary,coordinate_system:null,
    geometry_type:g.type,source_spans:g.source_spans,source_verified:g.source_verified,point_verified:false}));
  const location = locations.length === 1 ? locations[0] : selected === '' ? null : locations[Number(selected)];
  const locationIndex = locations.length === 1 ? 0 : Number(selected);
  const conversionKey = JSON.stringify([analysis.analysis_id,location?.coordinates_original,location?.coordinate_system]);
  const conversion = conversions[conversionKey];
  const converted = conversion?.result;
  const wgs = converted?.wgs84;
  const usable = converted?.usable && converted.status === 'converted' && converted.confidence === 'high' &&
    Number.isFinite(wgs?.latitude) && Number.isFinite(wgs?.longitude) &&
    Math.abs(wgs.latitude) <= 90 && Math.abs(wgs.longitude) <= 180;
  const queryPoint = loading ? null : location?.point_verified ? location : usable ? wgs : null;
  const canConvert = location?.source_verified && location.geometry_type === 'point' && location.coordinates_original &&
    !location.point_verified && analysis.spatial_context?.length && session;
  async function convertCoordinates() {
    if (pending.current || !canConvert) return;
    pending.current = true; setLoading(true);
    const key = conversionKey;
    setConversions(old=>({...old,[key]:{attempted:true}}));
    try {
      const response = await fetch('/api/coordinates/convert', {method:'POST',
        headers:{'Content-Type':'application/json','X-Session-Id':session.boot_id},
        body:JSON.stringify({analysis_id:analysis.analysis_id,location_index:locationIndex,force:!!conversion?.attempted})});
      if (!response.ok) throw new Error('Conversion failed');
      const result = await response.json();
      setConversions(old=>({...old,[key]:{attempted:true,result}}));
    } catch {
      setConversions(old=>({...old,[key]:{attempted:true,error:true}}));
    } finally {
      pending.current=false;setLoading(false);
    }
  }
  const extractedTiming = analysis.temporal_context;
  const hasTiming = extractedTiming && (extractedTiming.permit_valid_from || extractedTiming.permit_valid_until ||
    extractedTiming.operation_start || extractedTiming.operation_end || extractedTiming.operation_time_restrictions?.length);
  const timing = hasTiming ? extractedTiming : {
    permit_valid_from:analysis.summary?.valid_from,permit_valid_until:analysis.summary?.valid_until,
    source_spans:analysis.summary?.source_spans, source_verified:analysis.summary?.source_verified};
  const hasOperation = !!(timing.operation_start || timing.operation_end);
  const start = hasOperation ? timing.operation_start : timing.permit_valid_from;
  const end = hasOperation ? timing.operation_end : timing.permit_valid_until;
  const utcStart = explicitUtc(start), utcEnd = explicitUtc(end);
  const canUseDates = timing.source_verified && utcStart && utcEnd && utcEnd > utcStart;
  return <section className="permit-context" aria-label="Permit-defined location and time">
    <h2>PERMIT-DEFINED LOCATION &amp; TIME</h2>
    <p>Values extracted from the uploaded permit. Review before using as environmental-query inputs.</p>
    <div className="permit-context-grid">
      <article className="card"><h3>Work Location</h3>
        {locations.length > 1 && <><label>Choose a permit-defined location<select disabled={loading} value={selected} onChange={e=>setSelected(e.target.value)}>
          <option value="">Select a confirmed point or area</option>{locations.map((l,i)=><option key={i} value={i}>{l.location_name || `Source location ${i+1}`}</option>)}
        </select></label><p>Multiple locations: select and review a point; none is automatically chosen.</p></>}
        {location ? <><strong>{location.location_name || 'Unnamed source location'}</strong>
          {location.coordinates_original ? <p className="source-coordinate">{location.coordinates_original}</p> : <p>Coordinates not provided in uploaded permit.</p>}
          <p>Coordinate system: {location.coordinate_system || 'Not stated'}</p>
          {location.point_verified && <p>WGS84 latitude {location.latitude} · longitude {location.longitude}</p>}
          {location.coordinates_original && !queryPoint && <p className="context-warning">{location.geometry_type && location.geometry_type !== 'point'
            ? 'Area or route: select a confirmed point manually. No midpoint is inferred.'
            : 'Coordinate conversion to WGS84 required before environmental retrieval.'}</p>}
          {canConvert && <><p>Optional online coordinate conversion · one OpenAI request per click; API charges apply. No automatic retry.</p>
            <button className="button secondary" disabled={loading} onClick={convertCoordinates}>{loading ? 'Converting coordinates…' : conversion?.attempted ? 'Convert Again' : 'Convert Coordinates'}</button></>}
          {!location.point_verified && !converted && !loading && !conversion?.error && <p>WGS84: Not converted yet.</p>}
          {converted && <><h4>Converted WGS84</h4><p>Latitude: {wgs?.latitude ?? 'Not available'} · Longitude: {wgs?.longitude ?? 'Not available'}</p>
            <p>Source CRS: {converted.source_coordinate_system} / {converted.source_coordinate_system_identifier || 'Unresolved'}</p>
            <p>Conversion: Online model conversion · Model: {converted.model || 'Configured model'} · Confidence: {converted.confidence}</p>
            <p>Derived values, not coordinates quoted from the permit. {converted.notes}</p></>}
          {(conversion?.error || converted && !usable) && <p role="alert">Coordinate conversion could not be verified. Review the source coordinate system or enter a confirmed WGS84 location manually.</p>}
          <button className="button secondary" disabled={!queryPoint} onClick={()=>onLocation(queryPoint.latitude,queryPoint.longitude)}>Use location ↓</button>
          <Source value={location}/></> : <p>{locations.length ? 'Select a source location to inspect it.' : 'Coordinates not provided in uploaded permit.'}</p>}
      </article>
      <article className="card"><h3>Permit Timing</h3>
        <h4>{hasOperation ? 'Planned / permitted operational period' : 'Permit validity'}</h4>
        <p>Start: {start || 'Not stated'}</p><p>End: {end || 'Not stated'}</p>
        {hasOperation && (timing.permit_valid_from || timing.permit_valid_until) && <p>Permit validity: {timing.permit_valid_from || 'Not stated'} → {timing.permit_valid_until || 'Not stated'}</p>}
        {!hasOperation && (start || end) && <p className="context-warning">These are licence validity dates, not confirmed operational dates. Adjust them if the planned activity period is known.</p>}
        {(start || end) && <><button className="button secondary" disabled={!canUseDates} onClick={()=>onDates(utcStart,utcEnd)}>Use dates ↓</button>
          {!utcStart || !utcEnd ? <p>Explicit UTC times are not provided. Enter planned UTC dates and times below; no midnight or timezone is inferred.</p> : <p>Review the selected period below; retrieval remains limited to 48 hours.</p>}</>}
        {!!timing.operation_time_restrictions?.length && <div><h4>Source time restrictions</h4>{timing.operation_time_restrictions.map((r,i)=><p key={i}>{r}</p>)}</div>}
        <Source value={timing}/>
      </article>
    </div>
  </section>;
}
