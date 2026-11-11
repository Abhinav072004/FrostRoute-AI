import hmac
import json
import os
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st
from langchain_core.messages import HumanMessage
from src.agent_tools import query_telemetry_db, search_compliance_sop
from src.guardrails import validate_input
from src.orchestrator import get_agent
from src.storage import audit, read_audit

st.set_page_config(page_title='FrostRoute AI', page_icon='🧊', layout='wide')
st.title('🧊 FrostRoute AI')
backend = os.getenv('DATA_BACKEND', 'demo')
provider = os.getenv('AGENT_LLM', os.getenv('Agent_llm', 'DEMO')).upper()
st.caption(f'Data: {backend} · Retrieval: {os.getenv("RAG_BACKEND", "local")} · Assistant: {provider}')
st.warning('The bundled data is historical sample telemetry, with no shipment IDs or cargo types. Verify current conditions before operational action.')
if 'thread_id' not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.messages = []
if st.sidebar.button('New conversation'):
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.messages = []
    for key in ('fleet_result', 'policy_result', 'compliance_result'):
        st.session_state.pop(key, None)
    st.rerun()
page = st.sidebar.radio('Workspace', ['Evidence explorer', 'Assistant', 'Audit'])

if page == 'Evidence explorer':
    st.subheader('Fleet observations')
    st.caption('Latest ten observations in the configured dataset; these are not identified shipments.')
    if st.button('Load fleet sample'):
        query = 'SELECT * FROM FDE_VIEWS.VW_ACTIVE_FLEET ORDER BY Timestamp DESC'
        result = json.loads(query_telemetry_db.invoke({'sql_query': query}))
        audit(st.session_state.thread_id, 'fleet_preview', result)
        st.session_state.fleet_result = result
    if 'fleet_result' in st.session_state:
        result = st.session_state.fleet_result
        if 'error' in result:
            st.error(result['error'])
        else:
            st.dataframe(result['rows'], width='stretch')
    st.subheader('Check a confirmed cargo observation')
    from src.compliance import evaluate
    with st.form('compliance'):
        confirmed = st.checkbox('I confirm this observation is for fresh-perishable cargo')
        temperature = st.number_input('Observed cargo temperature (°C)', value=4.0)
        assess = st.form_submit_button('Check SOP thresholds')
    if assess:
        result = evaluate(temperature, 'fresh_perishables' if confirmed else 'unknown')
        audit(st.session_state.thread_id, 'compliance_check', result)
        st.session_state.compliance_result = result
    if 'compliance_result' in st.session_state:
        result = st.session_state.compliance_result
        if result['status'] != 'evaluated':
            st.info(result['reason'])
        else:
            for finding in result['findings']:
                st.write(finding)
            for action in result['recommendations']:
                st.write(action)
            st.caption(result['warning'])
            st.caption('Sources: ' + '; '.join(result['citations']))
    st.subheader('Search operating procedures')
    with st.form('sop_search'):
        question = st.text_input('Policy question', value='What are the temperature rules for fresh perishables?', max_chars=4000)
        submitted = st.form_submit_button('Find evidence')
    if submitted:
        result = json.loads(search_compliance_sop.invoke({'query': question}))
        audit(st.session_state.thread_id, 'policy_search', result)
        st.session_state.policy_result = result
    if 'policy_result' in st.session_state:
        result = st.session_state.policy_result
        if 'error' in result:
            st.error(result['error'])
        elif not result['evidence']:
            st.info('No matching evidence. Ask for a verified policy; do not infer a rule.')
        else:
            st.caption('Retrieved passages are evidence candidates, not a generated recommendation.')
            for item in result['evidence']:
                st.markdown(f'**{item["source"]} — {item["section"]}**')
                st.text(item['text'])
elif page == 'Assistant':
    if provider == 'DEMO':
        st.info('Use Evidence explorer without credentials. To enable conversational tool calling, configure AGENT_LLM and the provider in .env, then restart.')
    else:
        for message in st.session_state.messages:
            with st.chat_message(message['role']):
                st.markdown(message['content'])
        if prompt := st.chat_input('Ask about fleet evidence or SOP rules', max_chars=4000):
            try:
                prompt = validate_input(prompt)
                audit(st.session_state.thread_id, 'user', {'content': prompt})
                st.session_state.messages.append({'role': 'user', 'content': prompt})
                with st.chat_message('user'):
                    st.markdown(prompt)
                with st.chat_message('assistant'):
                    with st.spinner('Checking evidence…'):
                        answer = get_agent().invoke({'messages': [HumanMessage(content=prompt)]},
                            config={'configurable': {'thread_id': st.session_state.thread_id}, 'recursion_limit': 12})
                        response = answer['messages'][-1].content
                        audit(st.session_state.thread_id, 'assistant', {'content': response})
                    st.markdown(response)
                st.session_state.messages.append({'role': 'assistant', 'content': response})
            except Exception:
                st.error('The request could not be completed. Check provider configuration or start a new conversation if the execution limit was reached. No operational conclusion is available.')
else:
    st.subheader('Local audit events')
    st.caption('Durable application events, limited to the latest 200. This local store is not tamper-proof. Protect the host and configure retention before deployment.')
    password = st.text_input('Audit viewer password', type='password')
    expected = os.getenv('AUDIT_VIEW_PASSWORD', '')
    if st.button('Load events'):
        if expected and hmac.compare_digest(password, expected):
            st.dataframe(read_audit(), width='stretch')
        else:
            st.error('Audit access is disabled or credentials are invalid.')
