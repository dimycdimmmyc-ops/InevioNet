"""Tests for evolution module."""
import pytest
from inevionet.evolution import ProtocolGenome, EvolutionEngine
from inevionet.evolution.genome import create_random_genome, create_from_protocol


class TestProtocolGenome:
    def test_create(self):
        g = ProtocolGenome()
        assert 0 <= g.fitness <= 1

    def test_mutate(self):
        g = ProtocolGenome()
        old_id = g.genome_id
        g.mutate()
        assert g.genome_id != old_id
        assert g.generation == 1

    def test_crossover(self):
        g1 = create_random_genome("TCP")
        g2 = create_random_genome("UDP")
        child = g1.crossover(g2)
        assert child.parent_ids == [g1.genome_id, g2.genome_id]

    def test_serialization(self):
        g = ProtocolGenome()
        data = g.to_dict()
        restored = ProtocolGenome.from_dict(data)
        assert restored.genome_id == g.genome_id

    def test_from_protocol(self):
        g = create_from_protocol("TCP")
        assert g.protocol_name == "TCP"
        assert g.reliability >= 0.8


class TestEvolutionEngine:
    def test_create(self):
        engine = EvolutionEngine(population_size=10)
        assert engine.population_size == 10

    def test_initialize(self):
        engine = EvolutionEngine(population_size=10)
        engine.initialize()
        assert len(engine.population) == 10

    def test_evolve(self):
        engine = EvolutionEngine(population_size=10)
        engine.initialize()
        initial_best = engine.get_best_genome().fitness
        for _ in range(5):
            engine.evolve()
        stats = engine.get_stats()
        assert stats["generation"] == 5

    def test_get_top(self):
        engine = EvolutionEngine(population_size=10)
        engine.initialize()
        top = engine.get_top_genomes(3)
        assert len(top) == 3
