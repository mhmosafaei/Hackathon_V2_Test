import React, {useEffect, useRef, useState} from 'react';
import Environmental from './Environmental.jsx';
import HumanReview, {reviewSummary} from './HumanReview.jsx';
import HumanReviewOverview from './HumanReviewOverview.jsx';
import DecisionWorkWindows from './DecisionWorkWindows.jsx';
import './WorkflowStepper.css';
import brandLogo from './assets/permitpulse-logo.png';
import brandWordmark from './assets/permitpulse-wordmark.png';
import {ArrowUpRight, FileText, Upload, Plus, LoaderCircle, AlertCircle, ChevronDown, Waves, Leaf, Users, CalendarDays, Eye, BarChart3, Info, AlertTriangle, Wind, Droplets, Thermometer, Gauge, ArrowRight, ArrowUp, MoveHorizontal, Clock3, PieChart as PieChartIcon, ListChecks} from 'lucide-react';
import {BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell} from 'recharts';

export const phases = ['PRIOR', 'DURING', 'AFTER', 'GENERAL'];
export const categories = ['Notification / Deadline', 'Positioning / Geographic', 'Monitoring / Survey', 'Reporting / Recordkeeping', 'Operational / Safety', 'Approval / Administrative', 'Other'];
const colors = ['#1769a5', '#0b2853', '#68a8d5', '#b7d4e9'];
const pretty = s => s[0] + s.slice(1).toLowerCase();
export function chartData(conditions) {
  return {
    phase: phases.map(name => ({name: pretty(name), value: conditions.filter(c => c.phase === name).length})),
    category: categories.map(name => ({name, value: conditions.filter(c => c.category === name).length})),
    limits: [{name: 'Has explicit limit/deadline', value: conditions.filter(c => c.important_limit?.trim() || c.timing?.trim()).length},
      {name: 'No explicit limit/deadline', value: conditions.filter(c => !c.important_limit?.trim() && !c.timing?.trim()).length}]
  };
}
const fallback = v => v || 'Not stated';
export function geofenceSummary(geofence) {
  // Never place coordinate lists in the compact card, even if a model puts them in name.
  const name = geofence.name?.trim() || '';
  const coordinateLike = /[°º]|\d+\.\d+.*\d+\.\d+/.test(name);
  const label = name && name.length <= 100 && !coordinateLike ? name : geofence.type.replaceAll('_', ' ');
  const radius = geofence.type === 'radius' && geofence.coordinates_or_boundary?.match(/\b\d+(?:\.\d+)?\s*(?:NM|nautical miles?|km|kilometres?|kilometers?|metres?|meters?|m)\b/i)?.[0];
  return radius ? `${label} · ${radius} radius` : label;
}
function GeofenceCard({geofences}) {
  if (!geofences?.length) return null;
  return <section className="card metric geofence-card" aria-label="Geographic restrictions" data-testid="geofence-card"><details>
    <summary data-testid="geofence-summary"><span className="eyebrow">GEOFENCE</span><strong>{geofences.length === 1 ? geofenceSummary(geofences[0]) : `${geofences.length} geographic restrictions`}</strong>
      {geofences.length > 1 && <span className="geofence-lead">{geofenceSummary(geofences[0])}</span>}<span className="geofence-action">View restrictions <ChevronDown size={13}/></span></summary>
    <div className="geofence-details">{geofences.map((g, i) => <article key={i}><h3>{g.name}</h3><p>{g.description}</p><dl>
      <dt>Type</dt><dd>{g.type.replaceAll('_', ' ')}</dd><dt>Restriction</dt><dd>{g.restriction}</dd>
      <dt>Coordinates / boundary</dt><dd className="geofence-boundary">{fallback(g.coordinates_or_boundary)}</dd><dt>Physical source pages</dt><dd>{g.source_pages.join(', ') || 'Unresolved'}</dd>
    </dl><small>{g.source_verified ? 'Source quotation verified · Human review required' : 'Source verification required · Unreviewed'}</small>
      {g.source_spans?.map((s, j) => <blockquote key={j}><b>Physical page {s.page}</b><p>{s.quotation}</p></blockquote>)}
    </article>)}</div>
  </details></section>;
}
function Chart({title, label, data, type, index}) {
  return <section className="card chart-card" aria-label={label} data-testid="chart"><div className="section-heading"><h3>{title}</h3><span className="eyebrow">CONDITIONS</span></div>
    <div className="chart-area"><ResponsiveContainer width="100%" height="100%">
      {type === 'bar' ? <BarChart data={data} layout={index === 1 ? 'vertical' : 'horizontal'} margin={{top: 10, right: 25, left: index === 1 ? 5 : 0, bottom: 5}}>
        <CartesianGrid strokeDasharray="3 3" horizontal={index !== 1} vertical={index === 1} stroke="#e6edef"/>
        <XAxis type={index === 1 ? 'number' : 'category'} dataKey={index === 1 ? undefined : 'name'} allowDecimals={false} axisLine={false} tickLine={false} fontSize={12}/>
        <YAxis type={index === 1 ? 'category' : 'number'} dataKey={index === 1 ? 'name' : undefined} width={index === 1 ? 164 : 30} allowDecimals={false} axisLine={false} tickLine={false} fontSize={11}/>
        <Tooltip cursor={{fill: '#f1f6f6'}}/><Bar dataKey="value" name="Conditions" fill="#1769a5" radius={[4, 4, 4, 4]} maxBarSize={38} isAnimationActive={false}/>
      </BarChart> : <PieChart><Pie data={data} dataKey="value" nameKey="name" innerRadius={62} outerRadius={93} paddingAngle={2} isAnimationActive={false}>
        {data.map((d, i) => <Cell key={d.name} fill={colors[i % colors.length]}/>)}</Pie><Tooltip/></PieChart>}
    </ResponsiveContainer></div>
    {type === 'pie' && <div className="legend">{data.map((d, i) => <span key={d.name}><i style={{background: colors[i % colors.length]}}/>{d.name}<b>{d.value}</b></span>)}</div>}
  </section>;
}
const workflowSteps = [
  ['permit', FileText, 'Permit Intelligence'],
  ['review', Users, 'Human Review'],
  ['environment', Leaf, 'Environmental Intelligence'],
  ['decision', CalendarDays, 'Decision & Work Windows']
];
const workflowCopy = {
  permit: ['Understand the permit', 'Upload a permit and inspect the extracted conditions, limits and source text.', 'Analyze the PDF, then continue to Human Review.'],
  review: ['Human Review: Check the interpretation', '', 'Please resolve every AI-extracted item to unlock Environmental Intelligence and downstream decision assessment.'],
  environment: ['Gather environmental evidence', 'See which permit conditions need environmental data, then request evidence for a confirmed point and UTC period.', 'Fetch data, or explicitly continue with an evidence gap if retrieval is unavailable.'],
  decision: ['Assess work windows', 'Compare reviewed conditions with the evidence currently available.', 'Choose the work-window criteria and evaluate. Return to earlier steps whenever needed.']
};
function AppNav({tab, setTab, access, completed}) {
  const reasons = {review:'Analyze a permit first', environment:'Complete Human Review first', decision:'Complete the environmental evidence step first'};
  return <nav className="top-nav" aria-label="Primary navigation">{workflowSteps.map(([id, Icon, label], index) =>
    <button key={id} type="button" aria-pressed={tab === id} disabled={!access[id]}
      title={!access[id] ? reasons[id] : label} onClick={() => setTab(id)}>
      <b className={`workflow-step-number ${completed[id] ? 'is-complete' : ''}`} aria-hidden="true">{index + 1}</b>
      <Icon size={17}/><span>{label}</span><small className="workflow-nav-state" aria-hidden="true">{completed[id] ? 'Done' : !access[id] ? 'Locked' : tab === id ? 'Current' : 'Ready'}</small>
    </button>)}</nav>;
}
function reviewBlockerHint(rows, remaining) {
  if (!Array.isArray(rows) || !rows.length) return `${remaining} review item(s) remain.`;
  const interpretations = rows.filter(row => !['APPROVED', 'CORRECTED'].includes(row.state)).length;
  const applicability = rows.filter(row => !['APPLICABLE', 'NOT_APPLICABLE'].includes(row.applicability)).length;
  const details = [
    interpretations && `${interpretations} ${interpretations === 1 ? 'interpretation needs' : 'interpretations need'} approval or correction`,
    applicability && `${applicability} ${applicability === 1 ? 'item needs' : 'items need'} applicability`,
  ].filter(Boolean);
  return details.length ? `${details.join(' · ')}. Applicable alone does not complete review.` : `${remaining} review item(s) remain; check conflicts and required notes.`;
}
export function ReviewProgress({progress, rows}) {
  const summary = Array.isArray(rows) ? reviewSummary(rows) : null;
  const total = summary?.total ?? progress?.total ?? 0;
  const resolved = summary?.resolved ?? progress?.resolved ?? 0;
  const remaining = Math.max(0, total - resolved);
  const complete = summary?.complete ?? progress?.complete ?? false;
  const percentage = total ? Math.round(resolved / total * 100) : 0;
  return (<div className="review-completion-block"><div className="review-completion-heading"><strong>Review progress</strong><b>{percentage}%</b></div>
      <div className="review-completion-track" role="progressbar" aria-label={`Review completion: ${resolved} of ${total} items resolved, ${remaining} remaining`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percentage}><span style={{width:`${percentage}%`}}/></div>
      <div className="review-completion-caption"><span>{resolved} of {total} resolved · {remaining} remaining</span><strong className={complete ? 'readiness-complete' : 'readiness-incomplete'}>{complete ? 'REVIEW COMPLETE' : 'REVIEW INCOMPLETE'}</strong></div>
    </div>);
}
export function ReviewDashboard({progress, rows}) {
  const summary = Array.isArray(rows) ? reviewSummary(rows) : null;
  const counts = [summary?.applicable || 0, summary?.notApplicable || 0, summary?.unassessed || 0];
  const countTotal = counts.reduce((sum, count) => sum + count, 0);
  const applicableEnd = countTotal ? counts[0] / countTotal * 360 : 0;
  const notApplicableEnd = countTotal ? (counts[0] + counts[1]) / countTotal * 360 : 0;
  return <div className="workflow-review-dashboard" aria-label="Human Review dashboard">
    <div className="review-applicability-block"><div className="workflow-review-gauge review-applicability-gauge" role="img" aria-label={`Applicability: ${counts[0]} applicable, ${counts[1]} not applicable, ${counts[2]} unassessed`} style={{'--applicable-end':`${applicableEnd}deg`,'--not-applicable-end':`${notApplicableEnd}deg`}}><span>{countTotal}<small>items</small></span></div>
      <div className="review-applicability-legend"><strong>Applicability</strong>{[['Applicable',counts[0],'#10a878'],['Not Applicable',counts[1],'#e45868'],['Unassessed',counts[2],'#a8bacb']].map(([label,count,color])=><div key={label}><i style={{background:color}}/><span>{label}</span><b>{count}</b></div>)}</div>
    </div>
  </div>;
}
function WorkflowGuide({tab, access, reviewProgress, reviewRows, environmentHandled, onStep, onContinueWithoutEvidence, compact=false}) {
  const guideRef = useRef(null);
  useEffect(() => {
    if (tab !== 'review' || compact) return;
    const update = () => {
      const guide = guideRef.current;
      if (guide) guide.style.setProperty('--review-guide-top', `${guide.getBoundingClientRect().top + window.scrollY}px`);
    };
    update();
    window.addEventListener('resize', update);
    const header = document.querySelector('.header');
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(update) : null;
    if (header) observer?.observe(header);
    return () => {window.removeEventListener('resize', update); observer?.disconnect();};
  }, [tab, compact]);
  const index = workflowSteps.findIndex(([id]) => id === tab);
  const previous = workflowSteps[index - 1], next = workflowSteps[index + 1];
  const [title, description, task] = workflowCopy[tab];
  const nextReason = tab === 'permit' ? 'Analyze a permit to continue.' : tab === 'review'
    ? reviewProgress ? reviewBlockerHint(reviewRows, reviewProgress.remaining) : 'Loading review status…' : 'Fetch evidence or acknowledge the gap to continue.';
  const stepActions = <div className="workflow-guide-actions">
    {previous && <button type="button" className="button secondary" onClick={() => onStep(previous[0])}>{tab === 'review' && !compact ? 'Back: Permit Intelligence' : 'Back'}</button>}
    {tab === 'environment' && !environmentHandled && <button type="button" className="button secondary" onClick={onContinueWithoutEvidence}>Continue with evidence gap</button>}
    {next && <button type="button" className="button primary" disabled={!access[next[0]]} title={!access[next[0]] ? nextReason : undefined} onClick={() => onStep(next[0])}>Next: {next[2]}</button>}
    {next && !access[next[0]] && tab !== 'review' && <small>{nextReason}</small>}
  </div>;
  return <section ref={guideRef} className={`workflow-guide ${compact ? 'workflow-guide-compact' : ''} ${tab === 'review' && !compact ? 'workflow-guide-review' : ''}`} aria-label={`Step ${index + 1} ${compact ? 'navigation' : 'guidance'}`}>
    <div className="workflow-guide-intro"><span className="workflow-guide-label">STEP {index + 1} OF 4</span>
      {!compact && <>{tab === 'review' ? <div className="workflow-guide-heading-row"><h2>{title}</h2>{stepActions}</div> : <h2>{title}</h2>}{description && <p>{description}</p>}{tab !== 'review' && <p className="workflow-guide-task"><strong>What to do:</strong> {task}</p>}
        {tab === 'environment' && environmentHandled && <p className="workflow-guide-progress">Environmental evidence step handled. You can continue to the decision.</p>}</>}
    </div>
    {tab === 'review' && !compact && reviewProgress && <ReviewDashboard progress={reviewProgress} rows={reviewRows}/>}
    {tab === 'review' && !compact && <div className="workflow-review-instructions"><p className="workflow-review-main-instruction">{task}</p><p className="workflow-review-start"><span aria-hidden="true">↓ ↓ ↓</span><b>START REVIEW — work through each item below</b><span aria-hidden="true">↓ ↓ ↓</span></p><p><strong>Approve:</strong> Is the AI’s interpretation of the permit text correct?</p><p><strong>Applicable:</strong> Does this permit condition apply to the work you plan to do?</p></div>}
    {!(tab === 'review' && !compact) && stepActions}
    {tab === 'review' && !compact && Array.isArray(reviewRows) && <div className="workflow-review-summary"><ReviewProgress progress={reviewProgress} rows={reviewRows}/><HumanReviewOverview summary={reviewSummary(reviewRows)}/></div>}
  </section>;
}
function limitTitle(label) {
  return String(label || '').replace(/\s+STOP(?:\s+(?:limit|threshold))?\b/ig, '').trim() || 'Permit limit';
}
function limitValue(label, value) {
  const text = String(value ?? '').trim();
  const name = limitTitle(label);
  const prefix = new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?=\\s|[:–—-]|$)\\s*[:–—-]?\\s*`, 'i');
  return text.replace(prefix, '').trim() || text;
}
const parameterIconEntries = [
  ['wave height', Waves], ['significant wave', Waves], ['wave period', Clock3], ['mean wave', Clock3],
  ['wind speed', Wind], ['wind gust', Wind], ['current speed', MoveHorizontal], ['eastward', ArrowRight],
  ['northward', ArrowUp], ['visibility', Eye], ['turbidity', Droplets], ['dissolved oxygen', Gauge],
  ['oxygen', Gauge], ['temperature', Thermometer]
];
export function EnvironmentalParameterIcon({label}) {
  const normalized = String(label || '').toLowerCase();
  const [, Icon] = parameterIconEntries.find(([term]) => normalized.includes(term)) || [];
  const Component = Icon || Gauge;
  if (normalized.includes('dissolved oxygen') || normalized.includes('oxygen')) return <span className="limit-icon oxygen-icon" aria-hidden="true">O₂</span>;
  return <span className="limit-icon" aria-hidden="true"><Component size={19}/></span>;
}
function ChartIcon({index, type}) {
  const Icon = type === 'pie' ? PieChartIcon : index === 1 ? ListChecks : BarChart3;
  return <Icon size={19} aria-hidden="true"/>;
}
function ScrollDownCue({active, analysisId}) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!active) { setVisible(false); return; }
    const update = () => setVisible(document.documentElement.scrollHeight - window.scrollY - window.innerHeight > 80);
    update();
    const frame = window.requestAnimationFrame(update);
    window.addEventListener('scroll', update, {passive:true});
    window.addEventListener('resize', update);
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener('scroll', update); window.removeEventListener('resize', update); };
  }, [active, analysisId]);
  if (!visible) return null;
  return <button type="button" className="permit-scroll-cue" aria-label="Scroll down for more permit information" title="Scroll down" onClick={() => window.scrollBy({top:Math.max(320, Math.round(window.innerHeight * .75)), behavior:'smooth'})}><ChevronDown size={30}/></button>;
}
export function scrollToPermitSection(id) {
  const target = document.getElementById(id);
  if (!target) return;
  const header = document.querySelector('.header');
  const position = header ? window.getComputedStyle(header).position : '';
  const headerHeight = header && ['sticky', 'fixed'].includes(position)
    ? header.getBoundingClientRect().height : 0;
  const top = Math.max(0, target.getBoundingClientRect().top + window.scrollY - headerHeight - 16);
  window.scrollTo({top, behavior:'smooth'});
}
export function Results({analysis,reviewData,onReview,active=true}) {
  const data = chartData(analysis.conditions);
  const unverified = analysis.conditions.filter(c => !c.source_verified).length;
  const summary = analysis.summary;
  const progress = reviewData?.review_progress;

  return <>
    <div className="permit-intro-screen"><section className="overview-hero permit-overview"><div className="page-heading"><div><div className="eyebrow">STEP 1 OF 4</div><h1>Permit Intelligence: <span>Review key permit details and limits here</span></h1><strong className="document-filename" title={analysis.filename}>{analysis.filename}</strong>{analysis.restoration_status === 'INCOMPLETE' && <p className="permit-extraction-warning" role="alert">Extraction incomplete — review the returned information and any missing fields.</p>}</div><div className="permit-hero-actions"><nav className="permit-quick-nav" aria-label="Permit section shortcuts">
      <button type="button" className="button secondary" onClick={()=>scrollToPermitSection('key-permit-limits')}>Key Permit Limits</button><button type="button" className="button secondary" onClick={()=>scrollToPermitSection('condition-overview')}>Condition Overview</button>
      </nav><div className="permit-review-action" role="status"><button type="button" className="button primary" onClick={()=>onReview?.()}>Next: Human Review <ArrowUpRight size={16}/></button></div></div></div></section>
    {analysis.mode === 'MOCK' && <div className="notice">Synthetic demonstration · These are mocked records, not extracted Kilkeel evidence.</div>}
    <section className="card permit-basic-information"><div className="section-heading"><h2><Info size={19}/> Basic Information</h2></div><div className="summary-grid permit-summary-grid">{[['Permit number', summary.permit_number], ['Validity', `${fallback(summary.valid_from)} — ${fallback(summary.valid_until)}`], ['Activity', summary.activity], ['Licensee', summary.licensee], ['Issuing authority', summary.authority], ['Total conditions', analysis.conditions.length]].map(([label, value]) => <section className="card metric" key={label}><div className="eyebrow">{label}</div><strong>{fallback(value)}</strong></section>)}</div></section>
    <GeofenceCard geofences={analysis.geofences}/></div>
    <section className="card limits" id="key-permit-limits"><div className="section-heading"><div><h2><BarChart3 size={19}/> Key Permit Limits</h2></div></div>
      {analysis.key_limits.length ? <div className="limits-grid">{analysis.key_limits.map((l, i) => { const sourceState = typeof l.source_verified === 'boolean' ? l.source_verified : null; const stop = /\bstop\b/i.test(`${l.label} ${l.value}`); const title = limitTitle(l.label); return <div key={i} className={`limit ${stop ? 'limit-stop' : ''}`}><EnvironmentalParameterIcon label={l.label}/><div className="limit-copy"><strong>{title}{stop && <span className="limit-title-stop"> · STOP threshold</span>}</strong><b>{limitValue(l.label, l.value)}</b>{sourceState === false && <small><Info size={13}/> Source verification required</small>}{sourceState === null && <small><Info size={13}/> Source status not stated</small>}</div></div>; })}</div> : <p className="muted">No key limits returned. Review the original permit for completeness.</p>}
    </section>
    {!!analysis.warnings?.length && <div className="notice warning">{analysis.warnings.map(w => <p key={w}>{w}</p>)}</div>}
    {!!unverified && <div className="notice warning">{unverified} condition{unverified === 1 ? ' requires' : 's require'} source verification. Review the original quotations in Human Review. <button type="button" className="decision-link" onClick={()=>onReview?.()}>Next: Open Human Review</button></div>}
    <section className="card permit-chart-section" id="condition-overview"><div className="section-heading"><h2><PieChartIcon size={19}/> Condition Overview</h2></div><div className="chart-grid"><Chart label="Conditions by Phase" title={<><ChartIcon index={0} type="bar"/>Conditions by Phase</>} data={data.phase} type="bar" index={0}/><Chart label="Conditions by Requirement Type" title={<><ChartIcon index={1} type="bar"/>Conditions by Requirement Type</>} data={data.category} type="bar" index={1}/><Chart label="Conditions with Explicit Limits" title={<><ChartIcon type="pie"/>Conditions with Explicit Limits</>} data={data.limits} type="pie"/></div></section>
    <ScrollDownCue active={active} analysisId={analysis.analysis_id}/>
  </>;
}
export default function App() {
  const [session, setSession] = useState(null);
  const [file, setFile] = useState(null);
  const [currentAnalysis, setCurrentAnalysis] = useState(null);
  const [status, setStatus] = useState('empty');
  const [error, setError] = useState('');
  const [tab, setTab] = useState('permit');
  const [reviewTarget, setReviewTarget] = useState(null);
  const [reviewData, setReviewData] = useState(null);
  const [environmentAcknowledged, setEnvironmentAcknowledged] = useState(false);
  const [assessmentStale, setAssessmentStale] = useState(false);
  const input = useRef(null);
  const generation = useRef(0);
  const boot = useRef(null);
  const restoredBoot = useRef(null);
  const reviewProgress = reviewData?.review_progress || (Array.isArray(reviewData?.requirements) ? (()=>{const summary=reviewSummary(reviewData.requirements);return {total:summary.total,resolved:summary.resolved,remaining:summary.total-summary.resolved,complete:summary.complete};})() : null);
  const reviewComplete = !!(currentAnalysis && reviewData?.analysis_run_id === currentAnalysis.analysis_id && reviewProgress?.complete);
  const evidenceRetrieved = !!(currentAnalysis && session?.environmental_result?.analysis_id === currentAnalysis.analysis_id);
  const environmentHandled = evidenceRetrieved || environmentAcknowledged;
  const access = {permit:true, review:!!currentAnalysis, environment:reviewComplete, decision:reviewComplete && environmentHandled};
  const completed = {permit:!!currentAnalysis, review:reviewComplete, environment:reviewComplete && environmentHandled,
    decision:!!(access.decision && session?.decision_result && !assessmentStale)};
  useEffect(() => {
    if (tab === 'decision' && !access.decision) setTab(access.environment ? 'environment' : access.review ? 'review' : 'permit');
    else if (tab === 'environment' && !access.environment) setTab(access.review ? 'review' : 'permit');
    else if (tab === 'review' && !access.review) setTab('permit');
  }, [tab, access.review, access.environment, access.decision]);
  function acknowledgeEvidenceGap() {
    if (!currentAnalysis || !reviewComplete) return;
    setEnvironmentAcknowledged(true);
    if (session?.boot_id) sessionStorage.setItem(`permitpulse:environmentGap:${session.boot_id}:${currentAnalysis.analysis_id}`, 'true');
  }
  useEffect(() => {
    if (!currentAnalysis || !session?.boot_id) {setEnvironmentAcknowledged(false);return;}
    setEnvironmentAcknowledged(sessionStorage.getItem(`permitpulse:environmentGap:${session.boot_id}:${currentAnalysis.analysis_id}`) === 'true');
  }, [currentAnalysis?.analysis_id, session?.boot_id]);
  useEffect(() => {
    setReviewData(null);
    if (!currentAnalysis || !session) return;
    let active = true;
    fetch(`/api/reviews?analysis_id=${encodeURIComponent(currentAnalysis.analysis_id)}`, {headers:{'X-Session-Id':session.boot_id}})
      .then(async response => {if(!response.ok) throw new Error('Review status unavailable'); return response.json();})
      .then(data => {if(active && data.analysis_run_id===currentAnalysis.analysis_id){setReviewData(data);}})
      .catch(() => {if(active)setReviewData(null);});
    return () => {active=false;};
  }, [currentAnalysis?.analysis_id, session?.boot_id]);
  function updateReview(data) {
    setReviewData(data);

    setAssessmentStale(true);
    setSession(previous => previous ? {...previous,decision_result:null,invalidated_assessment_id:previous.decision_result?.assessment_id || previous.invalidated_assessment_id} : previous);
  }
  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const response = await fetch('/api/session');
        if (!response.ok) return;
        const s = await response.json();
        if (!mounted) return;
        if (boot.current && boot.current !== s.boot_id) reset();
        boot.current = s.boot_id; setSession(s);
        if (restoredBoot.current !== s.boot_id) {
          restoredBoot.current = s.boot_id;
          const query = new URLSearchParams(window.location.search);
          const queryHash = query.get('document_sha256'), queryRun = query.get('analysis_run_id');
          const raw = queryHash && queryRun ? JSON.stringify({document_sha256:queryHash, analysis_run_id:queryRun}) : localStorage.getItem('permitpulse:lastAnalysisRef');
          if (raw) {
            try {
              const ref = JSON.parse(raw);
              const restored = await fetch('/api/restore', {method:'POST', headers:{'Content-Type':'application/json','X-Session-Id':s.boot_id}, body:JSON.stringify(ref)});
              if (restored.ok && mounted) { setCurrentAnalysis(await restored.json()); setStatus('complete'); setTab('permit'); }
            } catch { /* A missing or malformed saved reference never triggers analysis. */ }
          }
        }
      } catch { /* A transient health failure never triggers extraction. */ }
    };
    check(); const timer = setInterval(check, 3000);
    return () => {mounted = false; clearInterval(timer);};
  }, []);
  function reset() { generation.current++; setCurrentAnalysis(null); setReviewData(null); setEnvironmentAcknowledged(false); setAssessmentStale(false); setTab('permit'); setFile(null); setStatus('empty'); setError(''); if (input.current) input.current.value = ''; }
  async function analyze() {
    if (!file || !session || status === 'loading') return;
    const ticket = ++generation.current;
    setStatus('loading'); setError(''); setCurrentAnalysis(null);
    try {
      const response = await fetch('/api/analyze', {method: 'POST', headers: {'Content-Type': 'application/pdf', 'X-Filename': encodeURIComponent(file.name), 'X-Session-Id': session.boot_id}, body: file});
      if (!response.ok) {
        const detail = typeof response.json === 'function' ? await response.json().catch(() => ({})) : {};
        if (detail.error === 'EXTRACTION_INCOMPLETE') {
          throw new Error(`Environmental extraction incomplete: ${detail.extracted_count || 0} of ${detail.candidate_count || 0} candidate requirements extracted. Re-analysis or human review is required.`);
        }
        throw new Error('Permit analysis could not be completed.');
      }
      const result = await response.json();
      if (ticket !== generation.current) return;
      localStorage.setItem('permitpulse:lastAnalysisRef', JSON.stringify({document_sha256:result.document_sha256, analysis_run_id:result.analysis_id}));
      setReviewData(null);setEnvironmentAcknowledged(false);setAssessmentStale(false);setCurrentAnalysis(result); setTab('permit'); setStatus('complete');
    } catch (cause) {
      if (ticket !== generation.current) return;
      setStatus('error'); setError(cause?.message || 'Permit analysis could not be completed.');
    }
  }
  return <div className="app"><header className="header"><div className="brand"><img className="brand-symbol" src={brandLogo} alt=""/><div><img className="brand-wordmark" src={brandWordmark} alt="PermitPulse"/><span>Evidence first. Human review always.</span></div></div><AppNav tab={tab} setTab={setTab} access={access} completed={completed}/><button className="button secondary new-analysis" onClick={reset} disabled={status === 'loading'}><Plus size={16}/> New Analysis</button></header>
    <main className={tab === 'permit' && currentAnalysis ? 'main-permit-result' : undefined}>
    {(tab !== 'permit' || !currentAnalysis) && <WorkflowGuide tab={tab} access={access} reviewProgress={reviewProgress} reviewRows={reviewData?.requirements} environmentHandled={environmentHandled} onStep={setTab} onContinueWithoutEvidence={acknowledgeEvidenceGap}/>}
    {tab === 'decision' && access.decision && <DecisionWorkWindows key={currentAnalysis?.analysis_id || 'empty'} analysis={currentAnalysis} session={assessmentStale ? {...session,decision_result:null} : session} reviewReady={reviewComplete} reviewProgress={reviewProgress} assessmentStale={assessmentStale} onEvaluated={decision=>{setAssessmentStale(false);setSession(previous=>previous ? {...previous,decision_result:decision,invalidated_assessment_id:null} : previous);}} onReview={id=>{setReviewTarget(id);setTab('review');}}/>}
    {tab === 'review' && <HumanReview key={currentAnalysis?.analysis_id || 'empty'} analysis={currentAnalysis} session={session} initialTargetId={reviewTarget} onUpdated={updateReview} onLoaded={setReviewData}/>}
    <div hidden={tab !== 'environment'}><Environmental key={currentAnalysis?.analysis_id || 'empty'} analysis={currentAnalysis} session={session} reviewData={reviewData ? {...reviewData,review_progress:reviewProgress} : null}/></div>
    <div hidden={tab !== 'permit'}>{currentAnalysis ? <Results analysis={currentAnalysis} reviewData={reviewData ? {...reviewData,review_progress:reviewProgress} : null} active={tab === 'permit'} onReview={id=>{setReviewTarget(id);setTab('review');}}/> : <>
      <div className="empty-heading"><div className="eyebrow">CLARITY BEFORE YOU OPERATE</div><h1>Analyze a Marine Permit</h1><p>Upload a PDF to extract its conditions, deadlines,<br className="desktop-break"/> operational limits and key compliance requirements.</p></div>
      <section className="upload-card card"><div className="upload-icon">{status === 'loading' ? <LoaderCircle className="spinner" size={30}/> : <Upload size={30}/>}</div>
        {status === 'loading' ? <div role="status"><h2>Analyzing permit…</h2><p>Reading your document and extracting conditions, limits and deadlines.</p><div className="progress-track"><div/></div><small>Preparing your dashboard. Please keep this window open.</small></div> : <>
          <h2>{file ? file.name : 'Start with your permit'}</h2><p>{file ? `${(file.size / 1024).toFixed(0)} KB · Ready to analyze` : 'Select a PDF document. Your original evidence stays intact.'}</p>
          <input ref={input} type="file" accept="application/pdf,.pdf" aria-label="Upload permit PDF" onChange={e => {setFile(e.target.files?.[0] || null); setError(''); setStatus('empty');}}/>
          <div className="upload-actions"><button className="button secondary" onClick={() => input.current?.click()}><Upload size={16}/>{file ? 'Change PDF' : 'Upload Permit'}</button><button className="button primary" disabled={!file || !session} onClick={analyze}>{status === 'error' ? 'Try Again' : 'Analyze'}<ArrowUpRight size={17}/></button></div><small>PDF documents · Up to 25 MB · Small permits analyzed in one pass</small>
        </>}
        {error && <div role="alert" className="error"><AlertCircle size={18}/>{error}</div>}
      </section>
      {session?.mode === 'MOCK' && <div className="mock-label">Offline preview · Synthetic mocked responses · No OpenAI calls</div>}
      <div className="empty-state"><Waves size={26}/><p>No permit analyzed yet. Upload a permit to begin.</p></div>
      <div className="features">{[['Complete conditions', 'Numbered requirements and administrative duties.'], ['Limits & deadlines', 'Important values, timing and restrictions.'], ['Original evidence', 'Source quotations and physical page references.']].map(([title, description]) => <div key={title}><FileText size={18}/><h3>{title}</h3><p>{description}</p></div>)}</div>
    </>}</div>
    <WorkflowGuide compact tab={tab} access={access} reviewProgress={reviewProgress} environmentHandled={environmentHandled} onStep={setTab} onContinueWithoutEvidence={acknowledgeEvidenceGap}/>
    </main><div className="bottom-line"><span>PermitPulse</span><span>Evidence first. Human review always.</span></div></div>;
}
