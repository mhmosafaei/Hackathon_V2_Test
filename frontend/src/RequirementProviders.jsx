import React from 'react';
import {ChevronDown, ExternalLink, Waves, Wind, Database, FileText} from 'lucide-react';
import './RequirementProviders.css';

const names = {
  COPERNICUS_MARINE: ['Copernicus Marine', Waves, 'https://marine.copernicus.eu/', 'Retrieved through the Copernicus Marine service.'],
  ECMWF_FORECAST: ['ECMWF Forecast', Wind, 'https://open-meteo.com/en/docs', 'ECMWF IFS forecast via the public Open-Meteo API. No API key required.'],
  ERA5: ['Historical / ERA5', Database, 'https://open-meteo.com/en/docs/historical-weather-api', 'ERA5 historical data via the Open-Meteo archive API. No API key required.'],
  EXTERNAL: ['External Evidence', FileText, null, 'Evidence must be supplied separately; no automatic connection.'],
  UNAVAILABLE: ['Unavailable Source', Database, null, 'No live connector is available for these variables.'],
  NOT_APPLICABLE: ['No Retrieval Required', FileText, null, 'These requirements do not request an environmental data source.'],
};
const pretty = value => String(value || 'Unspecified variable').replaceAll('_', ' ');
const conditionKey = (row, index) => row.condition_id == null ? `missing-${index}` : String(row.condition_id);
const capabilityName = variable => ({surface_current_speed:'current_speed',surface_current_direction:'current_direction'}[variable] || variable);
export default function RequirementProviders({rows = [], providers = {}, capabilities = [], mock = false, renderVariableDetails, configuration = providers}) {
  const keys=['COPERNICUS_MARINE','ECMWF_FORECAST','ERA5'];
  const total=new Set(rows.map(conditionKey)).size;
  function variablesFor(items) {
    return [...new Set(items.map(row=>row.canonical_variable))].map(variable=>{
      const matching=items.filter(row=>row.canonical_variable===variable);
      const capability=capabilities.find(c=>capabilityName(c.canonical_variable)===capabilityName(variable));
      const Icon=names[matching[0].routing?.preferred_provider]?.[1] || Database;
      return <details className="requirement-variable" data-testid="environment-variable" key={variable || 'unspecified'}><summary><Icon size={17}/><strong>{capability?.display_name || pretty(variable)}</strong><ChevronDown size={15} className="requirement-expand"/></summary><div className="requirement-variable-body">
        <p className="requirement-variable-capability"><strong>Conditions:</strong> {[...new Set(matching.map(row=>row.condition_id).filter(id=>id != null && String(id).trim() !== ''))].join(', ') || 'Not stated'}</p>
        <div className="requirement-variable-unit"><span>Permit unit: {[...new Set(matching.map(row=>row.unit || 'Not stated'))].join(', ')}</span>{capability && <><span>Data unit: {capability.unit || 'Not stated'}</span><b className={`requirement-coverage-state ${capability.implementation_status.toLowerCase()}`}>{pretty(capability.implementation_status)}</b></>}</div>
        {capability && <p className="requirement-variable-capability">{capability.derived ? 'Derived from compatible input variables. ' : ''}{capability.notes}</p>}
        {matching.some(row=>!row.routing?.implemented) && <p className="requirement-variable-capability">Live retrieval is not configured for this variable.</p>}
        {renderVariableDetails?.(matching)}
      </div></details>;
    });
  }
  const additional=rows.filter(row=>!keys.includes(row.routing?.preferred_provider));
  return <section className="card requirement-providers" aria-label="Environmental requirements and providers">
    <div className="requirement-providers-heading"><div><h2><Waves size={19}/> Data Sources & Variables</h2><p>Click a variable for units and data details. Review permit conditions in Human Review.</p></div><strong className="requirement-total">{total}<span>requirements</span></strong></div>
    <div className="requirement-provider-cards">{keys.map(key=>{
      const [name,Icon,href,method]=names[key];
      const items=rows.filter(row=>row.routing?.preferred_provider===key);
      const status=String(providers[key] || '');
      const configured=/credentials configured|^Connected\b/i.test(String(configuration[key] || status));
      const retrieved=!mock && /^Connected\b/i.test(status) && !/not tested|mock|synthetic/i.test(status);
      const sourceStatus=mock ? 'Offline preview' : key==='COPERNICUS_MARINE' ? configured ? 'Credentials configured' : 'Credentials required' : 'Public API · no key required';
      return <article className="requirement-provider-card" key={key} aria-label={name}>
        <header className="requirement-provider-card-heading"><Icon size={22}/><a href={href} target="_blank" rel="noreferrer">{name}<ExternalLink size={12}/></a><span className="requirement-source-config">{sourceStatus}</span></header>
        <p className="requirement-provider-method">{method}</p>
        {key==='COPERNICUS_MARINE' && !configured && <p className="requirement-credentials">Configure your Copernicus Marine username and password in the backend .env file.</p>}
        {retrieved && <p className="requirement-source-retrieved">Live retrieval completed.</p>}
        <div className="requirement-provider-variables">{items.length ? variablesFor(items) : <p className="requirement-provider-empty">No variables required by this permit.</p>}</div>
      </article>;
    })}</div>
    {additional.length>0 && <div className="requirement-additional-evidence"><h3>Additional Evidence</h3><p>These variables need an external source or do not have a configured live connector.</p>{variablesFor(additional)}</div>}
  </section>;
}
