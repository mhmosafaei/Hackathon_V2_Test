import React from 'react';
import { AlertTriangle, CheckCircle2, Clock3, FileText, Pencil, XCircle, Ban, HelpCircle } from 'lucide-react';
import './HumanReviewOverview.css';

const metrics = [
  ['total', 'Total conditions', FileText, 'neutral'],
  ['approved', 'Approved', CheckCircle2, 'approved'],
  ['corrected', 'Corrected', Pencil, 'corrected'],
  ['pending', 'Pending review', Clock3, 'pending'],
  ['rejected', 'Rejected', XCircle, 'rejected'],
  ['applicable', 'Applicable', CheckCircle2, 'approved'],
  ['notApplicable', 'Not applicable', Ban, 'rejected'],
  ['unassessed', 'Unassessed', HelpCircle, 'neutral'],
  ['gaps', 'Source / review gaps', AlertTriangle, 'warning'],
];

export default function HumanReviewOverview({ summary, filename, analysisId }) {
  const total = summary.total || 0;
  const resolved = summary.resolved || 0;
  const percent = total ? Math.round((resolved / total) * 100) : 0;
  const applicableTotal = summary.applicable + summary.notApplicable + summary.unassessed;
  const applicablePct = applicableTotal ? (summary.applicable / applicableTotal) * 100 : 0;
  const notApplicablePct = applicableTotal ? (summary.notApplicable / applicableTotal) * 100 : 0;
  return <div className="human-review-overview">
    <section className="review-panel overview-main" aria-label="Human review overview">
      <div className="overview-heading"><div><span className="review-label">Interpretation verification</span><h1>Human Review</h1><p title={filename}>{filename} · Run {analysisId}</p></div><span className={`review-badge ${summary.complete ? 'review-approved' : 'review-unreviewed'}`}>{summary.complete ? 'REVIEW COMPLETE' : 'REVIEW REQUIRED'}</span></div>
      <p>Review the AI-extracted permit interpretation before it is used by downstream decision assessment.</p>
      <div className="overview-metrics">{metrics.map(([key, name, Icon, tone]) => <div className={`overview-metric overview-${tone}`} key={key}><span className="overview-icon"><Icon size={17}/></span><b>{summary[key] || 0}</b><span>{name}</span></div>)}</div>
    </section>
    <aside className="review-panel overview-progress" aria-label="Review progress">
      <h2>Review progress</h2><div className="overview-progress-track"><span style={{width:`${percent}%`}}/></div><div className="overview-progress-label"><strong>{resolved} of {total} items resolved</strong><b>{percent}%</b></div>
      <h3>Applicability overview</h3><div className="overview-app-track"><span className="overview-applicable" style={{width:`${applicablePct}%`}}/><span className="overview-not-applicable" style={{width:`${notApplicablePct}%`}}/></div>
      <ul><li><i className="dot dot-green"/>Applicable <b>{summary.applicable}</b></li><li><i className="dot dot-red"/>Not applicable <b>{summary.notApplicable}</b></li><li><i className="dot dot-gray"/>Unassessed <b>{summary.unassessed}</b></li></ul>
    </aside>
  </div>;
}
