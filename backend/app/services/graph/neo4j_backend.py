"""Neo4j implementation of `GraphBackend` with strict workspace isolation.

Two things here are load-bearing for multi-tenancy:

1. Node identity is `(workspace_id, source_document_id, canonical_name)`, not `canonical_name`. The
   previous unique constraint on `canonical_name` alone meant "Pump P-101" in two
   different customers' workspaces was literally the same node, sharing
   relationships and evidence.
2. Every read filters `workspace_id = $ws_id` exactly. The previous queries used
   `... OR n.workspace_id IS NULL`, so any node written without a workspace was
   readable by every tenant.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from neo4j import Driver, GraphDatabase

from app.core.config import get_settings
from app.schemas.knowledge import KnowledgeGraphExtraction
from app.services.graph.base import GraphBackend
from app.services.graph.view import GraphReads, merge_topology

logger = logging.getLogger(__name__)

_MAX_DEPTH = 3


def sanitize_identifier(name: str) -> str:
    """Make a string safe to interpolate as a Cypher label or relationship type.

    Labels and relationship types cannot be parameterised in Cypher, so they are
    string-interpolated. This is the injection barrier: everything that is not
    [A-Za-z0-9_] is stripped before it reaches a query.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", (name or "").strip())
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"TYPE_{cleaned}"
    return cleaned[:64]


