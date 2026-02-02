#!/usr/bin/env python3
"""
Run the Agent Memory Benchmark (AMB).

Scores a memory system across 6 categories:
1. Identity Persistence (20 pts)
2. Semantic Recall (25 pts)
3. Temporal Reasoning (15 pts)
4. Active Context (20 pts)
5. Auto-Capture (10 pts)
6. Proactive Surfacing (10 pts)

Total: 100 points
"""

import argparse
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent_memory.memory import Memory
from agent_memory.extract import extract_memories
from agent_memory.surface import MemorySurfacer


@dataclass
class TestResult:
    name: str
    passed: bool
    score: float
    max_score: float
    details: str


@dataclass
class CategoryResult:
    name: str
    score: float
    max_score: float
    tests: List[TestResult]


class AMBenchmark:
    """Agent Memory Benchmark runner."""
    
    def __init__(self, db_path: str):
        self.mem = Memory(db_path)
        self.surfacer = MemorySurfacer(self.mem)
        self.results: List[CategoryResult] = []
    
    def run_all(self) -> Dict:
        """Run all benchmark categories."""
        self.results = [
            self._test_identity(),
            self._test_semantic_recall(),
            self._test_temporal(),
            self._test_active_context(),
            self._test_auto_capture(),
            self._test_proactive_surfacing(),
        ]
        
        total_score = sum(r.score for r in self.results)
        total_max = sum(r.max_score for r in self.results)
        
        return {
            'total_score': total_score,
            'total_max': total_max,
            'percentage': (total_score / total_max * 100) if total_max > 0 else 0,
            'categories': self.results,
            'grade': self._get_grade(total_score)
        }
    
    def _get_grade(self, score: float) -> str:
        if score >= 90:
            return "EXCELLENT"
        elif score >= 75:
            return "GOOD"
        elif score >= 60:
            return "ACCEPTABLE"
        else:
            return "NEEDS WORK"
    
    def _test_identity(self) -> CategoryResult:
        """Test identity persistence."""
        tests = []
        identity = self.mem.get_identity()
        
        # Name recall
        has_name = 'name' in identity and identity['name']
        tests.append(TestResult(
            "Name recall", has_name, 4 if has_name else 0, 4,
            f"name = {identity.get('name', 'NOT SET')}"
        ))
        
        # Human recall
        has_human = any(k for k in identity if 'human' in k.lower())
        tests.append(TestResult(
            "Human recall", has_human, 4 if has_human else 0, 4,
            f"human info = {any(k for k in identity if 'human' in k.lower())}"
        ))
        
        # Role/creature recall
        has_role = 'creature' in identity or 'role' in identity
        tests.append(TestResult(
            "Role recall", has_role, 4 if has_role else 0, 4,
            f"role/creature = {identity.get('creature', identity.get('role', 'NOT SET'))[:50]}"
        ))
        
        # Has soul/personality
        has_soul = 'soul' in identity
        tests.append(TestResult(
            "Personality", has_soul, 4 if has_soul else 0, 4,
            f"soul = {'SET' if has_soul else 'NOT SET'}"
        ))
        
        # History/birth
        has_history = 'born' in identity or any('birth' in k for k in identity)
        tests.append(TestResult(
            "History", has_history, 4 if has_history else 0, 4,
            f"born = {identity.get('born', 'NOT SET')}"
        ))
        
        total = sum(t.score for t in tests)
        return CategoryResult("Identity Persistence", total, 20, tests)
    
    def _test_semantic_recall(self) -> CategoryResult:
        """Test semantic/meaning-based recall."""
        tests = []
        
        # Synonym match: search for synonym of something in memory
        results = self.mem.search("monetization approach", limit=3)
        found_pricing = any('pric' in r['content'].lower() or 'money' in r['content'].lower() 
                           for r in results)
        tests.append(TestResult(
            "Synonym match", found_pricing, 5 if found_pricing else 0, 5,
            f"'monetization' found pricing-related: {found_pricing}"
        ))
        
        # Paraphrase match
        results = self.mem.search("why we changed direction", limit=3)
        found_pivot = any('pivot' in r['content'].lower() or 'chang' in r['content'].lower() 
                         for r in results)
        tests.append(TestResult(
            "Paraphrase match", found_pivot, 5 if found_pivot else 0, 5,
            f"'changed direction' found pivot: {found_pivot}"
        ))
        
        # Concept match
        results = self.mem.search("Bill's wishes and desires", limit=3)
        found_bill = any('bill' in r['content'].lower() for r in results)
        tests.append(TestResult(
            "Concept match", found_bill, 5 if found_bill else 0, 5,
            f"'Bill's wishes' found Bill-related: {found_bill}"
        ))
        
        # Negative test - random gibberish shouldn't match well
        results = self.mem.search("xyzzy quantum banana spacecraft", limit=3)
        low_relevance = all(r.get('relevance', 1) < 0.5 for r in results) if results else True
        tests.append(TestResult(
            "Negative test", low_relevance, 5 if low_relevance else 0, 5,
            f"Gibberish has low relevance: {low_relevance}"
        ))
        
        # Ranking quality - best match should be first
        results = self.mem.search("memory system for agents", limit=3)
        good_ranking = len(results) > 0 and (
            results[0].get('relevance', 0) >= results[-1].get('relevance', 0) if len(results) > 1 else True
        )
        tests.append(TestResult(
            "Ranking quality", good_ranking, 5 if good_ranking else 0, 5,
            f"Results properly ranked: {good_ranking}"
        ))
        
        total = sum(t.score for t in tests)
        return CategoryResult("Semantic Recall", total, 25, tests)
    
    def _test_temporal(self) -> CategoryResult:
        """Test temporal reasoning."""
        tests = []
        
        # Has any temporal metadata
        cursor = self.mem.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM memories WHERE metadata IS NOT NULL")
        has_dates = cursor.fetchone()[0] > 0
        tests.append(TestResult(
            "Has temporal data", has_dates, 5 if has_dates else 0, 5,
            f"Memories with dates: {has_dates}"
        ))
        
        # Can find by date reference
        results = self.mem.search("what happened today", limit=3)
        found_recent = len(results) > 0
        tests.append(TestResult(
            "Date-based recall", found_recent, 5 if found_recent else 0, 5,
            f"Found recent memories: {found_recent}"
        ))
        
        # Has created_at timestamps
        cursor.execute("SELECT COUNT(*) FROM memories WHERE created_at IS NOT NULL")
        has_timestamps = cursor.fetchone()[0] > 0
        tests.append(TestResult(
            "Timestamps present", has_timestamps, 5 if has_timestamps else 0, 5,
            f"Memories have timestamps: {has_timestamps}"
        ))
        
        total = sum(t.score for t in tests)
        return CategoryResult("Temporal Reasoning", total, 15, tests)
    
    def _test_active_context(self) -> CategoryResult:
        """Test active context management."""
        tests = []
        active = self.mem.get_active()
        
        # Has current task
        has_task = any('task' in k.lower() for k in active)
        tests.append(TestResult(
            "Current task", has_task, 5 if has_task else 0, 5,
            f"Has task: {has_task}"
        ))
        
        # Has current project
        has_project = any('project' in k.lower() for k in active)
        tests.append(TestResult(
            "Current project", has_project, 5 if has_project else 0, 5,
            f"Has project: {has_project}"
        ))
        
        # Can update (test by setting and reading)
        self.mem.set_active("_benchmark_test", "test_value")
        updated = self.mem.get_active("_benchmark_test").get("_benchmark_test") == "test_value"
        tests.append(TestResult(
            "State update", updated, 5 if updated else 0, 5,
            f"Can update state: {updated}"
        ))
        
        # Has session state
        has_state = 'session_state' in active or len(active) > 0
        tests.append(TestResult(
            "Session state", has_state, 5 if has_state else 0, 5,
            f"Has session state: {has_state}"
        ))
        
        total = sum(t.score for t in tests)
        return CategoryResult("Active Context", total, 20, tests)
    
    def _test_auto_capture(self) -> CategoryResult:
        """Test automatic capture capabilities."""
        tests = []
        
        # Decision capture
        test_text = "We decided to use sqlite for storage"
        memories = extract_memories(test_text)
        found_decision = any(m.memory_type == 'decision' for m in memories)
        tests.append(TestResult(
            "Decision capture", found_decision, 3 if found_decision else 0, 3,
            f"Extracted decision: {found_decision}"
        ))
        
        # Preference capture
        test_text = "I prefer semantic search over keyword matching"
        memories = extract_memories(test_text)
        found_pref = any(m.memory_type == 'preference' for m in memories)
        tests.append(TestResult(
            "Preference capture", found_pref, 3 if found_pref else 0, 3,
            f"Extracted preference: {found_pref}"
        ))
        
        # No-noise capture
        test_text = "The weather is nice today. Hello world. Testing 123."
        memories = extract_memories(test_text)
        no_noise = len(memories) == 0
        tests.append(TestResult(
            "No-noise capture", no_noise, 4 if no_noise else 0, 4,
            f"Ignored noise: {no_noise}"
        ))
        
        total = sum(t.score for t in tests)
        return CategoryResult("Auto-Capture", total, 10, tests)
    
    def _test_proactive_surfacing(self) -> CategoryResult:
        """Test proactive memory surfacing."""
        tests = []
        
        # Entity surfacing
        surfaced = self.surfacer.surface("Bill mentioned something", limit=3)
        found_bill = any('bill' in s.content.lower() for s in surfaced)
        tests.append(TestResult(
            "Entity surfacing", found_bill, 4 if found_bill else 0, 4,
            f"Bill mention surfaced Bill info: {found_bill}"
        ))
        
        # Context surfacing
        surfaced = self.surfacer.surface("working on the memory project", limit=3)
        found_relevant = len(surfaced) > 0
        tests.append(TestResult(
            "Context surfacing", found_relevant, 3 if found_relevant else 0, 3,
            f"Context surfaced relevant: {found_relevant}"
        ))
        
        # Startup surfacing
        startup_memories = self.surfacer.surface_for_startup()
        has_startup = True  # Just check it doesn't crash
        tests.append(TestResult(
            "Startup surfacing", has_startup, 3 if has_startup else 0, 3,
            f"Startup surfacing works: {has_startup}"
        ))
        
        total = sum(t.score for t in tests)
        return CategoryResult("Proactive Surfacing", total, 10, tests)
    
    def close(self):
        self.mem.close()


def main():
    parser = argparse.ArgumentParser(description="Run Agent Memory Benchmark")
    parser.add_argument("--db", required=True, help="Path to memory database")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed results")
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("AGENT MEMORY BENCHMARK (AMB)")
    print("=" * 50)
    print()
    
    bench = AMBenchmark(args.db)
    results = bench.run_all()
    
    for cat in results['categories']:
        print(f"\n{cat.name}: {cat.score}/{cat.max_score}")
        if args.verbose:
            for test in cat.tests:
                status = "✓" if test.passed else "✗"
                print(f"  {status} {test.name}: {test.score}/{test.max_score}")
                print(f"      {test.details}")
    
    print("\n" + "=" * 50)
    print(f"TOTAL SCORE: {results['total_score']}/{results['total_max']} ({results['percentage']:.1f}%)")
    print(f"GRADE: {results['grade']}")
    print("=" * 50)
    
    bench.close()


if __name__ == "__main__":
    main()
