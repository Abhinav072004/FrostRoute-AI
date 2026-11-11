import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from src.guardrails import safe_sql, coordinates, validate_input
from src.retrieval import search, load_chunks
from src.agent_tools import query_telemetry_db, search_compliance_sop, fetch_corridor_conditions


class SQLTests(unittest.TestCase):
    def test_valid_query_caps_rows(self):
        tree = safe_sql('SELECT TOP 999 Latitude FROM FDE_VIEWS.VW_ACTIVE_FLEET WHERE Latitude > 30 ORDER BY Timestamp DESC')
        self.assertIn('TOP 10', tree.sql(dialect='tsql'))

    def test_blocks_mutations_exfiltration_and_obfuscation(self):
        attacks = [
            'SELECT * FROM FDE_VIEWS.VW_ACTIVE_FLEET; DROP TABLE x',
            'SELECT * INTO stolen FROM FDE_VIEWS.VW_ACTIVE_FLEET',
            'SELECT * FROM dbo.TBL_SC_FLEET_HIST_RAW',
            'SELECT * FROM other.FDE_VIEWS.VW_ACTIVE_FLEET',
            'SELECT * FROM FDE_VIEWS.VW_ACTIVE_FLEET UNION SELECT * FROM sys.tables',
            'SELECT * FROM FDE_VIEWS.VW_ACTIVE_FLEET f JOIN sys.tables t ON 1=1',
            'SELECT (SELECT password FROM users) FROM FDE_VIEWS.VW_ACTIVE_FLEET',
            'SELECT * FROM OPENROWSET(\'x\',\'y\',\'z\')',
            'SELECT secret FROM FDE_VIEWS.VW_ACTIVE_FLEET',
            'SELECT SLEEP(100) FROM FDE_VIEWS.VW_ACTIVE_FLEET',
            'DELETE FROM FDE_VIEWS.VW_ACTIVE_FLEET',
            'SELECT * FROM FDE_VIEWS.VW_ACTIVE_FLEET OPTION (QUERYTRACEON 460)',
            'WITH x AS (SELECT * FROM sys.tables) SELECT * FROM x',
        ]
        for attack in attacks:
            with self.subTest(attack=attack), self.assertRaises(Exception):
                safe_sql(attack)

    @patch.dict(os.environ, {'DATA_BACKEND': 'demo'})
    def test_real_csv_demo_query(self):
        data = json.loads(query_telemetry_db.invoke({'sql_query': 'SELECT * FROM FDE_VIEWS.VW_ACTIVE_FLEET ORDER BY Timestamp DESC'}))
        self.assertNotIn('error', data)
        self.assertEqual(len(data['rows']), 10)
        self.assertTrue(data['historical_sample'])
        self.assertIn('Timestamp', data['rows'][0])

    def test_error_does_not_echo_secrets(self):
        result = query_telemetry_db.invoke({'sql_query': 'SELECT password_secret FROM sys.users'})
        self.assertNotIn('password_secret', result)


class RetrievalTests(unittest.TestCase):
    def test_policy_questions_return_relevant_citations(self):
        for query, section in [('fresh perishables temperature', 'Temperature Control'),
                               ('port congestion diversion', 'Route Congestion'),
                               ('High Risk delay escalate', 'Risk Classification')]:
            with self.subTest(query=query):
                result = search(query)
                self.assertIn(section, result[0]['section'])
                self.assertEqual(result[0]['source'], 'Cold_Chain_Incident_SOP_v2.md')

    def test_no_evidence(self):
        self.assertEqual(search('quantum cryptocurrency zzzzz'), [])

    def test_empty_and_long_input(self):
        for value in ['', ' ' , 'x' * 4001]:
            with self.assertRaises(ValueError):
                validate_input(value)

    @patch.dict(os.environ, {'RAG_BACKEND': 'local'})
    def test_local_needs_no_vector_service(self):
        result = json.loads(search_compliance_sop.invoke({'query': 'fresh perishables temperature'}))
        self.assertEqual(result['backend'], 'local')
        self.assertIn('4.0', result['evidence'][0]['text'])


