import React from 'react';
import { AlertTriangle, CheckCircle2, Clock3, FileText, Pencil, XCircle } from 'lucide-react';
import './HumanReviewOverview.css';

const metrics = [
  ['total', 'Total review items', FileText, 'neutral'],
  ['approved', 'Approved', CheckCircle2, 'approved'],
  ['corrected', 'Corrected', Pencil, 'corrected'],
  ['pending', 'Pending review', Clock3, 'pending'],
  ['rejected', 'Rejected', XCircle, 'rejected'],
  ['gaps', 'Source / review gaps', AlertTriangle, 'warning'],
];

export default function HumanReviewOverview({ summary }) {
  return <div className="human-review-overview" aria-label="Review status summary">
      <div className="overview-metrics">{metrics.map(([key, name, Icon, tone]) => <div className={`overview-metric overview-${tone}`} key={key}><span className="overview-icon"><Icon size={17}/></span><b>{summary[key] || 0}</b><span>{name}</span></div>)}</div>
  </div>;
}
