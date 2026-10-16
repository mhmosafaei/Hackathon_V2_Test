const STOP_FALLBACK = 'One or more reviewed operational constraints are triggered.';
const TITLES = {
  significant_wave_height: 'Significant wave height', mean_wave_period: 'Mean wave period',
  wind_speed_10m: 'Wind speed 10m', wind_gust: 'Wind gust',
  surface_current_speed: 'Surface current speed',
  eastward_current: 'Eastward current component U', eastward_current_component_u: 'Eastward current component U',
  northward_current: 'Northward current component V', northward_current_component_v: 'Northward current component V',
  visibility: 'Visibility', turbidity: 'Turbidity', dissolved_oxygen: 'Dissolved oxygen',
};

function triggerTitle(result) {
  const rule = result.effective_rule || {};
  const known = TITLES[rule.canonical_variable];
  if (known) return known;
  const raw = rule.title || rule.variable || rule.requirement || result.title;
  if (typeof raw !== 'string' || !raw.trim() || raw === result.requirement_id || /environmental_requirement[-_]|^env[-_]|\b[a-f0-9]{32,64}\b/i.test(raw)) return null;
  const canonical = raw.trim().toLowerCase().replaceAll(' ', '_');
  if (TITLES[canonical]) return TITLES[canonical];
  const text = raw.trim().replaceAll('_', ' ').replace(/\s+/g, ' ')
    .replace(/\bcomponent ([uv])\b/gi, (_, component) => `component ${component.toUpperCase()}`);
  return text[0].toUpperCase() + text.slice(1);
}

export function intervalRuleResults(assessment, payload) {
  if (assessment?.rule_results?.length) return assessment.rule_results;
  const start = Date.parse(assessment?.start), end = Date.parse(assessment?.end);
  if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) return [];
  const inside = interval => {
    const a = Date.parse(interval?.start), b = Date.parse(interval?.end);
    return Number.isFinite(a) && Number.isFinite(b) && start <= a && b <= end && a < b;
  };
  const intervals = (payload?.timeline || []).filter(inside);
  const timelineRules = intervals.flatMap(interval => interval.rule_results || []);
  // Aggregate current-rule STOP status is not an interval trigger. Use only
  // evaluated children whose actual bounds fall within this interval/window.
  const children = (payload?.current_assessment?.rule_results || []).flatMap(parent =>
    (parent.interval_results || []).filter(child => inside(child) && !intervals.some(interval =>
      interval.rule_results?.length && Date.parse(interval.start) === Date.parse(child.start)
      && Date.parse(interval.end) === Date.parse(child.end))).map(child => ({...child,
      effective_rule: child.effective_rule || parent.effective_rule,
    })));
  return [...timelineRules, ...children];
}

export function decisionExplanation(assessment, fallback = '', payload) {
  if (assessment?.status === 'UNKNOWN') {
    const issues = new Set();
    const categories = {
      EVIDENCE_MISSING:'data is unavailable', NO_WAVE_EVIDENCE:'data is unavailable',
      EVIDENCE_STALE:'data is stale', STALE_OXYGEN_EVIDENCE:'data is stale', STALE_WAVE_EVIDENCE:'data is stale',
      TEMPORAL_COVERAGE_INSUFFICIENT:'does not cover this interval', FORECAST_COVERAGE_INSUFFICIENT:'does not cover this interval',
      SPATIAL_COVERAGE_INSUFFICIENT:'spatial coverage is insufficient', UNIT_INCOMPATIBLE:'unit is incompatible',
      DEPTH_UNSATISFIED:'depth is incompatible or unresolved', NO_COMPATIBLE_OXYGEN_SOURCE:'compatible source is unavailable',
      PROVIDER_FAILURE:'provider/source is unavailable', EVIDENCE_UNSUPPORTED:'compatible source is unavailable',
      TIME_UNRESOLVED:'permit time prerequisite is unresolved', POSITION_UNRESOLVED:'permit position prerequisite is unresolved',
    };
    for (const result of intervalRuleResults(assessment, payload)) {
      if (result?.gating !== true || result.status !== 'UNKNOWN') continue;
      const title = result.condition_id === 'time' && result.kind === 'decision_prerequisite' ? 'Permit time'
        : result.condition_id === 'position' && result.kind === 'decision_prerequisite' ? 'Permit position' : triggerTitle(result);
      if (!title) continue;
      const code = result.reason_code || '';
      const category = categories[code] || (code.includes('TIME') ? 'permit time prerequisite is unresolved'
        : code.includes('POSITION') ? 'permit position prerequisite is unresolved' : 'requires review or compatible evidence');
      issues.add(`${title} ${category}`);
    }
    const ordered = [...issues].sort((a,b)=>a.localeCompare(b,'en'));
    return ordered.length ? `Insufficient evidence: ${ordered.join('; ')}.` : 'Insufficient evidence for one or more required operational constraints.';
  }
  if (assessment?.status !== 'STOP') return assessment?.explanation || fallback;
  const names = new Map();
  for (const result of intervalRuleResults(assessment, payload)) {
    if (!result || result.gating !== true || result.status !== 'STOP') continue;
    const title = triggerTitle(result);
    if (title) names.set(title.toLowerCase(), title);
  }
  const ordered = [...names.values()].sort((a, b) => a.localeCompare(b, 'en'));
  if (!ordered.length) return STOP_FALLBACK;
  return `${ordered.length === 1 ? 'Triggered constraint' : 'Triggered constraints'}: ${ordered.join(', ')}`;
}
