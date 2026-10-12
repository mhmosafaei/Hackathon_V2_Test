"""PermitPulse Stage 0 Streamlit shell."""

from pathlib import Path
import os
from uuid import uuid4
from datetime import datetime, timezone, date
from dotenv import load_dotenv

import streamlit as st

from src.config import load_settings
from src.documents.page_filter import select_relevant_pages
from src.documents.pdf_parser import parse_pdf
from src.documents.extractor import extract_pages, openai_request
from src.documents.validator import validate_conditions
from src.permit.classification import classify
from src.permit.rule_factory import make_rule
from src.models.common import ReviewState
from src.permit.review import load_conditions, load_decisions, load_recovery, save_decision
from src.permit.document_store import available_documents, load_document, analysis_result_notice, resolve_active_permit, load_decisions as load_document_decisions, save_decision as save_document_decision, BELFAST_KEY
from src.permit.upload_flow import analyze_upload, analyze_ai_first_upload, local_mock_candidate_request
from src.documents.exports import csv_bytes, export_json, excel_bytes
from src.documents.ai_first import document_identity
from src.intelligence.dashboard import render_intelligence_dashboard
from src.runtime import runtime_metadata, pre_dispatch_runtime_check
from src.environment.dashboard import load_belfast, marine_series, weather_series, evidence_readiness
from src.environment.analytics import summary, rainfall_total, advisory_windows, exceedance_hours
from src.environment.synchronization import shared_hourly_grid, advisory_intervals, coverage_percent
from src.environment.location import retrieve_location
from src.permit.decision_ui import readiness, demonstration
from src.documents.pdf_parser import parse_pdf_bytes, PdfPage
from src.contracts.service import document_id as contract_document_id, extract_weather_clauses, save_clauses, load_clauses, save_review as save_contract_review, reviews as contract_reviews, analyse_confirmed
from src.models.contract_clause import ContractReviewState
from src.historical.analysis import select_mode, equivalent_periods
from src.historical.service import analyse_history
from src.environment.synchronization import parse_utc


ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


