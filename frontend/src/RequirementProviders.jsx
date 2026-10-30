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
export default function RequirementProviders({rows = [], providers = {}, capabilities = [], mock = false, renderConditions}) {
  const groups = new Map();
  rows.forEach((row, index) => {
    const provider = row.routing?.preferred_provider || 'UNAVAILABLE';
    if (!groups.has(provider)) groups.set(provider, []);
    groups.get(provider).push({...row, conditionKey: conditionKey(row, index)});
  });
  const total = new Set(rows.map(conditionKey)).size;
  return <section className="card requirement-providers" aria-label="Environmental requirements and providers">
    <div className="requirement-providers-heading"><div><h2><Waves size={19}/> Environmental Requirements</h2><p>Select a variable to inspect its permit conditions, units and capability details.</p></div><strong className="requirement-total">{total}<span>requirements</span></strong></div>
    <div className="requirement-provider-columns" aria-hidden="true"><span>Required Evidence</span><span>Data Source & Connection</span></div>
    {[...groups].map(([key, items]) => {
      const [name, Icon, href, method] = names[key] || [pretty(key), Database, null, 'No automatic retrieval is configured.'];
      const variables = [...new Set(items.map(row => row.canonical_variable))];
      const count = new Set(items.map(row => row.conditionKey)).size;
      const status = String(providers[key] || '');
      const connected = !mock && /^Connected\b/i.test(status) && !/not tested|mock|synthetic/i.test(status);
      const failed = !connected && /failed|error/i.test(status);
      const credentialRequired = key === 'COPERNICUS_MARINE' && !/credentials configured|^Connected\b/i.test(status);
      const connectionNote = mock ? 'Offline preview · no live connection confirmed.' : connected ? /connection check/i.test(status) ? 'Connection check passed. Evidence not yet retrieved.' : 'Live retrieval completed.' : failed ? 'Last connection attempt failed.' : /credentials required/i.test(status) ? 'Credentials required before connecting.' : ['EXTERNAL','UNAVAILABLE','NOT_APPLICABLE'].includes(key) ? 'No automatic connection.' : 'Connection not tested yet. Use Check Connections above to check.';
      return <div className="requirement-provider-row" key={key}>
        <div className="requirement-source-group"><p className="requirement-variable-group-count">{count} requirement{count === 1 ? '' : 's'} · {variables.length} variable{variables.length === 1 ? '' : 's'}</p>{variables.map(variable => {
          const matching = items.filter(row => row.canonical_variable === variable);
          const ids = [...new Set(matching.map(row => row.condition_id).filter(id => id != null))];
          const capability = capabilities.find(c => capabilityName(c.canonical_variable) === capabilityName(variable));
          return <details className="requirement-variable" key={variable || 'unspecified'}><summary><Icon size={18}/><div><strong>{capability?.display_name || pretty(variable)}</strong><span>Condition{ids.length === 1 ? '' : 's'} {ids.join(', ') || 'not specified'}</span></div><ChevronDown size={16} className="requirement-expand"/></summary><div className="requirement-variable-body">
            <div className="requirement-variable-unit"><span>Permit unit: {matching[0].unit || 'Not stated'}</span>{capability && <><span>Data unit: {capability.unit || 'Not stated'}</span><b className={`requirement-coverage-state ${capability.implementation_status.toLowerCase()}`}>{pretty(capability.implementation_status)}</b></>}</div>
            {capability && <p className="requirement-variable-capability">{capability.derived ? 'Derived from compatible input variables. ' : ''}{capability.notes}</p>}
            {renderConditions ? renderConditions(matching) : matching.map((row,i)=><article className="requirement-condition-detail" key={i}><h4>Condition {row.condition_id}</h4><p>{row.requirement_text}</p></article>)}
          </div></details>;
        })}</div>
        <div className="requirement-provider-connection"><div className="requirement-connection-heading">{href ? <a href={href} target="_blank" rel="noreferrer">{name}<ExternalLink size={13}/></a> : <strong>{name}</strong>}<span className={`requirement-connect-state ${connected ? 'is-connected' : 'is-disconnected'}`}>{connected ? 'Connected' : 'Not connected'}</span></div><p>{method}</p><small>{connectionNote}</small>{key === 'COPERNICUS_MARINE' && <div className="requirement-credentials">{credentialRequired ? 'Credentials required: configure your Copernicus Marine username and password in the backend .env file.' : 'Copernicus Marine credentials configured.'}</div>}</div>
      </div>;
    })}
    {!groups.size && <p className="requirement-providers-empty">No environmental requirements identified in this permit.</p>}
  </section>;
}
