"""Rutas de documentos, estados, versiones y fragmentos."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from markupsafe import Markup, escape

from secguard_advisor.cases.scope import (
    CaseNotFoundError,
    require_case,
    resolve_case_scope,
)
from secguard_advisor.db.models import Document, DocumentChunk, DocumentVersion
from secguard_advisor.documents.service import (
    DocumentConflict,
    DocumentNotFound,
    documents_overview,
    get_document,
    ingest_document,
    list_chunks,
    list_versions,
    retry_ingestion,
)
from secguard_advisor.documents.validation import (
    DocumentValidationError,
    read_upload,
)
from secguard_advisor.retrieval.citations import find_quote_span
from secguard_advisor.web.errors import ERRORS
from secguard_advisor.web.navigation import Crumb, case_crumbs, page

router = APIRouter(tags=["documents"])


def _templates(request: Request):
    return request.app.state.templates


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request", "").lower() == "true"


def _resolve_scope(request: Request, case_id: str):
    with request.app.state.session_factory() as session:
        return resolve_case_scope(session, case_id)


def _case_header(request: Request, case_id: str) -> tuple[str, str]:
    """Título del caso para la navegación, resuelto en el servidor."""
    with request.app.state.session_factory() as session:
        scope = resolve_case_scope(session, case_id)
        case = require_case(session, scope)
        return case.id, case.title


def _section(
    request: Request,
    case_id: str,
    case_title: str,
    *,
    status_code: int = 200,
):
    with request.app.state.session_factory() as session:
        documents = documents_overview(session, case_id)
    return _templates(request).TemplateResponse(
        request=request,
        name="documents/section.html",
        context={
            "case_id": case_id,
            "documents": documents,
            "errors": {},
            **page(
                title="Documentos",
                section="documents",
                case_id=case_id,
                case_title=case_title,
                crumbs=case_crumbs(case_id, case_title, Crumb("Documentos")),
            ),
        },
        status_code=status_code,
    )


def _panel(
    request: Request,
    case_id: str,
    *,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
):
    with request.app.state.session_factory() as session:
        documents = documents_overview(session, case_id)
    return _templates(request).TemplateResponse(
        request=request,
        name="documents/list.html",
        context={
            "case_id": case_id,
            "documents": documents,
            "errors": errors or {},
        },
        status_code=status_code,
    )


def _not_found(request: Request):
    return _templates(request).TemplateResponse(
        request=request,
        name="errors/404.html",
        context={"message": "No encontrado en este caso."},
        status_code=404,
    )


@router.get("/cases/{case_id}/documents", response_class=HTMLResponse)
def list_documents_view(request: Request, case_id: str):
    try:
        resolved_id, case_title = _case_header(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)
    if _is_htmx(request):
        return _panel(request, case_id)
    return _section(request, resolved_id, case_title)


@router.post("/cases/{case_id}/documents", response_class=HTMLResponse)
def upload_document_view(
    request: Request,
    case_id: str,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()] = "",
    declared_version: Annotated[str, Form()] = "",
    declared_date: Annotated[str, Form()] = "",
):
    try:
        _resolve_scope(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)

    settings = request.app.state.settings
    try:
        upload = read_upload(file, settings.max_upload_bytes)
    except DocumentValidationError as exc:
        status = ERRORS.get(exc.code, ERRORS["validation_error"]).status
        return _panel(request, case_id, errors={"file": exc.message}, status_code=status)

    embedder = request.app.state.embedder_factory()
    index = request.app.state.index_factory()
    try:
        outcome = ingest_document(
            request.app.state.session_factory,
            settings,
            scope_key=f"case:{case_id}",
            case_id=case_id,
            origin="case_evidence",
            source_id=None,
            title=title.strip() or upload.filename,
            upload=upload,
            embedder=embedder,
            index=index,
            declared_version=declared_version.strip() or None,
            declared_date=declared_date.strip() or None,
        )
    finally:
        close = getattr(embedder, "close", None)
        if callable(close):
            close()

    if outcome.status == "duplicate":
        return _panel(
            request,
            case_id,
            errors={"file": outcome.message},
            status_code=409,
        )
    if outcome.status == "failed":
        return _panel(
            request,
            case_id,
            errors={"file": outcome.message},
            status_code=500,
        )

    if not _is_htmx(request):
        return RedirectResponse(url=f"/cases/{case_id}", status_code=303)
    return _panel(request, case_id, status_code=201)


@router.get(
    "/cases/{case_id}/documents/{document_id}",
    response_class=HTMLResponse,
)
def document_detail_view(request: Request, case_id: str, document_id: str):
    try:
        scope = _resolve_scope(request, case_id)
        with request.app.state.session_factory() as session:
            case = require_case(session, scope)
            document = get_document(session, scope, document_id)
            versions = list_versions(session, document.id)
            latest = versions[0] if versions else None
            chunks = list_chunks(session, latest.id) if latest is not None else []
            view = {
                "id": document.id,
                "title": document.title,
                "origin": document.origin,
                "created_at": document.created_at,
                "current_version_id": document.current_version_id,
            }
            case_title = case.title
    except CaseNotFoundError, DocumentNotFound:
        return _not_found(request)

    return _templates(request).TemplateResponse(
        request=request,
        name="documents/detail.html",
        context={
            "case_id": case_id,
            "document": view,
            "versions": versions,
            "latest": latest,
            "chunks": chunks,
            **page(
                title=view["title"],
                section="documents",
                case_id=case_id,
                case_title=case_title,
                crumbs=(
                    Crumb("Casos", "/cases"),
                    Crumb(case_title, f"/cases/{case_id}"),
                    Crumb("Documentos", f"/cases/{case_id}/documents"),
                    Crumb(view["title"]),
                ),
            ),
        },
    )


@router.post(
    "/cases/{case_id}/documents/{document_id}/retry",
    response_class=HTMLResponse,
)
def retry_document_view(request: Request, case_id: str, document_id: str):
    try:
        scope = _resolve_scope(request, case_id)
    except CaseNotFoundError:
        return _not_found(request)

    embedder = request.app.state.embedder_factory()
    index = request.app.state.index_factory()
    try:
        outcome = retry_ingestion(
            request.app.state.session_factory,
            request.app.state.settings,
            scope=scope,
            document_id=document_id,
            embedder=embedder,
            index=index,
        )
    except DocumentNotFound:
        return _not_found(request)
    except DocumentConflict as exc:
        return _panel(
            request,
            case_id,
            errors={"file": str(exc)},
            status_code=409,
        )
    finally:
        close = getattr(embedder, "close", None)
        if callable(close):
            close()

    status = 500 if outcome.status == "failed" else 202
    if not _is_htmx(request) and status != 500:
        return RedirectResponse(
            url=f"/cases/{case_id}/documents/{document_id}",
            status_code=303,
        )
    return _panel(
        request,
        case_id,
        errors={"file": outcome.message} if outcome.status == "failed" else {},
        status_code=status,
    )


def _highlight(text: str, quote: str) -> Markup:
    """Resalta la cita sobre el texto original, tolerando espacios normalizados."""
    span = find_quote_span(text, quote)
    if span is None:
        return Markup(str(escape(text)))
    return Markup(
        str(escape(text[: span.start]))
        + '<mark class="bg-yellow-200">'
        + str(escape(text[span.start : span.end]))
        + "</mark>"
        + str(escape(text[span.end :]))
    )


@router.get(
    "/cases/{case_id}/documents/{document_id}/versions/{version_id}/fragments/{chunk_id}",
    response_class=HTMLResponse,
)
def fragment_view(
    request: Request,
    case_id: str,
    document_id: str,
    version_id: str,
    chunk_id: str,
):
    try:
        scope = _resolve_scope(request, case_id)
        with request.app.state.session_factory() as session:
            document = session.get(Document, document_id)
            if document is None:
                raise DocumentNotFound(document_id)
            # Una cita puede señalar evidencia del caso o el corpus público; el
            # alcance autorizado sigue siendo el caso de la ruta.
            if document.origin == "public_corpus":
                if document.case_id is not None:
                    raise DocumentNotFound(document_id)
            elif document.case_id != scope.case_id:
                raise DocumentNotFound(document_id)
            version = session.get(DocumentVersion, version_id)
            if version is None or version.document_id != document.id:
                raise DocumentNotFound(version_id)
            chunk = session.get(DocumentChunk, chunk_id)
            if chunk is None or chunk.version_id != version.id:
                raise DocumentNotFound(chunk_id)
            text_html = _highlight(chunk.text, request.query_params.get("quote", ""))
            view = {
                "chunk_id": chunk.id,
                "page": chunk.page_start,
                "section": chunk.section,
                "locator": chunk.locator,
                "token_count": chunk.token_count,
            }
            document_view = {
                "id": document.id,
                "title": document.title,
                "origin": document.origin,
            }
            case_title = require_case(session, scope).title
    except CaseNotFoundError, DocumentNotFound:
        return _not_found(request)

    # El destino de regreso lo decide el servidor a partir de un valor conocido;
    # nunca se redirige a una URL aportada por el cliente.
    back_url = None
    if request.query_params.get("from") == "consultation":
        back_url = f"/cases/{case_id}/chat"

    return _templates(request).TemplateResponse(
        request=request,
        name="documents/fragment.html",
        context={
            "case_id": case_id,
            "document": document_view,
            "version": version,
            "fragment": view,
            "text_html": text_html,
            "back_url": back_url,
            **page(
                title="Fragmento",
                section="documents",
                case_id=case_id,
                case_title=case_title,
                crumbs=(
                    Crumb("Casos", "/cases"),
                    Crumb(case_title, f"/cases/{case_id}"),
                    *(
                        (
                            Crumb("Documentos", f"/cases/{case_id}/documents"),
                            Crumb(document_view["title"]),
                        )
                        if document_view["origin"] == "case_evidence"
                        else (Crumb(document_view["title"]),)
                    ),
                    Crumb("Fragmento"),
                ),
            ),
        },
    )
