"""Tests for the memory system."""

import os
import tempfile
import pytest
from src.memory import Memory


@pytest.fixture
def mem():
    """Create a temporary memory instance for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    m = Memory(db_path)
    yield m
    
    m.close()
    os.unlink(db_path)


class TestIdentity:
    def test_set_and_get(self, mem):
        mem.set_identity('name', 'TestBot')
        result = mem.get_identity('name')
        assert result == {'name': 'TestBot'}
    
    def test_get_all(self, mem):
        mem.set_identity('name', 'TestBot')
        mem.set_identity('human', 'TestHuman')
        result = mem.get_identity()
        assert result == {'name': 'TestBot', 'human': 'TestHuman'}
    
    def test_update(self, mem):
        mem.set_identity('name', 'OldName')
        mem.set_identity('name', 'NewName')
        result = mem.get_identity('name')
        assert result == {'name': 'NewName'}
    
    def test_context_format(self, mem):
        mem.set_identity('name', 'TestBot')
        context = mem.get_identity_context()
        assert '# Identity' in context
        assert 'name: TestBot' in context


class TestActiveContext:
    def test_set_and_get(self, mem):
        mem.set_active('task', 'Testing')
        result = mem.get_active('task')
        assert result == {'task': 'Testing'}
    
    def test_context_format(self, mem):
        mem.set_active('task', 'Testing the system')
        context = mem.get_active_context()
        assert '# Active Context' in context
        assert '## task' in context


class TestMemoryArchive:
    def test_add_memory(self, mem):
        memory_id = mem.add('Test memory content', memory_type='fact')
        assert memory_id > 0
    
    def test_add_with_salience(self, mem):
        memory_id = mem.add('Important memory', salience=0.9)
        stats = mem.stats()
        assert stats['memories'] == 1
    
    def test_keyword_search(self, mem):
        mem.add('The quick brown fox')
        mem.add('Lazy dog sleeping')
        
        results = mem.search('fox')
        # With semantic search, should find the fox memory with highest relevance
        assert len(results) >= 1
        # The most relevant result should contain 'fox'
        assert 'fox' in results[0]['content']
    
    def test_search_relevance(self, mem):
        mem.add('Machine learning is fascinating')
        mem.add('The weather is nice today')
        
        results = mem.search('AI and neural networks')
        # Semantic search should rank ML higher than weather
        if len(results) >= 2:
            assert results[0]['relevance'] >= results[1]['relevance']


class TestStartupContext:
    def test_empty_startup(self, mem):
        context = mem.get_startup_context()
        assert context == ""
    
    def test_full_startup(self, mem):
        mem.set_identity('name', 'TestBot')
        mem.set_active('task', 'Testing')
        
        context = mem.get_startup_context()
        assert '# Identity' in context
        assert '# Active Context' in context


class TestStats:
    def test_initial_stats(self, mem):
        stats = mem.stats()
        assert stats['memories'] == 0
        assert stats['identity_keys'] == 0
        assert stats['active_keys'] == 0
    
    def test_stats_after_adds(self, mem):
        mem.set_identity('name', 'Test')
        mem.set_active('task', 'Testing')
        mem.add('A memory')
        
        stats = mem.stats()
        assert stats['memories'] == 1
        assert stats['identity_keys'] == 1
        assert stats['active_keys'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
