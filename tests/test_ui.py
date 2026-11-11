import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest


class UITests(unittest.TestCase):
    def test_demo_evidence_and_audit_gate(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'src/ui.py')).run(timeout=30)
        self.assertFalse(app.exception)
        next(b for b in app.button if b.label == 'Load fleet sample').click().run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe), 1)
        next(b for b in app.button if b.label == 'Find evidence').click().run(timeout=30)
        self.assertFalse(app.exception)
        self.assertTrue(any('Temperature Control' in x.value for x in app.markdown))
        self.assertEqual(len(app.dataframe), 1)
        next(b for b in app.button if b.label == 'Check SOP thresholds').click().run()
        self.assertTrue(any('Confirm fresh-perishable' in x.value for x in app.info))
        app.checkbox[0].check()
        next(b for b in app.button if b.label == 'Check SOP thresholds').click().run()
        self.assertTrue(any('within' in x.value for x in app.markdown))
        app.sidebar.radio[0].set_value('Assistant').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        app.sidebar.radio[0].set_value('Audit').run()
        next(b for b in app.button if b.label == 'Load events').click().run()
        self.assertTrue(app.error)
        self.assertFalse(app.exception)
