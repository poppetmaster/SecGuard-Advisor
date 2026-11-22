"""Calibración y evaluación funcional del umbral de Qdrant."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from qdrant_client import QdrantClient
from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fixtures.corpus import create_case, seed_document
from tests.fixtures.qdrant_eval import CAL2, FINAL

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import (
    create_engine_for_url,
    create_session_factory,
)
from secguard_advisor.db.models import (
    Document,
    DocumentChunk,
    MessageCitation,
)
from secguard_advisor.documents.embedding import OllamaEmbeddingClient
from secguard_advisor.retrieval.calibration import choose_threshold
from secguard_advisor.retrieval.citations import check_citation
from secguard_advisor.retrieval.collections import (
    case_scope,
    public_scope,
)
from secguard_advisor.retrieval.evaluation import (
    evaluate_criteria,
    measure_isolation_violations,
)
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.retrieval.search import search_documents
from secguard_advisor.vulnerabilities.service import QualysImportService

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "files"
DATASETS = {"cal2": CAL2, "final": FINAL}


def _dataset_hash(dataset: dict) -> str:
    material = json.dumps(dataset, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(material).hexdigest()


def _environment(root: Path, instance: str):
    settings = Settings(
        _env_file=None,
        storage_dir=root / "storage",
        instance_id=instance,
        embedding_dim=768,
    )
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    return settings, engine


def _runtime(settings: Settings):
    factory = create_session_factory(create_engine_for_url(settings.database_url))
    embedder = OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        dimension=settings.embedding_dim,
        context_tokens=settings.embedding_context_tokens,
    )
    return factory, embedder


def _index(root: Path, settings: Settings, backend: str, instance: str):
    if backend == "embedded":
        client = QdrantClient(path=str(root / "qdrant"))
        storage_dir = None
    else:
        client = QdrantClient(url=settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)
        storage_dir = settings.storage_dir
    index = QdrantIndex(
        url=settings.qdrant_url,
        instance_id=instance,
        timeout=settings.qdrant_timeout_seconds,
        client=client,
        storage_dir=storage_dir,
    )
    return index, str(client.info().version)


def _scope(scope_key: str, case_ids: dict[str, str]):
    if scope_key == "public":
        return public_scope()
    return case_scope(case_ids[scope_key])


def _seed(dataset: dict, factory, index, embedder):
    scopes = {
        "public": seed_document(
            factory,
            texts=dataset["public"],
            source_id="eval-public",
            index=index,
            embedder=embedder,
        )
    }
    with factory() as session:
        case_ids = {
            "a": create_case(session, "Caso evaluación A"),
            "b": create_case(session, "Caso evaluación B"),
        }
        session.commit()
    for key, texts in dataset["cases"].items():
        scopes[key] = seed_document(
            factory,
            texts=texts,
            case_id=case_ids[key],
            index=index,
            embedder=embedder,
        )
    return scopes, case_ids


def _score(embedder, index, scope, query, expected_id, top_k):
    embedding = embedder.embed_one(query, kind="query")
    hits = index.query(scope, embedder.model, embedder.dimension, embedding.vector, top_k=top_k)
    scores = {hit.chunk_id: float(hit.score) for hit in hits if hit.score is not None}
    return scores.get(expected_id, 0.0), list(scores)


def _top(embedder, index, scope, query, top_k):
    embedding = embedder.embed_one(query, kind="query")
    hits = index.query(scope, embedder.model, embedder.dimension, embedding.vector, top_k=top_k)
    return max((float(hit.score) for hit in hits if hit.score is not None), default=0.0)


def _metadata(settings, backend, version, dataset, top_k, threshold):
    return {
        "backend": "qdrant",
        "modality": backend,
        "qdrant_version": version,
        "embedding_model": settings.ollama_embedding_model,
        "embedding_dim": settings.embedding_dim,
        "metric": "cosine",
        "top_k": top_k,
        "threshold": threshold,
        "executed_at": datetime.now(UTC).isoformat(),
        "dataset_sha256": _dataset_hash(dataset),
    }


def calibrate(root: Path, settings, backend: str, instance: str, dataset: dict) -> dict:
    factory, embedder = _runtime(settings)
    index, version = _index(root, settings, backend, instance)
    try:
        scopes, case_ids = _seed(dataset, factory, index, embedder)
        top_k = 3
        relevant = []
        for scope_key, query, position in dataset["relevant"]:
            expected = scopes[scope_key].chunk_ids[position]
            score, _ids = _score(
                embedder, index, _scope(scope_key, case_ids), query, expected, top_k
            )
            relevant.append({"scope": scope_key, "query": query, "score": round(score, 4)})
        non_relevant = []
        for query in dataset["non_relevant"]:
            score = _top(embedder, index, public_scope(), query, top_k)
            non_relevant.append({"query": query, "top_score": round(score, 4)})
        choice = choose_threshold(
            [item["score"] for item in relevant],
            [item["top_score"] for item in non_relevant],
        )
        return {
            "mode": "calibration",
            **_metadata(settings, backend, version, dataset, top_k, choice.threshold),
            "criteria": {
                "relevant": "el fragmento esperado debe recuperarse con score >= umbral",
                "non_relevant": "ninguna consulta no pertinente debe superar el umbral",
                "selection": "mayor umbral válido; si no existe, mejor equilibrio y fallo",
            },
            "relevant": relevant,
            "non_relevant": non_relevant,
            "proposed_threshold": round(min((i["score"] for i in relevant), default=0.0), 4),
            "observed": asdict(choice),
        }
    finally:
        index.close()
        embedder.close()


def _counts(factory, index, case_id, model, dimension):
    with factory() as session:
        return {
            "documents": session.scalar(select(func.count()).select_from(Document)) or 0,
            "chunks": session.scalar(select(func.count()).select_from(DocumentChunk)) or 0,
            "citations": session.scalar(select(func.count()).select_from(MessageCitation)) or 0,
            "points": index.count(public_scope(), model, dimension)
            + index.count(case_scope(case_id), model, dimension),
        }


def evaluate(
    root: Path, settings, backend: str, instance: str, dataset: dict, threshold: float
) -> dict:
    factory, embedder = _runtime(settings)
    index, version = _index(root, settings, backend, instance)
    try:
        scopes, case_ids = _seed(dataset, factory, index, embedder)
        top_k = 3
        results = []
        for scope_key, query, position in dataset["relevant"]:
            expected = scopes[scope_key].chunk_ids[position]
            score, ids = _score(
                embedder, index, _scope(scope_key, case_ids), query, expected, top_k
            )
            results.append(
                {
                    "scenario": f"{scope_key}-{position}",
                    "query": query,
                    "hit": score >= threshold and expected in ids,
                    "score": round(score, 4),
                }
            )
        accepted = 0
        for query in dataset["non_relevant"]:
            score = _top(embedder, index, public_scope(), query, top_k)
            if score >= threshold:
                accepted += 1
            results.append(
                {"scenario": "non-relevant", "query": query, "hit": False, "score": round(score, 4)}
            )

        retrieved = {}
        for key, case_id in case_ids.items():
            query = dataset["relevant"][3 if key == "a" else 5][1]
            with factory() as session:
                resolved = search_documents(
                    session,
                    scope=CaseScope(case_id=case_id),
                    query=query,
                    embedder=embedder,
                    index=index,
                    top_k=10,
                    min_score=threshold,
                )
            retrieved[key] = {hit.document_id for hit in resolved.hits}
        forbidden = {"a": {scopes["b"].document_id}, "b": {scopes["a"].document_id}}
        violations = measure_isolation_violations(retrieved=retrieved, forbidden=forbidden)

        superseded = dataset["superseded"]
        v1 = seed_document(
            factory,
            texts=[superseded["v1"]],
            source_id="version",
            index=index,
            embedder=embedder,
        )
        v2 = seed_document(
            factory,
            texts=[superseded["v2"]],
            source_id="version",
            new_version=True,
            index=index,
            embedder=embedder,
        )
        with factory() as session:
            version_result = search_documents(
                session,
                scope=CaseScope(case_id=case_ids["a"]),
                query=superseded["query"],
                embedder=embedder,
                index=index,
                top_k=10,
                min_score=threshold,
            )
            citation = check_citation(
                session,
                CaseScope(case_id=case_ids["a"]),
                chunk_id=v1.chunk_ids[0],
                version_id=v1.version_id,
                page=1,
                section=None,
                quote=superseded["v1"],
            )
        version_ids = {hit.chunk_id for hit in version_result.hits}
        current_only = set(v2.chunk_ids) == version_ids
        leaked = bool(version_ids & set(v1.chunk_ids))

        before = _counts(factory, index, case_ids["a"], embedder.model, embedder.dimension)
        service = QualysImportService(factory, settings)
        staged = service.stage_import(
            case_ids["a"],
            "valid.csv",
            (FIXTURES / "qualys_synthetic_valid.csv").read_bytes(),
        )
        service.confirm_import(case_ids["a"], staged.import_record.id)
        after = _counts(factory, index, case_ids["a"], embedder.model, embedder.dimension)
        qualys_unchanged = before == after

        outcome = evaluate_criteria(
            retrieval_ok=sum(1 for item in results if item["hit"]),
            retrieval_total=len(dataset["relevant"]),
            non_relevant_accepted=accepted,
            isolation_violations=violations,
            current_only=current_only,
            superseded_leaked=leaked,
            historical_citation=citation.status,
            qualys_unchanged=qualys_unchanged,
        )
        return {
            "mode": "evaluation",
            **_metadata(settings, backend, version, dataset, top_k, threshold),
            "criteria": {
                "retrieval": "todas las consultas pertinentes recuperan su fragmento con el umbral",
                "non_relevant": "ninguna consulta no pertinente supera el umbral",
                "isolation": "ningún documento privado cruza de caso",
                "versions": "la versión superada no reaparece; su cita histórica resuelve",
                "qualys": "la importación no altera documentos, fragmentos, puntos ni citas",
            },
            "results": results,
            "isolation": {
                "retrieved": {key: sorted(value) for key, value in retrieved.items()},
                "violations": violations,
            },
            "versions": {
                "current_only": current_only,
                "superseded_leaked": leaked,
                "historical_citation": citation.status,
            },
            "qualys": {"before": before, "after": after, "unchanged": qualys_unchanged},
            "metrics": {
                "retrieval_ok": sum(1 for item in results if item["hit"]),
                "retrieval_total": len(dataset["relevant"]),
                "non_relevant_accepted": accepted,
            },
            "outcome": {
                "passed": outcome.passed,
                "criteria": [asdict(item) for item in outcome.criteria],
            },
        }
    finally:
        index.close()
        embedder.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("calibrate", "evaluate"), required=True)
    parser.add_argument("--dataset", choices=tuple(DATASETS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("server", "embedded"), default="server")
    parser.add_argument("--instance", default="cut6-threshold")
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()
    dataset = DATASETS[args.dataset]
    with tempfile.TemporaryDirectory(prefix="cut6-threshold-") as directory:
        root = Path(directory)
        settings, engine = _environment(root, args.instance)
        try:
            if args.mode == "calibrate":
                report = calibrate(root, settings, args.backend, args.instance, dataset)
            else:
                if args.threshold is None:
                    raise SystemExit("--threshold es obligatorio en evaluación")
                report = evaluate(
                    root, settings, args.backend, args.instance, dataset, args.threshold
                )
        finally:
            engine.dispose()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    if args.mode == "evaluate" and not report["outcome"]["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
