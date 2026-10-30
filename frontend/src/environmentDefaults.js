import limits from '../../config/environmental_limits.json';
export function explicitUtc(value) {
  if (!value || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::00)?(?:Z|\+00:00)$/.test(value)) return '';
  const date = new Date(value);
  return Number.isFinite(date.valueOf()) && date.toISOString().slice(0,16) === value.slice(0,16) ? value.slice(0,16) : '';
}
export function environmentDefaults(analysis, reviewData) {
  const context = reviewData?.decision_context || analysis || {};
  const points = (context.spatial_context || []).filter(point => point.point_verified && point.source_verified && point.geometry_type === 'point' && Number.isFinite(point.latitude) && Number.isFinite(point.longitude) && Math.abs(point.latitude)<=90 && Math.abs(point.longitude)<=180);
  const unique = [...new Map(points.map(p=>[`${p.latitude},${p.longitude}`,p])).values()];
  const timing = context.temporal_context || analysis?.temporal_context || {permit_valid_from:analysis?.summary?.valid_from,permit_valid_until:analysis?.summary?.valid_until,source_verified:analysis?.summary?.source_verified};
  const operation = !!(timing.operation_start || timing.operation_end);
  const from = operation ? timing.operation_start : timing.permit_valid_from;
  const until = operation ? timing.operation_end : timing.permit_valid_until;
  const start=timing.source_verified ? explicitUtc(from) : '', end=timing.source_verified ? explicitUtc(until) : '';
  const hours=(Date.parse(end+'Z')-Date.parse(start+'Z'))/3600000;
  const usable = start && end && hours>0 && hours<=limits.max_fetch_hours;
  return {latitude:(context.spatial_context || []).length===1 && unique.length===1 ? String(unique[0].latitude) : '', longitude:(context.spatial_context || []).length===1 && unique.length===1 ? String(unique[0].longitude) : '', start:usable ? start : '',end:usable ? end : '',timingNote:usable ? operation ? 'Pre-filled from the verified operational period. Confirm or edit below.' : 'Pre-filled from permit validity dates. Confirm these are your actual planned work times.' : 'Enter your planned UTC period (up to 72 hours). Permit validity dates are available in the source details; no work times have been inferred.'};
}
