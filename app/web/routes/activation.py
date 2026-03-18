from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.activation.client import ActivationAPIClient
from app.core.config import get_settings
from app.services.activation import ActivationFlowResult, ActivationFlowService, ActivationStatus

router = APIRouter(tags=["activation-site"])
templates = Jinja2Templates(directory="app/web/templates")

TRANSLATIONS = {
    "en": {
        "title": "Account Activation",
        "subtitle": "Activate your purchased product access in a few steps.",
        "cdk_label": "Activation code (CDK)",
        "cdk_hint": "Paste the code you received from the Telegram shop.",
        "token_label": "Token / account JSON",
        "token_hint": "Use either plain token text or JSON payload from your account panel.",
        "submit": "Start activation",
        "reset": "Reset form",
        "lang_toggle": "RU",
        "validation_cdk": "Activation code is required.",
        "validation_token": "Token/account input is required.",
        "validation_token_json": "Token JSON looks invalid. Please fix formatting.",
        "state_success": "Activation successful",
        "state_pending": "Activation in progress",
        "state_failed": "Activation failed",
    },
    "ru": {
        "title": "Активация аккаунта",
        "subtitle": "Активируйте доступ к купленному продукту за несколько шагов.",
        "cdk_label": "Код активации (CDK)",
        "cdk_hint": "Вставьте код, который вы получили в Telegram-магазине.",
        "token_label": "Токен / JSON аккаунта",
        "token_hint": "Можно ввести обычный токен или JSON из вашего аккаунта.",
        "submit": "Запустить активацию",
        "reset": "Очистить форму",
        "lang_toggle": "EN",
        "validation_cdk": "Введите код активации.",
        "validation_token": "Введите токен или JSON аккаунта.",
        "validation_token_json": "Похоже, JSON токена введен с ошибкой формата.",
        "state_success": "Активация успешна",
        "state_pending": "Активация выполняется",
        "state_failed": "Активация не выполнена",
    },
}


def get_activation_service() -> ActivationFlowService:
    settings = get_settings()
    client = ActivationAPIClient(
        base_url=settings.activation_api_base_url,
        timeout_seconds=settings.activation_api_timeout_seconds,
    )
    return ActivationFlowService(client)


@router.get("/", response_class=HTMLResponse)
def activation_page(request: Request, lang: str = "en") -> HTMLResponse:
    language = _normalize_lang(lang)
    return templates.TemplateResponse(
        request,
        "activation.html",
        {
            "lang": language,
            "t": TRANSLATIONS[language],
            "form": {"cdk": "", "token_input": ""},
            "form_errors": {},
            "flow_result": None,
        },
    )


@router.post("/", response_class=HTMLResponse)
async def activation_submit(
    request: Request,
    service: ActivationFlowService = Depends(get_activation_service),
) -> HTMLResponse:
    form_data = await request.form()
    cdk = str(form_data.get("cdk", "")).strip()
    token_input = str(form_data.get("token_input", "")).strip()
    language = _normalize_lang(str(form_data.get("lang", "en")))
    text = TRANSLATIONS[language]

    form = {"cdk": cdk, "token_input": token_input}
    form_errors: dict[str, str] = {}

    if not form["cdk"]:
        form_errors["cdk"] = text["validation_cdk"]
    if not form["token_input"]:
        form_errors["token_input"] = text["validation_token"]
    elif _looks_like_json(form["token_input"]):
        try:
            json.loads(form["token_input"])
        except json.JSONDecodeError:
            form_errors["token_input"] = text["validation_token_json"]

    flow_result: ActivationFlowResult | None = None
    if not form_errors:
        flow_result = service.run(cdk=form["cdk"], token_input=form["token_input"])

    return templates.TemplateResponse(
        request,
        "activation.html",
        {
            "lang": language,
            "t": text,
            "form": form,
            "form_errors": form_errors,
            "flow_result": flow_result,
            "status_labels": {
                ActivationStatus.SUCCESS: text["state_success"],
                ActivationStatus.PENDING: text["state_pending"],
                ActivationStatus.FAILED: text["state_failed"],
            },
        },
    )



def _looks_like_json(raw_value: str) -> bool:
    trimmed = raw_value.strip()
    return (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]"))

def _normalize_lang(lang: str) -> str:
    return "ru" if lang.lower() == "ru" else "en"
