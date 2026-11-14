"""Merge document evidence for display without discarding its ownership."""

from collections import Counter
import networkx as nx


def merge_topology(topology, excluded=()):
    def merge(items, key):
        grouped = {}
        for item in items:
            for source in item.get("sources", [item]):
                if source.get("source_document_id") in excluded:
                    continue
                grouped.setdefault(key(source), {})[source.get("source_document_id")] = source
        result = []
        for sources in grouped.values():
            evidence = sorted(sources.values(), key=lambda s: s.get("source_document_id", ""))
            result.append({**evidence[0], "sources": evidence})
        return result

    nodes = merge(topology["nodes"], lambda n: n["id"])
    ids = {n["id"] for n in nodes}
    edges = merge(topology["edges"], lambda e: (e["source"], e["target"], e["type"]))
    return {"nodes": nodes, "edges": [e for e in edges if e["source"] in ids and e["target"] in ids]}


class GraphReads:
    def get_node(self, node_id, workspace_id):
        return next((n for n in self.get_topology(workspace_id)["nodes"] if n["id"] == node_id), None)

    def get_stats(self, workspace_id):
        topology = self.get_topology(workspace_id)
        return {
            "total_nodes": len(topology["nodes"]),
            "total_relationships": len(topology["edges"]),
            "entity_type_counts": dict(Counter(n["type"] for n in topology["nodes"])),
            "relationship_type_counts": dict(Counter(e["type"] for e in topology["edges"])),
        }

    def get_subgraph(self, root_node_id, workspace_id, depth=1):
        topology = self.get_topology(workspace_id)
        graph = nx.Graph()
        graph.add_nodes_from(n["id"] for n in topology["nodes"])
        graph.add_edges_from((e["source"], e["target"]) for e in topology["edges"])
        if root_node_id not in graph:
            return {"nodes": [], "edges": []}
        ids = set(nx.single_source_shortest_path_length(graph, root_node_id, cutoff=max(1, min(depth, 3))))
        return {
            "nodes": [n for n in topology["nodes"] if n["id"] in ids],
            "edges": [e for e in topology["edges"] if e["source"] in ids and e["target"] in ids],
        }


class VisibleGraph(GraphReads):
    def __init__(self, backend):
        self.backend = backend

    def health_check(self):
        return self.backend.health_check()

    def ingest_extraction(self, extraction, workspace_id):
        return self.backend.ingest_extraction(extraction, workspace_id)

    def delete_document_subgraph(self, document_id, workspace_id):
        return self.backend.delete_document_subgraph(document_id, workspace_id)

    def get_topology(self, workspace_id):
        from app.services.cleanup_service import pending_document_ids
        # Fetch tombstones after the index, so a concurrent deletion cannot reappear.
        topology = self.backend.get_topology(workspace_id)
        return merge_topology(topology, pending_document_ids(workspace_id))
