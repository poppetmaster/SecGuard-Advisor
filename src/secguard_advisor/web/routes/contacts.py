"""Contact, verification and case-authorization routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from secguard_advisor.cases.scope import CaseNotFoundError, resolve_case_scope
from secguard_advisor.db.models import Case, ContactCaseLink
from secguard_advisor.notifications.channels.base import TelegramError
from secguard_advisor.notifications.channels.telegram import build_transport
from secguard_advisor.notifications.contacts import (
    authorize_case,
    create_contact,
    list_contacts,
    mask_chat_id,
    set_active,
    set_consent,
    set_contact_status,
)
from secguard_advisor.notifications.errors import NotificationError
from secguard_advisor.notifications.verification import confirm_verification, start_verification
from secguard_advisor.web.navigation import Crumb, page

router = APIRouter(tags=["contacts"])


def _templates(request: Request):
    return request.app.state.templates


def _transport(request: Request):
    if request.app.state.telegram_transport is None:
        request.app.state.telegram_transport = build_transport(request.app.state.settings)
    return request.app.state.telegram_transport


def _contacts_view(
    session,
    request: Request,
    *,
    error: str | None = None,
    message: str | None = None,
    status: int = 200,
    case_id: str | None = None,
):
    contacts = []
    all_cases = list(session.scalars(select(Case).order_by(Case.title)))
    case_titles = {item.id: item.title for item in all_cases}
    for contact in list_contacts(session):
        links = list(
            session.query(ContactCaseLink).filter(ContactCaseLink.contact_id == contact.id)
        )
        contacts.append(
            {
                "id": contact.id,
                "alias": contact.alias,
                "chat_type": contact.chat_type,
                "chat_type_label": {
                    "private": "Privado",
                    "group": "Grupo",
                    "supergroup": "Supergrupo",
                    "channel": "Canal",
                }.get(contact.chat_type, contact.chat_type),
                "status_label": {
                    "unverified": "Sin verificar",
                    "verified": "Verificado",
                    "revoked": "Revocado",
                    "disabled": "Desactivado",
                }.get(contact.status, contact.status),
                "consent_label": {
                    "pending": "Pendiente",
                    "granted": "Otorgado",
                    "revoked": "Revocado",
                }.get(contact.consent_status, contact.consent_status),
                "masked_chat": mask_chat_id(contact.chat_id),
                "status": contact.status,
                "consent_status": contact.consent_status,
                "active": contact.active,
                "verified_at": contact.verified_at,
                "verified_by": contact.verified_by,
                "cases": [link.case_id for link in links if link.authorized],
                "case_titles": [
                    case_titles.get(link.case_id, link.case_id) for link in links if link.authorized
                ],
            }
        )
    cases = list(session.scalars(__import__("sqlalchemy").select(Case).order_by(Case.title)))
    return _templates(request).TemplateResponse(
        request=request,
        name="contacts/index.html",
        context={
            "contacts": contacts,
            "cases": cases,
            "case_id": case_id,
            "error": error,
            "message": message,
            **page(
                title="Contactos y canales",
                section="contacts",
                crumbs=(Crumb("Administración"), Crumb("Contactos y canales")),
            ),
        },
        status_code=status,
    )


@router.get("/settings/contacts", response_class=HTMLResponse)
def contacts_index(request: Request):
    with request.app.state.session_factory() as session:
        return _contacts_view(session, request)


@router.post("/settings/contacts", response_class=HTMLResponse)
def contacts_create(
    request: Request,
    alias: str = Form(""),
    chat_id: str = Form(""),
    chat_type: str = Form("private"),
):
    with request.app.state.session_factory() as session:
        try:
            contact = create_contact(session, alias=alias, chat_id=chat_id, chat_type=chat_type)
            session.commit()
        except NotificationError as exc:
            session.rollback()
            return _contacts_view(session, request, error=exc.message, status=422)
        return RedirectResponse(f"/settings/contacts?created={contact.id}", status_code=303)


@router.post("/settings/contacts/{contact_id}/verification", response_class=HTMLResponse)
def contacts_start_verification(request: Request, contact_id: str):
    with request.app.state.session_factory() as session:
        try:
            start_verification(session, contact_id=contact_id, transport=_transport(request))
            session.commit()
        except (NotificationError, TelegramError) as exc:
            session.rollback()
            return _contacts_view(session, request, error=exc.message, status=422)
        return _contacts_view(
            session, request, message="Código enviado. Pedí el código a quien controla el destino."
        )


@router.post("/settings/contacts/{contact_id}/verification/confirm", response_class=HTMLResponse)
def contacts_confirm_verification(
    request: Request,
    contact_id: str,
    code: str = Form(""),
    verified_by: str = Form(""),
):
    with request.app.state.session_factory() as session:
        try:
            confirm_verification(session, contact_id=contact_id, code=code, verified_by=verified_by)
            session.commit()
        except NotificationError as exc:
            session.rollback()
            return _contacts_view(session, request, error=exc.message, status=422)
        return _contacts_view(session, request, message="Contacto verificado.")


@router.post("/settings/contacts/{contact_id}/consent", response_class=HTMLResponse)
def contacts_consent(
    request: Request,
    contact_id: str,
    status: str = Form("granted"),
    declared_by: str = Form(""),
):
    with request.app.state.session_factory() as session:
        try:
            set_consent(session, contact_id, status, declared_by=declared_by)
            session.commit()
        except NotificationError as exc:
            session.rollback()
            return _contacts_view(session, request, error=exc.message, status=422)
        return _contacts_view(session, request, message="Consentimiento actualizado.")


@router.post("/settings/contacts/{contact_id}/status", response_class=HTMLResponse)
def contacts_status(
    request: Request,
    contact_id: str,
    status: str = Form("unverified"),
    active: str = Form(""),
):
    with request.app.state.session_factory() as session:
        try:
            set_contact_status(session, contact_id, status)
            set_active(session, contact_id, active == "on")
            session.commit()
        except NotificationError as exc:
            session.rollback()
            return _contacts_view(session, request, error=exc.message, status=422)
        return _contacts_view(session, request, message="Estado actualizado.")


@router.post("/cases/{case_id}/contacts/{contact_id}", response_class=HTMLResponse)
def contacts_case_link(
    request: Request,
    case_id: str,
    contact_id: str,
    authorized: str = Form("on"),
):
    with request.app.state.session_factory() as session:
        try:
            resolve_case_scope(session, case_id)
            authorize_case(
                session, contact_id=contact_id, case_id=case_id, authorized=authorized == "on"
            )
            session.commit()
        except (CaseNotFoundError, NotificationError) as exc:
            session.rollback()
            message = getattr(exc, "message", "No encontrado.")
            return _contacts_view(session, request, error=message, status=422, case_id=case_id)
        return _contacts_view(session, request, message="Vinculación actualizada.", case_id=case_id)
