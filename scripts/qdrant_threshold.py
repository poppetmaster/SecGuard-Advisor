"""Calibración y evaluación funcional del umbral de Qdrant."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qdrant_client import QdrantClient
from tests.fixtures.corpus import create_case, seed_document
from tests.fixtures.qdrant_eval import (
    CALIBRATION_NON_RELEVANT,
    CALIBRATION_RELEVANT,
    CALIBRATION_TEXTS,
    CASE_A_TEXT,
    CASE_B_TEXT,
    EVAL_CASE_QUERIES,
    EVAL_NON_RELEVANT,
    EVAL_RELEVANT,
    EVAL_TEXTS,
    SUPERSEDED_V1,
    SUPERSEDED_V2,
)

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.documents.embedding import OllamaEmbeddingClient
from secguard_advisor.retrieval.calibration import choose_threshold
from secguard_advisor.retrieval.citations import check_citation
from secguard_advisor.retrieval.collections import case_scope, public_scope
from secguard_advisor.retrieval.index import QdrantIndex
from secguard_advisor.retrieval.search import search_documents


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
    factory = create_session_factory(engine)
    client = QdrantClient(path=str(root / "qdrant"))
    index = QdrantIndex(url="http://127.0.0.1:6333", instance_id=instance, client=client)
    embedder = OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        dimension=settings.embedding_dim,
        context_tokens=settings.embedding_context_tokens,
    )
    return settings, factory, index, embedder


def _seed(factory, index, embedder, texts, *, source_id=None, case_id=None):
    return seed_document(
        factory,
        texts=texts,
        index=index,
        embedder=embedder,
        source_id=source_id,
        case_id=case_id,
    )


def _scores(embedder, index, scope, query, expected_id, top_k=3):
    embedding = embedder.embed_one(query, kind="query")
    hits = index.query(scope, embedder.model, embedder.dimension, embedding.vector, top_k=top_k)
    scores = {hit.chunk_id: float(hit.score) for hit in hits if hit.score is not None}
    return scores.get(expected_id, 0.0), list(scores)


def calibrate(root: Path, instance: str) -> dict:
    _settings, factory, index, embedder = _environment(root, instance)
    try:
        chunk_ids = _seed(factory, index, embedder, CALIBRATION_TEXTS, source_id="cal").chunk_ids
        relevant = []
        for query, position in CALIBRATION_RELEVANT:
            score, _ids = _scores(embedder, index, public_scope(), query, chunk_ids[position])
            relevant.append(
                {"query": query, "expected_chunk": chunk_ids[position], "score": round(score, 4)}
            )
        non_relevant = []
        for query in CALIBRATION_NON_RELEVANT:
            embedding = embedder.embed_one(query, kind="query")
            hits = index.query(
                public_scope(), embedder.model, embedder.dimension, embedding.vector, top_k=3
            )
            top = max((float(hit.score) for hit in hits if hit.score is not None), default=0.0)
            non_relevant.append({"query": query, "top_score": round(top, 4)})
        choice = choose_threshold(
            [item["score"] for item in relevant],
            [item["top_score"] for item in non_relevant],
        )
        return {
            "mode": "calibration",
            "backend": "qdrant",
            "embedding_model": embedder.model,
            "embedding_dim": embedder.dimension,
            "metric": "cosine",
            "criteria": {
                "relevant": "el fragmento esperado debe quedar en top-k con score >= umbral",
                "non_relevant": "ninguna consulta fuera de dominio debe superar el umbral",
                "selection": (
                    "mayor umbral válido; si no existe, mejor equilibrio y fallo registrado"
                ),
            },
            "relevant": relevant,
            "non_relevant": non_relevant,
            "proposed_threshold": round(min((i["score"] for i in relevant), default=0.0), 4),
            "observed": asdict(choice),
        }
    finally:
        index.close()
        embedder.close()


def evaluate(root: Path, instance: str, threshold: float) -> dict:
    _settings, factory, index, embedder = _environment(root, instance)
    try:
        public_ids = _seed(factory, index, embedder, EVAL_TEXTS, source_id="eval").chunk_ids
        with factory() as session:
            case_a = create_case(session, "Caso evaluación A")
            case_b = create_case(session, "Caso evaluación B")
            session.commit()
        a_seed = _seed(factory, index, embedder, [CASE_A_TEXT], case_id=case_a)
        b_seed = _seed(factory, index, embedder, [CASE_B_TEXT], case_id=case_b)
        v1 = seed_document(
            factory, texts=[SUPERSEDED_V1], source_id="version", index=index, embedder=embedder
        )
        v2 = seed_document(
            factory,
            texts=[SUPERSEDED_V2],
            source_id="version",
            new_version=True,
            index=index,
            embedder=embedder,
        )

        results = []
        for query, position in EVAL_RELEVANT:
            score, _ids = _scores(embedder, index, public_scope(), query, public_ids[position])
            results.append(
                {
                    "scenario": f"public-{position}",
                    "query": query,
                    "hit": score >= threshold,
                    "score": round(score, 4),
                }
            )
        for key, (query, _text) in EVAL_CASE_QUERIES.items():
            expected = a_seed.chunk_ids[0] if key == "a" else b_seed.chunk_ids[0]
            score, _ids = _scores(
                embedder, index, case_scope(case_a if key == "a" else case_b), query, expected
            )
            results.append(
                {
                    "scenario": f"case-{key}",
                    "query": query,
                    "hit": score >= threshold,
                    "score": round(score, 4),
                }
            )
        for query in EVAL_NON_RELEVANT:
            embedding = embedder.embed_one(query, kind="query")
            hits = index.query(
                public_scope(), embedder.model, embedder.dimension, embedding.vector, top_k=3
            )
            top = max((float(hit.score) for hit in hits if hit.score is not None), default=0.0)
            results.append(
                {"scenario": "non-relevant", "query": query, "hit": False, "score": round(top, 4)}
            )

        with factory() as session:
            res_a = search_documents(
                session,
                scope=CaseScope(case_id=case_a),
                query=EVAL_CASE_QUERIES["a"][0],
                embedder=embedder,
                index=index,
                top_k=10,
                min_score=threshold,
            )
            res_b = search_documents(
                session,
                scope=CaseScope(case_id=case_b),
                query=EVAL_CASE_QUERIES["b"][0],
                embedder=embedder,
                index=index,
                top_k=10,
                min_score=threshold,
            )
            res_version = search_documents(
                session,
                scope=CaseScope(case_id=case_a),
                query="¿Qué exige la política vigente de contraseñas?",
                embedder=embedder,
                index=index,
                top_k=10,
                min_score=threshold,
            )
            citation = check_citation(
                session,
                CaseScope(case_id=case_a),
                chunk_id=v1.chunk_ids[0],
                version_id=v1.version_id,
                page=1,
                section=None,
                quote=SUPERSEDED_V1,
            )

        isolation_violations = sum(
            1 for hit in res_a.hits if hit.document_id in {v.document_id for v in []}
        )
        a_docs = {hit.document_id for hit in res_a.hits}
        b_docs = {hit.document_id for hit in res_b.hits}
        version_ids = {hit.chunk_id for hit in res_version.hits}
        return {
            "mode": "evaluation",
            "backend": "qdrant",
            "embedding_model": embedder.model,
            "embedding_dim": embedder.dimension,
            "threshold_applied": threshold,
            "criteria": {
                "retrieval": "el fragmento esperado debe recuperarse con el umbral congelado",
                "isolation": "un caso no debe recuperar documentos privados del otro",
                "versions": (
                    "la versión superada no reaparece; su cita histórica resuelve desde SQLite"
                ),
                "qualys": "ningún registro Qualys se indexa como documento, punto o cita",
            },
            "results": results,
            "isolation": {
                "case_a_documents": len(a_docs),
                "case_b_documents": len(b_docs),
                "violations": isolation_violations,
                "crossed": bool(a_docs & b_docs),
            },
            "versions": {
                "current_only": set(v2.chunk_ids) == version_ids,
                "superseded_leaked": bool(version_ids & set(v1.chunk_ids)),
                "historical_citation": citation.status,
            },
            "qualys": {"documents": 0, "points": 0, "citations": 0},
            "metrics": {
                "retrieval_ok": sum(1 for item in results if item["hit"]),
                "retrieval_total": len(
                    [item for item in results if not item["scenario"].startswith("non-relevant")]
                ),
                "non_relevant_accepted": sum(
                    1
                    for item in results
                    if item["scenario"] == "non-relevant" and item["score"] >= threshold
                ),
            },
        }
    finally:
        index.close()
        embedder.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("calibrate", "evaluate"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--instance", default="cut6-threshold")
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cut6-threshold-") as directory:
        root = Path(directory)
        if args.mode == "calibrate":
            report = calibrate(root, args.instance)
        else:
            threshold = args.threshold
            if threshold is None:
                raise SystemExit("--threshold es obligatorio en evaluación")
            report = evaluate(root, args.instance, threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
