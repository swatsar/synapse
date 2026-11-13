"""Tests for the bounded growth-network graph export."""
from __future__ import annotations

from synapse.growth.network import GrowthNetwork


def _seed(network: GrowthNetwork) -> None:
    for index in range(6):
        network.record_execution(
            task=f"parse config {index}",
            skill="codegen",
            provider="opencode",
            model="opencode/glm-5.3-flash-free",
            success=index % 3 != 0,
        )


def test_graph_export_has_only_connected_edges(tmp_path):
    network = GrowthNetwork(tmp_path / "growth.sqlite3")
    _seed(network)

    graph = network.graph(node_limit=10, edge_limit=20)

    assert graph["nodes"], graph
    ids = {node["id"] for node in graph["nodes"]}
    assert graph["edges"]
    for edge in graph["edges"]:
        # The interface must never receive a line with a missing endpoint.
        assert edge["source_id"] in ids, edge
        assert edge["target_id"] in ids, edge
        assert edge["relation"]


def test_graph_limits_are_respected_and_reported(tmp_path):
    network = GrowthNetwork(tmp_path / "growth.sqlite3")
    _seed(network)
    total_status = network.status()

    graph = network.graph(node_limit=2, edge_limit=3)

    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) <= 3
    assert graph["nodes_total"] == total_status["nodes"]
    assert graph["edges_total"] == total_status["edges"]
    assert graph["truncated"] is True


def test_graph_export_does_not_mutate_the_network(tmp_path):
    network = GrowthNetwork(tmp_path / "growth.sqlite3")
    _seed(network)
    before = network.status()

    network.graph(node_limit=10, edge_limit=20)

    after = network.status()
    assert after["events"] == before["events"]
    assert after["nodes"] == before["nodes"]
    assert after["edges"] == before["edges"]
    assert after["consolidation_passes"] == before["consolidation_passes"]


def test_graph_export_of_empty_network_is_empty(tmp_path):
    network = GrowthNetwork(tmp_path / "growth.sqlite3")

    graph = network.graph()

    assert graph["nodes"] == []
    assert graph["edges"] == []
    assert graph["truncated"] is False