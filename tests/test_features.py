"""
tests/test_features.py
Comprehensive test suite verifying CareerAgent AI premium features:
- Auto-Apply Browser form mappings
- Candidate CRM RAG retrieval & TF-IDF search fallback
- Proactive crawler scheduler & alert logging
- Voice coaching anxiety detection logic
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
import unittest
from unittest.mock import patch, MagicMock, mock_open

# Import agents/utils modules to test
from utils.rag_manager import chunk_text, cosine_similarity, tf_idf_fallback_search
from utils.browser_apply import analyze_form_with_llm
from utils.cron_agent import search_all_sources
from interview_module.engine import InterviewEngine

class TestCareerAgentFeatures(unittest.TestCase):

    def setUp(self):
        self.sample_resume = (
            "Venkat Applicant is a Software Engineer with 5 years of experience in Python, "
            "Kubernetes, and Machine Learning. He worked at TechCorp building RAG pipelines "
            "and deploying microservices on AWS using Docker."
        )
        self.sample_query = "What is Venkat's experience with Kubernetes?"

    # ── 1. Candidate CRM RAG Tests ──────────────────────────────────────────
    def test_text_chunking(self):
        """Verify resume text is chunked correctly with appropriate sizes and overlaps."""
        text = "word1 " * 100
        chunks = chunk_text(text, chunk_size=30, overlap=10)
        self.assertTrue(len(chunks) > 1)
        # Verify first chunk contains ~30 words
        self.assertEqual(len(chunks[0].split()), 30)

    def test_cosine_similarity(self):
        """Verify vector similarity calculations."""
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        # Identical vectors should have similarity near 1.0
        self.assertAlmostEqual(cosine_similarity(v1, v2), 1.0, places=4)
        
        v3 = [0.0, 1.0, 0.0]
        # Orthogonal vectors should have similarity near 0.0
        self.assertAlmostEqual(cosine_similarity(v1, v3), 0.0, places=4)

    def test_tf_idf_fallback_search(self):
        """Verify fallback keyword matcher when embedding API keys are not provided."""
        records = [
            {"id": 0, "text": "I worked on Kubernetes pipelines and Docker deployment."},
            {"id": 1, "text": "I have experience with retail sales and marketing."}
        ]
        # Querying "Kubernetes Docker" should rank project 0 highest
        results = tf_idf_fallback_search("Kubernetes Docker", records, limit=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], 0)
        self.assertIn("Kubernetes", results[0]["text"])

    # ── 2. Auto-Apply Browser Form Tests ────────────────────────────────────
    @patch("litellm.completion")
    def test_form_llm_selector_generation(self, mock_completion):
        """Test that LLM form helper returns correct mappings from input JSON specifications."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"input[name=\'first_name\']": "first_name"}'))
        ]
        mock_completion.return_value = mock_response

        snippet = [{"tag": "input", "name": "first_name", "selector": "input[name='first_name']"}]
        mappings = analyze_form_with_llm(json.dumps(snippet))
        
        self.assertIn("input[name='first_name']", mappings)
        self.assertEqual(mappings["input[name='first_name']"], "first_name")

    # ── 3. Autonomous Crawler Tests ──────────────────────────────────────────
    @patch("utils.cron_agent.fetch_adzuna")
    @patch("utils.cron_agent.fetch_remotive")
    @patch("utils.cron_agent.fetch_usajobs")
    def test_search_all_sources_consolidation(self, mock_usajobs, mock_remotive, mock_adzuna):
        """Test unified crawler consolidates jobs from USAJobs and Remotive correctly."""
        mock_adzuna.return_value = []
        mock_remotive.return_value = [
            {"MatchedObjectDescriptor": {"PositionTitle": "Python Dev", "OrganizationName": "A", "_source": "Remotive"}}
        ]
        mock_usajobs.return_value = [
            {"MatchedObjectDescriptor": {"PositionTitle": "Data Scientist", "OrganizationName": "B"}}
        ]
        
        jobs = search_all_sources("Python", limit=2)
        self.assertEqual(len(jobs), 2)
        titles = [j["MatchedObjectDescriptor"]["PositionTitle"] for j in jobs]
        self.assertIn("Python Dev", titles)
        self.assertIn("Data Scientist", titles)

    # ── 4. Voice Coaching Anxiety Logic Tests ───────────────────────────────
    def test_interview_anxiety_indicator_warnings(self):
        """Verify that the engine identifies speech anxiety signals (stutter patterns, filler word counts)."""
        engine = InterviewEngine()
        
        # Test case: excessive usage of filler words
        anxious_answer = "I, like, um, worked on this project, basically, and like, it was nice."
        should_break, signals = engine.detect_anxiety_signals(anxious_answer)
        
        self.assertTrue(signals["filler_count"] >= 3)
        self.assertIn("like", signals["filler_words"])
        self.assertIn("um", signals["filler_words"])
        
        # Test case: normal clean answer
        clean_answer = "I built the cloud server infrastructure utilizing Kubernetes and Docker."
        clean_should_break, clean_signals = engine.detect_anxiety_signals(clean_answer)
        self.assertEqual(clean_signals["filler_count"], 0)
        self.assertFalse(clean_signals["fast_speaking"])

if __name__ == "__main__":
    unittest.main()