def main() -> None:
    settings = load_settings(ROOT / "config" / "settings.yaml")
    # Runs inside the actual Streamlit worker on every rerender.  It performs
    # no network activity; a live Analyze call invokes it again immediately
    # before constructing the dispatch ledger.
    try:
        live_runtime_preflight = pre_dispatch_runtime_check()
    except RuntimeError as exc:
        live_runtime_preflight = {"ready": False, "error": str(exc), **runtime_metadata()}
    st.set_page_config(page_title="PermitPulse", layout="wide")
    st.markdown("""<style>.stApp{background:#f6f9fb}.stMetric{border-left:3px solid #167d9a;padding-left:.6rem}.stAlert{border-radius:.45rem}</style>""",unsafe_allow_html=True)
    st.title("PermitPulse")
    st.caption("Evidence-backed marine permit and contract intelligence · review-gated · advisory only")

    with st.sidebar:
        st.subheader("Foundation status")
        st.caption(f"Mode: {settings.mode.value}")
        st.info("External data connections are intentionally not enabled in Stage 0.")

    permit_tab, environment_tab, decision_tab, contract_tab = st.tabs(
        ["Permit Operations", "Environmental Intelligence", "Permit Decision Intelligence", "Marine Contract Weather Intelligence"]
    )
    with permit_tab:
        st.header("Permit Operations")
        upload=st.file_uploader('Upload permit PDF',type='pdf')
        if upload:
            st.info('Analyze creates resumable, provenance-preserving checkpoints. Document text is treated as data; review is required before any rule can be executable.')
            mock_upload=st.checkbox('Use local mocked AI response (sanitized test only)',value=False,help='Exercises the complete candidate/review workflow without sending this file to OpenAI.')
            live_acceptance=st.checkbox('Fresh capped live acceptance run',value=bool(st.query_params.get('analysis_run_id')),help='Uses a new run namespace, at most five OpenAI requests and a $0.15 estimated-cost ceiling. Requires explicit authorization before Analyze.')
            analysis_run_id=None
            if live_acceptance:
                query_run_id=st.query_params.get('analysis_run_id')
                if 'live_acceptance_run_id' not in st.session_state:
                    st.session_state.live_acceptance_run_id=query_run_id if isinstance(query_run_id,str) and query_run_id else f'acceptance-{uuid4().hex}'
                analysis_run_id=st.text_input('Acceptance analysis run ID',value=st.session_state.live_acceptance_run_id,key='live_acceptance_run_id')
                st.query_params['analysis_run_id']=analysis_run_id
                st.caption('Guardrails: two compact-schema candidate batches followed by local normalization and coverage; five requests maximum; $0.15 estimated-cost ceiling; 8,000-token candidate ceiling; no automatic retry. No additional intelligence-stage requests.')
                candidate_diagnostic=st.checkbox('One-request candidate diagnostic (batch 1 only)',value=False,help='Sends only the first candidate batch, caps the ledger at one request, and never dispatches batch 2 or intelligence stages.')
            else:
                candidate_diagnostic=False
            if st.button('Analyze document'):
                try:
                    if mock_upload and live_acceptance:
                        raise ValueError('A fresh live acceptance run cannot use mocked AI transport')
                    with st.status('Analyzing permit',expanded=True) as status:
                        st.write('Validating PDF and identifying conditions…')
                        if mock_upload:
                            result=analyze_ai_first_upload(ROOT,upload.name,upload.getvalue(),request=local_mock_candidate_request)
                        elif live_acceptance:
                            result=analyze_ai_first_upload(ROOT,upload.name,upload.getvalue(),analysis_run_id=analysis_run_id,live_acceptance=True,diagnostic_candidate_batch_only=candidate_diagnostic)
                        else:
                            result=analyze_upload(ROOT,upload.name,upload.getvalue())
                        if result.get('state') in {'FAILED', 'DIAGNOSTIC_FAILED'}:
                            status.update(label='Analysis failed — results incomplete',state='error')
                        elif candidate_diagnostic:
                            st.write('Candidate batch 1 diagnostic complete. No further candidate or intelligence stages were dispatched.')
                            status.update(label='Diagnostic complete',state='complete')
                        else:
                            st.write('Candidate discovery, source verification and coverage checkpointing complete.')
                            status.update(label='Ready for human review',state='complete')
                    if result.get('run_identity'):
                        st.session_state['active_permit'] = result['run_identity']
                    notice_type, notice = analysis_result_notice(result)
                    getattr(st, notice_type)(notice)
                except Exception as exc:
                    failed_key = document_identity(upload.getvalue(), os.environ.get('OPENAI_MODEL', ''), analysis_run_id)
                    if failed_key in available_documents(ROOT):
                        st.session_state['active_permit'] = failed_key
                    st.error(f'Analysis did not complete: {type(exc).__name__}: {exc}')
        documents=available_documents(ROOT)
        st.session_state['active_permit'] = resolve_active_permit(documents, st.session_state.get('active_permit'), st.query_params.get('analysis_run_id'))
        active_key=st.selectbox('Active permit',list(documents),format_func=lambda key:documents[key]['title'],key='active_permit')
        spec,conditions,coverage_data=load_document(ROOT,active_key)
        st.subheader(f"Review: {spec['title']}")
        st.caption(f"{spec['pages'] or 'Unknown'} physical pages · {len(conditions)} reviewable records · processing {spec['version']}")
        if spec.get('candidate_mode'):
            st.caption(f"Selected run: {spec.get('analysis_run_id') or active_key} · extraction: {spec.get('extraction_status', 'UNKNOWN')} · recorded dispatches: {spec.get('dispatch_count', 0)}")
            if spec.get('outcome_unknown'):
                st.error('This historical run is blocked by an OUTCOME_UNKNOWN request. It cannot be resumed automatically. A separately identified fresh run is required for further analysis.')
            elif spec.get('extraction_status') == 'FAILED':
                st.error('Extraction failed. These saved artifacts are incomplete and are not completed analysis results.')
            for batch_error in spec.get('batch_errors', []):
                st.caption(batch_error)
            if not conditions:
                st.info('No candidate obligations were retained for this run. Selecting another document does not restart analysis.')
        intelligence_path = spec['aggregate'].parent / 'intelligence_analysis_v1.json'
        if intelligence_path.exists():
            render_intelligence_dashboard(st, intelligence_path)
            st.divider()
            st.caption('Source review and recovery controls below remain document-scoped and do not approve operational rules.')
        if coverage_data:
            coverage_summary=coverage_data.get('summary',{}); c1,c2,c3,c4=st.columns(4)
            processed_pages=coverage_data.get('processed_pages',coverage_summary.get('processed_pages',0))
            processed_count=len(processed_pages) if isinstance(processed_pages,list) else processed_pages
            candidate_mode=spec.get('candidate_mode',False)
            review_count=len(conditions) if candidate_mode else coverage_summary.get('REVIEW_REQUIRED',coverage_summary.get('pages_without_candidates',0))
            c1.metric('Source conditions / pages',coverage_data.get('source_conditions_inventoried',coverage_data.get('physical_pages','—')))
            c2.metric('Captured / processed',coverage_summary.get('CAPTURED',processed_count))
            c3.metric('Missing / failed',coverage_summary.get('MISSING',coverage_summary.get('failed_pages',0)))
            c4.metric('Review required',review_count)
            if not coverage_data.get('semantic_coverage_complete',coverage_summary.get('MISSING',0) == 0 and coverage_summary.get('PARTIALLY_CAPTURED',0) == 0): st.warning('Coverage is not a legal-completeness finding. Human review remains required before operational use.')
        if active_key==BELFAST_KEY: decisions=load_decisions(ROOT)
        else: decisions=load_document_decisions(ROOT,spec['hash'],spec['version'])
        if conditions:
            candidate_mode=spec.get('candidate_mode',False)
            type_key='obligation_type' if candidate_mode else 'condition_type'
            id_key=('register_id' if candidate_mode and all(c.get('register_id') for c in conditions) else 'candidate_id') if candidate_mode else 'condition_id'
            source_key='source_quotation' if candidate_mode else 'source_text'
            options=sorted({c.get(type_key) or 'UNCLASSIFIED' for c in conditions})
            selected=st.multiselect('Obligation types' if candidate_mode else 'Condition types',options,default=options)
            page_options=sorted({c['page_number'] for c in conditions})
            selected_pages=st.multiselect('Source pages',page_options,default=page_options,key=f'candidate_pages_{active_key}')
            verification_options=['SOURCE_VERIFIED','UNRESOLVED'] if candidate_mode else ['VERIFIED','UNVERIFIED']
            selected_verification=st.multiselect('Verification state',verification_options,default=verification_options,key=f'candidate_verification_{active_key}')
            def quote_ok(c): return c.get('state') == 'SOURCE_VERIFIED' if candidate_mode else c.get('quote_verified',False)
            def allowed_verification(c): return ('SOURCE_VERIFIED' if quote_ok(c) else 'UNRESOLVED') in selected_verification if candidate_mode else ('VERIFIED' if quote_ok(c) else 'UNVERIFIED') in selected_verification
            rows=[c for c in conditions if (c.get(type_key) or 'UNCLASSIFIED') in selected and c['page_number'] in selected_pages and allowed_verification(c)]
            st.dataframe([{'ID':c[id_key],'Model ID':c.get('candidate_id') if candidate_mode else c[id_key],'Page':c['page_number'],'Type':c.get(type_key) or 'UNCLASSIFIED','Source verified':quote_ok(c),'Review':decisions.get(c[id_key],{}).get('decision','UNREVIEWED'),'Source':c[source_key]} for c in rows],hide_index=True,key=f'candidate_register_{active_key}')
            if not rows:
                st.info('No records match the selected filters.')
            else:
                cid=st.selectbox('Candidate to review' if candidate_mode else 'Condition to review',[c[id_key] for c in rows])
                current=next(c for c in conditions if c[id_key]==cid)
                st.code(current[source_key]); st.caption(f"PDF page {current['page_number']}" + (f" · section: {current.get('section') or 'not stated'}" if candidate_mode else ''))
                if not quote_ok(current): st.warning('Source unresolved: confirmation requires separately audited manual source verification.')
                col1,col2=st.columns(2)
                if active_key==BELFAST_KEY and col1.button('Confirm selected'):
                    try: save_decision(ROOT,cid,'CONFIRMED','Streamlit reviewer'); st.rerun()
                    except ValueError as exc: st.error(str(exc))
                if active_key==BELFAST_KEY:
                    if col2.button('Reject selected'): save_decision(ROOT,cid,'REJECTED','Streamlit reviewer'); st.rerun()
                else:
                    if col1.button('Confirm selected (document scoped)',key='new_confirm'):
                        try: save_document_decision(ROOT,spec['hash'],current,'CONFIRMED','Streamlit reviewer',spec['version']); st.rerun()
                        except ValueError as exc: st.error(str(exc))
                    if col2.button('Reject selected',key='new_reject'): save_document_decision(ROOT,spec['hash'],current,'REJECTED','Streamlit reviewer'); st.rerun()
            st.subheader('Validation recovery queue')
            if active_key==BELFAST_KEY: st.dataframe([{'page':x['page'],'raw':__import__('json').dumps(x['raw']),'validation_error':x['validation_error']} for x in load_recovery(ROOT)],hide_index=True)
            else: st.info('Recovered records are displayed above; original raw and recovery audits remain document-scoped.')
            if coverage_data:
                st.subheader('Source-backed coverage gaps')
                if candidate_mode:
                    gaps=[x for x in coverage_data.get('pages',[]) if x.get('semantic_status') in {'PROCESSED_REVIEW_REQUIRED','FAILED','NOT_PROCESSED','PENDING'}]
                    if gaps: st.dataframe(gaps,hide_index=True,key=f'candidate_coverage_gaps_{active_key}')
                    else: st.info('Every physical page was processed; candidate discovery still requires human completeness review.')
                else:
                    gaps=[x for x in coverage_data['conditions'] if x['status'] != 'CAPTURED']
                    if gaps: st.dataframe(gaps,hide_index=True,key=f'condition_coverage_gaps_{active_key}')
                    else: st.success('No unresolved numbered source-condition coverage gaps.')
            if candidate_mode:
                st.subheader('Comprehensive source inventory')
                aggregate_payload=__import__('json').loads(spec['aggregate'].read_text())
                source_records=aggregate_payload.get('source_inventory',[])
                st.caption(f"{len(source_records)} source records linked to {len(conditions)} review-gated candidate obligations.")
                st.download_button('Download obligation register (CSV)',csv_bytes(conditions),'obligation_register.csv','text/csv')
                st.download_button('Download source inventory (CSV)',csv_bytes(source_records),'source_inventory.csv','text/csv')
                st.download_button('Download complete analysis (JSON)',export_json(aggregate_payload),'document_analysis.json','application/json')
                st.download_button('Download Excel workbook',excel_bytes(aggregate_payload),'document_analysis.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                source_types=sorted({record['record_type'] for record in source_records})
                source_pages=sorted({page for record in source_records for page in record['pages']})
                source_states=sorted({record['verification_status'] for record in source_records})
                sinv1,sinv2,sinv3=st.columns(3)
                selected_source_types=sinv1.multiselect('Source record categories',source_types,default=source_types,key=f'source_types_{active_key}')
                selected_source_pages=sinv2.multiselect('Inventory pages',source_pages,default=source_pages,key=f'source_pages_{active_key}')
                selected_source_states=sinv3.multiselect('Source verification states',source_states,default=source_states,key=f'source_states_{active_key}')
                filtered_sources=[record for record in source_records if record['record_type'] in selected_source_types and any(page in selected_source_pages for page in record['pages']) and record['verification_status'] in selected_source_states]
                table_rows=[record for record in filtered_sources if record['record_type']=='TABLE_ROW']
                if table_rows:
                    st.subheader('Numerical limits and table source context')
                    st.caption('Values are shown only where present in labelled source cells. Blank or merged applicability remains unresolved.')
                    st.dataframe([{'page':record['pages'][0],'table':record.get('table_reference'),'row':record.get('row_reference'),'applicability':record.get('applicability') or 'UNRESOLVED_CONTEXT','parameter':record.get('parameter'),'limit':record.get('limit_text'),'reference_period':record.get('reference_period'),'monitoring_frequency':record.get('monitoring_frequency'),'compliance_statistic':record.get('compliance_statistic'),'ambiguity':'; '.join(record.get('ambiguity',[]))} for record in table_rows],hide_index=True,key=f'table_context_{active_key}')
                if filtered_sources: st.dataframe(filtered_sources,hide_index=True,key=f'source_inventory_{active_key}')
        with st.expander('Diagnostics (audit metadata)', expanded=False):
            st.json({'document_key':active_key,'processing_version':spec['version'],'document_hash':spec.get('hash'),'coverage_available':bool(coverage_data),'records_loaded':len(conditions), 'runtime': runtime_metadata(), 'live_dispatch_preflight': live_runtime_preflight})
    with environment_tab:
        active_is_belfast=st.session_state.get('active_permit') in {None,BELFAST_KEY}
        st.header("Environmental Intelligence — Belfast Harbour" if active_is_belfast else "Environmental Intelligence")
        st.caption("Exploratory marine and atmospheric intelligence. Advisory thresholds are not permit limits and never generate compliance decisions.")
        if not active_is_belfast:
            st.warning('DATA REQUIRED: this permit has no confirmed operating coordinates or site-matched environmental cache. Belfast data are not applied to it.')
            st.info('Environmental charts are intentionally empty until the reviewer confirms a location and retrieves a site-matched cache.')
        environment=load_belfast(ROOT) if active_is_belfast else {
            'marine': {},
            'weather': {'missing': True, 'reason': 'no site-matched environmental cache'},
        }
        marine,weather=environment['marine'],environment['weather']
        st.sidebar.selectbox('Site', ['Belfast Harbour (cached scenario)', 'Custom supported location'], key='environment_site')
        selected_lat=st.sidebar.number_input('Latitude',value=54.6,min_value=-90.0,max_value=90.0,format='%.5f')
        selected_lon=st.sidebar.number_input('Longitude',value=-5.9,min_value=-180.0,max_value=180.0,format='%.5f')
        if st.sidebar.button('Retrieve selected location (advisory data)'):
            try:
                st.session_state.location_retrieval=retrieve_location(ROOT,selected_lat,selected_lon)
                st.sidebar.success('Location retrieval checkpointed; inspect source/grid details below.')
            except Exception as exc:
                st.sidebar.error(f'Location retrieval unavailable: {type(exc).__name__}: {exc}')
        if st.session_state.get('location_retrieval'):
            location_result=st.session_state.location_retrieval
            st.sidebar.caption(f"Selected-location forecast: {location_result['weather']['forecast_hours']} hours, {location_result['weather']['model']}")
            st.sidebar.dataframe([{'source':name,'status':'FAILED' if 'error' in value else 'READY','representativeness':value.get('grid',{}).get('representativeness'),'distance_km':value.get('grid',{}).get('distance_km')} for name,value in location_result['marine'].items()],hide_index=True)
        st.sidebar.radio('Time display', ['UTC', 'Local (Europe/London)'], key='environment_time')
        if weather.get('missing'):
            st.warning(f"Atmospheric cache unavailable: {weather['reason']}")
        else:
            st.success(f"Cached forecast: {weather['provenance_label']} · {weather['forecast_hours']} hourly periods · {weather['cache_age_hours']:.1f}h old")
        forecast_dates=[x[:10] for x in weather.get('hourly',{}).get('time',[])]
        if forecast_dates:
            period=st.sidebar.date_input('Analysis period',value=(__import__('datetime').date.fromisoformat(forecast_dates[0]),__import__('datetime').date.fromisoformat(forecast_dates[-1])))
            period_start,period_end=(period if isinstance(period,tuple) and len(period)==2 else (period,period))
        else:
            period_start=period_end=None
        import plotly.graph_objects as go
        def chart(title, series):
            figure=go.Figure()
            for name,times,values,unit in series:
                points=[(time,value) for time,value in zip(times,values) if period_start is None or period_start.isoformat() <= time[:10] <= period_end.isoformat()]
                if points: figure.add_scatter(x=[x[0] for x in points],y=[x[1] for x in points],name=f'{name} ({unit or "unit unavailable"})')
            if not figure.data:
                st.info(f'{title}: no site-matched data are available.')
                return
            figure.update_layout(title=title, xaxis_title='UTC time', hovermode='x unified', height=320)
            st.plotly_chart(figure,width='stretch')
        wave_t,wave_v,wave_u=marine_series(marine.get('waves',{}),'VHM0')
        current_t,current_v,current_u=marine_series(marine.get('currents',{}),'current_speed')
        sst_t,sst_v,sst_u=marine_series(marine.get('sst',{}),'thetao')
        st.subheader('Marine conditions')
        chart('Waves and currents', [('Significant wave height',wave_t,wave_v,wave_u),('Current speed',current_t,current_v,current_u)])
        chart('Sea surface temperature', [('SST',sst_t,sst_v,sst_u)])
        availability=[]
        for name,payload in marine.items():
            availability.append({'source':name,'observations':len(payload.get('observations',[])),
                                 'representativeness':payload.get('grid',{}).get('representativeness','MISSING'),
                                 'distance_km':payload.get('grid',{}).get('distance_km'),
                                 'fresh':payload.get('cache_fresh'), 'limitation':'masked/no valid coastal cell' if not payload.get('observations') else ''})
        st.dataframe(availability,hide_index=True)
        st.subheader('Atmospheric forecast')
        weather_names=['wind_speed_10m','wind_direction_10m','wind_gusts_10m','precipitation','temperature_2m','pressure_msl','relative_humidity_2m','cloud_cover','visibility']
        atmospheric=[]
        for name in weather_names:
            times,values,unit=weather_series(weather,name)
            atmospheric.append((name,times,values,unit))
        chart('Wind speed and gusts', [x for x in atmospheric if x[0] in {'wind_speed_10m','wind_gusts_10m'}])
        visibility_item=next(x for x in atmospheric if x[0]=='visibility')
        if visibility_item[3] in {None,'undefined'}:
            st.info('Visibility was requested but the selected provider/model did not return a usable unit; it is treated as unavailable.')
        chart('Precipitation and visibility', [x for x in atmospheric if x[0]=='precipitation' or (x[0]=='visibility' and x[3] not in {None,'undefined'})])
        chart('Air temperature, pressure, humidity and cloud cover', [x for x in atmospheric if x[0] in {'temperature_2m','pressure_msl','relative_humidity_2m','cloud_cover'}])
        st.subheader('Descriptive analytics and advisory windows')
        wind=weather_series(weather,'wind_speed_10m')[1]; gusts=weather_series(weather,'wind_gusts_10m')[1]; rain=weather_series(weather,'precipitation')[1]
        c1,c2,c3,c4=st.columns(4)
        c1.metric('Mean wind', f"{summary(wind)['mean']:.1f} km/h" if summary(wind)['mean'] is not None else 'missing')
        c2.metric('Maximum gust', f"{summary(gusts)['maximum']:.1f} km/h" if summary(gusts)['maximum'] is not None else 'missing')
        c3.metric('Peak current', f"{summary(current_v)['maximum']:.3f} m/s" if summary(current_v)['maximum'] is not None else 'missing')
        c4.metric('Rainfall accumulation', f"{rainfall_total(rain):.1f} mm")
        selected_variables=st.multiselect('Advisory variables', ['wave_height','wind_speed','wind_gust','current_speed'], default=['wave_height','wind_speed','wind_gust','current_speed'])
        thresholds={'wave_height':st.number_input('Advisory wave-height maximum (m)',value=1.5,min_value=0.0),
                    'wind_speed':st.number_input('Advisory wind maximum (km/h)',value=30.0,min_value=0.0),
                    'wind_gust':st.number_input('Advisory wind-gust maximum (km/h)',value=45.0,min_value=0.0),
                    'current_speed':st.number_input('Advisory current-speed maximum (m/s)',value=1.0,min_value=0.0)}
        minimum_duration=st.number_input('Minimum consecutive advisory duration (hours)',value=2,min_value=1,step=1)
        st.caption(f"Wind exceeds its advisory threshold for {exceedance_hours(wind,thresholds['wind_speed']):.0f} hourly samples. These controls are exploratory, not permit limits.")
        wind_t,wind_v,_=weather_series(weather,'wind_speed_10m'); gust_t,gust_v,_=weather_series(weather,'wind_gusts_10m')
        series={'wave_height':(wave_t,wave_v,'mean'),'wind_speed':(wind_t,wind_v,'mean'),'wind_gust':(gust_t,gust_v,'max'),'current_speed':(current_t,current_v,'max')}
        active={name:series[name] for name in selected_variables}
        grid,aligned=shared_hourly_grid(active) if active else ([],{})
        quality={name:(weather.get('cache_fresh',False) if name.startswith('wind') else marine.get('waves' if name=='wave_height' else 'currents',{}).get('cache_fresh',False) and marine.get('waves' if name=='wave_height' else 'currents',{}).get('grid',{}).get('representativeness') in {'GOOD','MODERATE'}) for name in active}
        if grid:
            windows=advisory_intervals(grid,aligned,{name:thresholds[name] for name in active},quality,int(minimum_duration))
            st.caption('Synchronized hourly UTC timeline. Current speed uses the maximum of raw 15-minute values per hour; wave and weather values use hourly source values/means without interpolation.')
            st.dataframe(windows,hide_index=True)
            st.dataframe([{'variable':name,'coverage_percent':round(coverage_percent(values),1),'quality_usable':quality[name]} for name,values in aligned.items()],hide_index=True)
        else:
            st.warning('No shared advisory timeline is available. Missing evidence is not favourable evidence.')
        st.subheader('Permit-to-evidence readiness')
        st.caption('Environmental matches are never promoted to deciding evidence automatically.')
        st.dataframe(evidence_readiness(ROOT) if active_is_belfast else [],hide_index=True)
    with decision_tab:
        st.header('Permit Decision Intelligence')
        st.caption('Evidence-safe deterministic rule capability. This panel does not authorize operations.')
        overview=readiness(ROOT)
        st.subheader(f"Belfast Harbour licence {overview['document_id']}")
        m1,m2,m3,m4,m5=st.columns(5)
        m1.metric('Confirmed executable rules',overview['confirmed_executable'])
        m2.metric('Awaiting review',overview['awaiting_review'])
        m3.metric('External evidence required',overview['external_evidence'])
        m4.metric('Manual/authority evidence',overview['manual_evidence'])
        m5.metric('Unsupported/unmapped',overview['unsupported'])
        st.warning('REAL BELFAST STATUS: review-pending. No decision timeline is permission to operate; unreviewed and unresolved obligations remain in the readiness assessment.')
        status_filter=st.multiselect('Filter readiness', ['UNREVIEWED','CONFIRMED','EXTERNAL_DATA_REQUIRED','MANUAL_INPUT_REQUIRED','NOT_EVALUABLE'],default=['UNREVIEWED','CONFIRMED','EXTERNAL_DATA_REQUIRED','MANUAL_INPUT_REQUIRED','NOT_EVALUABLE'])
        filtered=[row for row in overview['conditions'] if row['review_status'] in status_filter or row['automation_status'] in status_filter]
        st.dataframe([{key:value for key,value in row.items() if key!='source_text'} for row in filtered],hide_index=True)
        st.subheader('Administrative and approval obligations')
        admin=[row for row in overview['conditions'] if row['administrative']]
        st.dataframe([{key:value for key,value in row.items() if key!='source_text'} for row in admin],hide_index=True)
        if filtered:
            detail_id=st.selectbox('Inspect requirement source and evidence', [row['condition_id'] for row in filtered],key='decision_condition')
            detail=next(row for row in overview['conditions'] if row['condition_id']==detail_id)
            st.code(detail['source_text']); st.caption(f"PDF page {detail['page']} · required source: {detail['required_source']} · action: {detail['required_action']}")
            st.write({'evidence_requirements':detail['evidence_requirements'],'review_status':detail['review_status'],'quote_verified':detail['quote_verified'],'automation_status':detail['automation_status']})
        st.subheader('Evaluation authorization')
        if overview['confirmed_executable']:
            st.info('Confirmed rules would be evaluated only after deciding-evidence authorization, freshness and completeness checks. No real deciding evidence is configured for this licence.')
        else:
            st.info('No confirmed, quote-verified Belfast conditions are eligible for evaluation. This is UNKNOWN/readiness-pending, not permission to operate.')
        st.subheader('ENGINE DEMONSTRATION — NOT AN OPERATIONAL AUTHORIZATION')
        st.error('All values below are isolated synthetic test fixtures. They are not Belfast environmental evidence and are never persisted.')
        if st.button('Run isolated engine demonstration'):
            st.dataframe(demonstration(),hide_index=True)
        st.subheader('Status vocabulary')
        st.write({'implemented_and_tested':['YES','STOP','RESUME','UNKNOWN'],'not_emitted_by_current_engine':['NO','WARN'],'meaning':'NO and WARN have no Stage 4A transition semantics and are not claimed as supported outcomes.'})
        st.caption('Use Permit Operations to review and confirm source-verified conditions. Decision Intelligence never changes a review decision.')
    with contract_tab:
        st.header('Marine Contract Weather Intelligence')
        st.warning('FORECAST INTELLIGENCE ONLY — NOT LEGAL ADVICE. No output determines liability, compensation, extension of time, or contractual entitlement.')
        upload=st.file_uploader('Upload marine/offshore contract PDF',type='pdf',key='contract_upload')
        left,right=st.columns(2)
        if left.button('Load labelled demonstration contract'):
            text=(ROOT/'data/contracts/demo_weather_contract.txt').read_text(encoding='utf-8')
            content=text.encode(); doc_id=contract_document_id(content); clauses=extract_weather_clauses(doc_id,[PdfPage(1,text)])
            save_clauses(ROOT,clauses); st.session_state.contract_doc_id=doc_id
        if upload and right.button('Extract weather clauses from upload'):
            content=upload.getvalue(); doc_id=contract_document_id(content); parsed=parse_pdf_bytes(content,doc_id)
            if parsed.needs_ocr: st.warning('PDF text layer is weak; clauses are retained for review and no inference is made.')
            clauses=extract_weather_clauses(doc_id,parsed.pages); save_clauses(ROOT,clauses); st.session_state.contract_doc_id=doc_id
        doc_id=st.session_state.get('contract_doc_id')
        if not doc_id:
            st.info('Upload a PDF or load the clearly labelled demonstration contract. No contract analysis is active yet.')
        else:
            clauses=load_clauses(ROOT,doc_id); review=contract_reviews(ROOT,doc_id)
            st.success(f'Contract {doc_id}: {len(clauses)} weather-related clauses retained for human review.')
            rows=[]
            for clause in clauses:
                state=review.get(clause.clause_id,{}).get('state','UNREVIEWED')
                rows.append({'clause':clause.clause_id,'page':clause.page_number,'variable':clause.environmental_variable,'operator':clause.operator,'threshold':clause.threshold,'unit':clause.unit,'continuous_hours':clause.continuous_hours,'quote_verified':clause.quote_verified,'review':state,'ambiguity':clause.ambiguity,'consequence':clause.consequence,'risk_allocation':clause.risk_allocation.value})
            st.dataframe(rows,hide_index=True)
            choice=st.selectbox('Inspect/review contract clause',[c.clause_id for c in clauses],key='contract_clause')
            clause=next(c for c in clauses if c.clause_id==choice)
            st.code(clause.source_text); st.caption(f'Page {clause.page_number} · quote verified: {clause.quote_verified}')
            if clause.ambiguity: st.warning(clause.ambiguity)
            a,b=st.columns(2)
            if a.button('Confirm contract interpretation'):
                if clause.quote_verified and not clause.ambiguity: save_contract_review(ROOT,doc_id,choice,ContractReviewState.CONFIRMED,'Streamlit contract reviewer'); st.rerun()
                else: st.error('Quote verification and complete structured fields are required before confirmation.')
            if b.button('Reject contract interpretation'): save_contract_review(ROOT,doc_id,choice,ContractReviewState.REJECTED,'Streamlit contract reviewer'); st.rerun()
            st.subheader('Forecast-based contract weather analysis')
            result=analyse_confirmed(ROOT,clauses,review)
            if result['status']=='UNKNOWN': st.info(result['reason'])
            else:
                st.caption(result['legal_notice']); st.dataframe(result['windows'],hide_index=True)
                st.write({'forecast_hours':result['forecast_hours'],'coverage_percent':result['coverage'],'confirmed_clause_count':result['clauses']})
                if result['exposure']: st.subheader('Potentially relevant contractual clauses — human assessment required'); st.dataframe(result['exposure'],hide_index=True)
            st.subheader('Historical Seasonal Weather Risk')
            st.caption('HISTORICAL SEASONAL WEATHER RISK — NOT A FORECAST. Historical weather patterns do not establish future downtime, legal liability, or compensation.')
            hcol1,hcol2=st.columns(2)
            historical_lat=hcol1.number_input('Project latitude',value=54.6,min_value=-90.0,max_value=90.0,format='%.5f',key='contract_historical_lat')
            historical_lon=hcol2.number_input('Project longitude',value=-5.9,min_value=-180.0,max_value=180.0,format='%.5f',key='contract_historical_lon')
            project_period=st.date_input('Requested project period',value=(date(2027,4,9),date(2027,4,11)),key='contract_project_period')
            years=st.number_input('Equivalent previous years',min_value=1,max_value=5,value=3,key='contract_historical_years')
            active=[c for c in clauses if review.get(c.clause_id,{}).get('state')=='CONFIRMED' and c.quote_verified and c.environmental_variable and c.threshold is not None and c.unit]
            if not active or not isinstance(project_period,tuple) or len(project_period)!=2:
                st.info('REQUIRES INPUT: confirm supported contract thresholds and specify a complete project period before selecting forecast or historical mode.')
            else:
                environment=load_belfast(ROOT); marine,weather=environment['marine'],environment['weather']; start_dt=datetime.combine(project_period[0],datetime.min.time(),tzinfo=timezone.utc); end_dt=datetime.combine(project_period[1],datetime.max.time(),tzinfo=timezone.utc)
                forecast_coverage={}
                for c in active:
                    if c.environmental_variable=='wave': times=marine_series(marine.get('waves',{}),'VHM0')[0]
                    elif c.environmental_variable=='current_speed': times=marine_series(marine.get('currents',{}),'current_speed')[0]
                    else: times=weather_series(weather,{'wind_speed':'wind_speed_10m','wind_gust':'wind_gusts_10m'}.get(c.environmental_variable,''))[0]
                    if times: forecast_coverage[c.environmental_variable]=(parse_utc(times[0]),parse_utc(times[-1]))
                mode=select_mode(start_dt,end_dt,[c.environmental_variable for c in active],forecast_coverage,True)
                st.write({'analysis_mode':mode,'required_variables':[c.environmental_variable for c in active]})
                if mode=='HISTORICAL_SEASONAL_WEATHER_RISK':
                    equivalent=equivalent_periods(project_period[0],project_period[1],int(years))
                    # The offline Belfast demonstration is intentionally limited to the
                    # cache that was actually retrieved.  It must never reuse an April
                    # sample as if it described a different requested project period.
                    demo_period=(date(2027,4,9),date(2027,4,11))
                    is_belfast_demo=abs(historical_lat-54.6)<0.00001 and abs(historical_lon+5.9)<0.00001
                    if tuple(project_period) != demo_period or not is_belfast_demo:
                        st.warning('HISTORICAL DATA REQUIRED: no cached equivalent periods match this requested location/date range. No historical risk result has been calculated.')
                        st.dataframe([{'sample_year':year,'equivalent_start':start.isoformat(),'equivalent_end':end.isoformat(),'status':'NOT CACHED'} for year,start,end in equivalent],hide_index=True)
                    else:
                        thresholds={c.environmental_variable:c.threshold for c in active}
                        historical=analyse_history(ROOT,[year for year,_,_ in equivalent],thresholds)
                        st.warning(historical['result']['caveats'][0]); st.dataframe(historical['result']['coverage'],hide_index=True)
                        st.dataframe([{'year':row['year'],'coverage_complete':row['coverage_complete'],'variables':', '.join(row['variables'])} for row in historical['years']],hide_index=True)
                        summary_rows=[]
                        for row in historical['years']:
                            for variable,detail in row['variables'].items():
                                stats=detail['statistics']; windows=detail['windows']
                                summary_rows.append({'year':row['year'],'variable':variable,'mean':stats['mean'],'p50':stats['p50'],'p90':stats['p90'],'maximum':stats['maximum'],'exceedance_hours':stats['exceedance_hours'],'exceedance_pct':stats['exceedance_pct'],'workable_windows':windows['workable_count'],'longest_workable_hours':windows['longest_workable_hours'],'weather_constrained_hours':windows['weather_constrained_hours'],'unknown_hours':windows['unknown_hours']})
                        st.dataframe(summary_rows,hide_index=True)
                        if summary_rows:
                            st.bar_chart({f"{row['year']} {row['variable']}":row['maximum'] for row in summary_rows})
                        st.caption('Incomplete/masked variables are UNKNOWN and excluded from workable or weather-constrained totals.')


if __name__ == "__main__":
    main()
