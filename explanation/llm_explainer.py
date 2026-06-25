"""
Capa de explicación: llamada a la API de Anthropic.
===================================================

Toma el AssetResult estructurado, lo serializa y pide al modelo un resumen en
español honesto y acotado por SYSTEM_PROMPT. Maneja errores de red/clave (falla
explícito si falta ANTHROPIC_API_KEY).
"""

from __future__ import annotations

from config.settings import SETTINGS, require_key
from explanation.prompts import SYSTEM_PROMPT, build_user_message
from modeling.results import AssetResult


class ExplanationError(RuntimeError):
    """Error generando el resumen en lenguaje natural."""


def generate_summary(result: AssetResult, *, max_tokens: int = 1500) -> str:
    """Genera el resumen en español del análisis de un activo.

    Parameters
    ----------
    result : AssetResult con la lista estructurada de variables y validaciones.
    max_tokens : tope de tokens de salida del modelo.

    Returns
    -------
    El texto del resumen.

    Raises
    ------
    ExplanationError ante fallas de red/API o respuesta vacía.
    ConfigError (vía require_key) si falta ANTHROPIC_API_KEY.
    """
    return generate_summary_from_dict(result.to_dict(), max_tokens=max_tokens)


def generate_summary_from_dict(result_dict: dict, *, max_tokens: int = 1500) -> str:
    """Igual que `generate_summary` pero a partir del dict del AssetResult.

    Útil para la UI: permite cachear por el dict (hashable) sin depender del objeto.
    """
    api_key = require_key(
        SETTINGS.anthropic_api_key,
        "ANTHROPIC_API_KEY",
        "Conseguila en https://console.anthropic.com/ (sección API Keys).",
    )

    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise ExplanationError(
            "El paquete 'anthropic' no está instalado. "
            "Ejecutá: pip install -r requirements.txt"
        ) from exc

    client = anthropic.Anthropic(api_key=api_key)

    # Pasamos SOLO el objeto estructurado (las variables que el modelo encontró).
    user_message = build_user_message(result_dict)

    try:
        response = client.messages.create(
            model=SETTINGS.anthropic_model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as exc:
        raise ExplanationError(
            f"Error llamando a la API de Anthropic: {exc}"
        ) from exc
    except Exception as exc:  # red, timeout, etc.
        raise ExplanationError(
            f"Error inesperado generando el resumen: {exc}"
        ) from exc

    # El modelo puede rehusar por seguridad; lo manejamos explícito.
    if response.stop_reason == "refusal":
        raise ExplanationError(
            "El modelo rechazó la solicitud por motivos de seguridad. "
            "Revisá el contenido enviado."
        )

    # Concatenamos los bloques de texto de la respuesta.
    partes = [b.text for b in response.content if b.type == "text"]
    texto = "\n".join(p for p in partes if p).strip()

    if not texto:
        raise ExplanationError("La API devolvió una respuesta vacía.")

    return texto