class Neo4jBackend(GraphReads, GraphBackend):
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        settings = get_settings()
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self._driver: Optional[Driver] = None
        self._init_driver()

    # -- connection ---------------------------------------------------------

    def _init_driver(self) -> None:
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                connection_timeout=5.0,
                max_connection_pool_size=20,
            )
            self._init_schema()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to connect to Neo4j at %s: %s", self.uri, exc)
            if self._driver is not None:
                self._driver.close()
            self._driver = None
            raise ConnectionError("Neo4j connection or schema initialization failed") from exc

    def _get_session(self):
        if not self._driver:
            self._init_driver()
        if not self._driver:
            raise ConnectionError("Unable to establish a connection to Neo4j.")
        return self._driver.session()

    def _init_schema(self) -> None:
        if not self._driver:
            return
        with self._driver.session() as session:
            # Retire the old global-uniqueness constraint if this database was
            # created by a previous version; it blocks the composite key below.
            try:
                for record in session.run("SHOW CONSTRAINTS"):
                    props = record.get("properties") or []
                    labels = record.get("labelsOrTypes") or []
                    if list(props) in (["canonical_name"], ["workspace_id", "canonical_name"]) and "Entity" in list(labels):
                        session.run("DROP CONSTRAINT `" + record["name"].replace("`", "``") + "` IF EXISTS")
                        logger.warning(
                            "Dropped legacy global uniqueness constraint %s on "
                            "Entity.canonical_name (it merged entities across workspaces).",
                            record["name"],
                        )
            except Exception as exc:  # noqa: BLE001
                raise ConnectionError("Could not inspect Neo4j constraints") from exc

            try:
                session.run(
                    "CREATE CONSTRAINT entity_document_canonical IF NOT EXISTS "
                    "FOR (n:Entity) REQUIRE (n.workspace_id, n.source_document_id, n.canonical_name) IS UNIQUE"
                )
                session.run(
                    "CREATE INDEX entity_workspace IF NOT EXISTS "
                    "FOR (n:Entity) ON (n.workspace_id)"
                )
                session.run(
                    "CREATE INDEX entity_source_document IF NOT EXISTS "
                    "FOR (n:Entity) ON (n.source_document_id)"
                )
            except Exception as exc:  # noqa: BLE001
                raise ConnectionError("Could not initialize Neo4j schema") from exc

    def health_check(self) -> bool:
        try:
            with self._get_session() as session:
                record = session.run("RETURN 1 AS ok").single()
                return bool(record and record["ok"] == 1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Neo4j health check failed: %s", exc)
            return False

    # -- writes -------------------------------------------------------------

    def ingest_extraction(
        self, extraction: KnowledgeGraphExtraction, workspace_id: str
    ) -> None:
        if not workspace_id:
            raise ValueError("workspace_id is required to ingest into the knowledge graph")
        if not extraction.entities and not extraction.relationships:
            return

        logger.info(
            "Ingesting %d entities / %d relationships into Neo4j workspace %s",
            len(extraction.entities), len(extraction.relationships), workspace_id,
        )

        with self._get_session() as session:
            with session.begin_transaction() as tx:
                tx.run(
                    "MATCH (n:Entity) WHERE n.workspace_id = $ws_id "
                    "AND n.source_document_id IN $documents DETACH DELETE n",
                    ws_id=workspace_id,
                    documents=list({entity.source_document_id for entity in extraction.entities}),
                )
                for entity in extraction.entities:
                    label = sanitize_identifier(entity.type or "Entity")
                    properties = (
                        json.dumps(entity.properties)
                        if isinstance(entity.properties, dict)
                        else json.dumps({})
                    )
                    tx.run(
                        f"""
                        MERGE (n:Entity {{workspace_id: $workspace_id, canonical_name: $canonical_name, source_document_id: $source_document_id}})
                        SET n:{label},
                            n.id = $id,
                            n.type = $type,
                            n.raw_name = $raw_name,
                            n.properties = $properties,
                            n.confidence = $confidence,
                            n.confidence_label = $confidence_label,
                            n.source_document_id = $source_document_id,
                            n.page_number = $page_number,
                            n.evidence_snippet = $evidence_snippet,
                            n.extraction_timestamp = $extraction_timestamp,
                            n.version = $version
                        """,
                        workspace_id=workspace_id,
                        canonical_name=entity.canonical_name,
                        id=entity.id,
                        type=entity.type,
                        raw_name=entity.name,
                        properties=properties,
                        confidence=float(entity.confidence),
                        confidence_label=_enum_value(entity.confidence_label),
                        source_document_id=entity.source_document_id,
                        page_number=entity.page_number,
                        evidence_snippet=entity.evidence_snippet,
                        extraction_timestamp=entity.extraction_timestamp.isoformat(),
                        version=entity.version,
                    )

                id_to_canonical = {e.id: e.canonical_name for e in extraction.entities}
                for rel in extraction.relationships:
                    source = id_to_canonical.get(rel.source_entity_id)
                    target = id_to_canonical.get(rel.target_entity_id)
                    if not source or not target:
                        continue

                    rel_type = sanitize_identifier(rel.type or "RELATED_TO").upper()
                    tx.run(
                        f"""
                        MATCH (s:Entity {{workspace_id: $workspace_id, canonical_name: $source, source_document_id: $source_document_id}})
                        MATCH (t:Entity {{workspace_id: $workspace_id, canonical_name: $target, source_document_id: $source_document_id}})
                        MERGE (s)-[r:{rel_type}]->(t)
                        SET r.type = $raw_type,
                            r.workspace_id = $workspace_id,
                            r.confidence = $confidence,
                            r.confidence_label = $confidence_label,
                            r.evidence = $evidence,
                            r.source_document_id = $source_document_id,
                            r.page_number = $page_number,
                            r.extraction_timestamp = $extraction_timestamp,
                            r.version = $version
                        """,
                        workspace_id=workspace_id,
                        source=source,
                        target=target,
                        raw_type=rel.type,
                        confidence=float(rel.confidence),
                        confidence_label=_enum_value(rel.confidence_label),
                        evidence=rel.evidence,
                        source_document_id=rel.source_document_id,
                        page_number=rel.page_number,
                        extraction_timestamp=rel.extraction_timestamp.isoformat(),
                        version=rel.version,
                    )

    def delete_document_subgraph(self, document_id: str, workspace_id: str) -> int:
        """Delete entities sourced from one document within one workspace."""
        if not (document_id and workspace_id):
            return 0
        with self._get_session() as session:
            record = session.run(
                """
                MATCH (n:Entity)
                WHERE n.workspace_id = $ws_id AND n.source_document_id = $doc_id
                WITH collect(n) AS nodes
                CALL {
                    WITH nodes
                    UNWIND nodes AS n
                    DETACH DELETE n
                }
                RETURN size(nodes) AS deleted
                """,
                ws_id=workspace_id,
                doc_id=document_id,
            ).single()
            deleted = int(record["deleted"]) if record else 0
        logger.info(
            "Deleted %d graph node(s) for document %s in workspace %s",
            deleted, document_id, workspace_id,
        )
        return deleted

    # -- reads --------------------------------------------------------------

    def get_topology(self, workspace_id: str) -> Dict[str, Any]:
        if not workspace_id:
            return {"nodes": [], "edges": []}
        with self._get_session() as session:
            nodes = [self._format_node(dict(row["n"])) for row in session.run(
                "MATCH (n:Entity) WHERE n.workspace_id = $ws_id RETURN n", ws_id=workspace_id
            )]
            edges = [self._format_edge(row["r"],
                source=self._format_node(dict(row["s"]))["id"],
                target=self._format_node(dict(row["t"]))["id"])
                for row in session.run(
                    "MATCH (s:Entity)-[r]->(t:Entity) "
                    "WHERE s.workspace_id = $ws_id AND t.workspace_id = $ws_id RETURN s, r, t",
                    ws_id=workspace_id,
                )]
        return merge_topology({"nodes": nodes, "edges": edges})

    # -- formatting ---------------------------------------------------------

    @staticmethod
    def _format_node(data: dict) -> Dict[str, Any]:
        canonical = data.get("canonical_name") or data.get("id") or "Unknown"
        node_type = data.get("type") or "Entity"

        properties = data.get("properties", {})
        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except json.JSONDecodeError:
                properties = {"raw": properties}
        if not isinstance(properties, dict):
            properties = {}

        return {
            "id": canonical,
            "name": canonical,
            "canonical_name": canonical,
            "raw_name": data.get("raw_name") or canonical,
            "type": node_type,
            "group": str(node_type).lower(),
            "confidence": float(data.get("confidence", 0.0)),
            "confidence_label": data.get("confidence_label") or "High",
            "source_document_id": data.get("source_document_id") or "",
            "workspace_id": data.get("workspace_id") or "",
            "evidence_snippet": data.get("evidence_snippet") or "",
            "page_number": data.get("page_number"),
            "properties": properties,
        }

    def _format_edge(self, rel, *, source: str = "", target: str = "") -> Dict[str, Any]:
        data = dict(rel)
        if not source:
            source = self._format_node(dict(rel.start_node))["id"]
        if not target:
            target = self._format_node(dict(rel.end_node))["id"]
        edge_type = data.get("type") or rel.type
        return {
            "source": source,
            "target": target,
            "type": edge_type,
            "label": edge_type,
            "confidence": float(data.get("confidence", 0.0)),
            "evidence": data.get("evidence") or "",
            "source_document_id": data.get("source_document_id") or "",
            "page_number": data.get("page_number"),
        }


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _empty_stats() -> Dict[str, Any]:
    return {
        "total_nodes": 0,
        "total_relationships": 0,
        "entity_type_counts": {},
        "relationship_type_counts": {},
    }