class WeatherTests(unittest.TestCase):
    def test_invalid_coordinates(self):
        for lat, lon in [(91, 0), (0, 181), (math.nan, 0), (0, math.inf)]:
            with self.assertRaises(ValueError):
                coordinates(lat, lon)
        with patch('src.agent_tools.requests.get') as get:
            result = json.loads(fetch_corridor_conditions.invoke({'latitude': 91, 'longitude': 0}))
            self.assertIn('error', result)
            get.assert_not_called()

    @patch('src.agent_tools.requests.get')
    def test_no_invented_congestion(self, get):
        response = Mock()
        response.json.return_value = {'current': {'time': '2026-11-11T12:00', 'temperature_2m': 20, 'wind_speed_10m': 30}, 'current_units': {'wind_speed_10m': 'km/h'}}
        get.return_value = response
        result = json.loads(fetch_corridor_conditions.invoke({'latitude': 33.8, 'longitude': -118.1}))
        self.assertEqual(result['traffic_congestion'], 'unknown')
        self.assertIn('observed_at_utc', result)

    @patch('src.agent_tools.requests.get', side_effect=TimeoutError)
    def test_outage_is_not_all_clear(self, get):
        result = json.loads(fetch_corridor_conditions.invoke({'latitude': 33.8, 'longitude': -118.1}))
        self.assertIn('error', result)


class ComplianceTests(unittest.TestCase):
    def test_boundaries_and_missing_eta(self):
        from src.compliance import evaluate
        for temperature in [0, 4]:
            result = evaluate(temperature, 'fresh_perishables')
            self.assertIn('within', result['findings'][0])
        critical = evaluate(4.01, 'fresh_perishables')
        self.assertTrue(any('Verify ETA' in a for a in critical['recommendations']))
        self.assertFalse(any('arrange diversion' in a for a in critical['recommendations']))
        self.assertTrue(any('arrange diversion' in a for a in evaluate(5, 'fresh_perishables', eta_delay_hours=1.01)['recommendations']))
        self.assertFalse(any('arrange diversion' in a for a in evaluate(5, 'fresh_perishables', eta_delay_hours=1)['recommendations']))
        self.assertIn('Below', evaluate(-1, 'fresh_perishables')['findings'][0])

    def test_cargo_unknown_and_escalation(self):
        from src.compliance import evaluate
        self.assertEqual(evaluate(10, 'unknown')['status'], 'unknown')
        self.assertFalse(any('Tier 2' in f for f in evaluate(2, 'fresh_perishables', 'High Risk', .65)['findings']))
        self.assertTrue(any('Tier 2' in f for f in evaluate(2, 'fresh_perishables', 'High Risk', .66)['findings']))
        with self.assertRaises(ValueError):
            evaluate(2, 'fresh_perishables', delay_probability=2)

    def test_policy_change_requires_review(self):
        from src.compliance import evaluate
        with patch('src.compliance.POLICY_SHA256', 'different'):
            self.assertEqual(evaluate(5, 'fresh_perishables')['status'], 'policy_review_required')


class AgentTests(unittest.TestCase):
    @patch.dict(os.environ, {'AGENT_LLM': 'OPENAI', 'RAG_BACKEND': 'local'})
    def test_system_policy_tool_execution_and_session_isolation(self):
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
        from src.orchestrator import get_agent
        invocations = []

        class FakeModel:
            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                invocations.append(messages)
                if isinstance(messages[-1], ToolMessage):
                    return AIMessage(content='Fresh perishables: 0–4 C. Source: Cold_Chain_Incident_SOP_v2.md, section 1.')
                return AIMessage(content='', tool_calls=[{'name': 'search_compliance_sop',
                    'args': {'query': 'fresh perishables temperature'}, 'id': 'test-call', 'type': 'tool_call'}])

        get_agent.cache_clear()
        try:
            with patch('langchain_openai.ChatOpenAI', return_value=FakeModel()), patch('src.orchestrator.audit') as audit:
                graph = get_agent()
                for session, question in [('session-a', 'Question A'), ('session-b', 'Question B')]:
                    result = graph.invoke({'messages': [HumanMessage(content=question)]},
                        config={'configurable': {'thread_id': session}, 'recursion_limit': 12})
                    self.assertIn('0–4', result['messages'][-1].content)
                self.assertEqual(audit.call_count, 4)
                self.assertTrue(all(isinstance(messages[0], SystemMessage) for messages in invocations))
                self.assertIn('untrusted', invocations[0][0].content)
                self.assertFalse(any(m.content == 'Question A' for m in invocations[2]))
        finally:
            get_agent.cache_clear()


if __name__ == '__main__':
    unittest.main()
