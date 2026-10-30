import limits from '../../config/environmental_limits.json';
const months=['january','february','march','april','may','june','july','august','september','october','november','december'];
export function explicitUtc(value) {
  if (typeof value !== 'string') return '';
  let text=value.trim();
  const english=text.match(/^(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})[ ,]+(\d{1,2}):(\d{2})(?::(\d{2}))?\s+UTC$/i);
  if (english) {
    const month=months.indexOf(english[2].toLowerCase());
    if (month<0) return '';
    text=`${english[3]}-${String(month+1).padStart(2,'0')}-${english[1].padStart(2,'0')}T${english[4].padStart(2,'0')}:${english[5]}:${english[6] || '00'}Z`;
  }
  const iso=text.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?(Z|[+-]\d{2}:\d{2})$/i);
  if (!iso) return '';
  const [year,month,day,hour,minute,second]=iso.slice(1,7).map(Number);
  const calendar=new Date(Date.UTC(year,month-1,day));
  if (calendar.getUTCFullYear()!==year || calendar.getUTCMonth()!==month-1 || calendar.getUTCDate()!==day || hour>23 || minute>59 || (second || 0)>59) return '';
  const date=new Date(text);
  if (!Number.isFinite(date.valueOf())) return '';
  return date.toISOString().slice(0,date.getUTCMilliseconds() ? 23 : date.getUTCSeconds() ? 19 : 16);
}
export function boundedPeriod(start,end) {
  const startMs=Date.parse(start+'Z'),endMs=Date.parse(end+'Z');
  const adjusted=Number.isFinite(startMs) && Number.isFinite(endMs) && endMs-startMs>limits.max_fetch_hours*3600000;
  return {originalEnd:end,end:adjusted ? explicitUtc(new Date(startMs+limits.max_fetch_hours*3600000).toISOString()) : end,rangeAdjusted:adjusted};
}
export function environmentDefaults(analysis, reviewData) {
  const context = reviewData?.decision_context || analysis || {};
  const points = (context.spatial_context || []).filter(point => point.point_verified && point.source_verified && point.geometry_type === 'point' && Number.isFinite(point.latitude) && Number.isFinite(point.longitude) && Math.abs(point.latitude)<=90 && Math.abs(point.longitude)<=180);
  const unique = [...new Map(points.map(p=>[`${p.latitude},${p.longitude}`,p])).values()];
  const timing = context.temporal_context || analysis?.temporal_context || {};
  const operation = !!(timing.operation_start || timing.operation_end);
  const from = operation ? timing.operation_start : timing.permit_valid_from || analysis?.summary?.valid_from;
  const until = operation ? timing.operation_end : timing.permit_valid_until || analysis?.summary?.valid_until;
  const verified = timing.source_verified ?? analysis?.summary?.source_verified;
  let start=verified ? explicitUtc(from) : '', sourceEnd=verified ? explicitUtc(until) : '';
  const period=boundedPeriod(start,sourceEnd);
  const testStart=period.rangeAdjusted ? explicitUtc(limits.demo_query_start_utc) : '';
  if (testStart) {
    start=testStart;
    period.end=explicitUtc(new Date(Date.parse(testStart+'Z')+limits.max_fetch_hours*3600000).toISOString());
  }
  return {latitude:(context.spatial_context || []).length===1 && unique.length===1 ? String(unique[0].latitude) : '', longitude:(context.spatial_context || []).length===1 && unique.length===1 ? String(unique[0].longitude) : '', start,...period,testWindow:!!testStart,timingSource:testStart ? 'Configured test query window' : operation ? 'From permit operational dates' : 'From permit validity dates',timingNote:operation ? 'Pre-filled from the verified operational period. Confirm or edit below.' : 'Pre-filled from permit validity dates. Confirm these are your actual planned work times.'};
}
