from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

from .ai_defaults import DEFAULT_AI_BASE_URL
from .settings_store import AiSettings


def _base_url_origin(base_url: str) -> str:
    value = str(base_url or "").strip()
    parsed = urlparse(value if "://" in value else f"//{value}")
    if parsed.hostname:
        return parsed.hostname.strip("[]")
    netloc = (parsed.netloc or value.split("/", 1)[0]).split("@")[-1]
    if netloc.startswith("[") and "]" in netloc:
        return netloc[1 : netloc.index("]")]
    if netloc == "::1" or netloc.startswith("::1:"):
        return "::1"
    return netloc.split(":")[0].strip("[]")


def _normalize_ipv6_netloc(value: str) -> str:
    netloc, sep, suffix = value.partition("/")
    if netloc.startswith("["):
        return value
    if netloc == "::1":
        return f"[::1]{sep}{suffix}" if sep else "[::1]"
    if netloc.startswith("::1:"):
        port = netloc.removeprefix("::1:")
        if port.isdigit():
            normalized = f"[::1]:{port}"
            return f"{normalized}{sep}{suffix}" if sep else normalized
    return value


def normalize_base_url(base_url: str) -> str:
    value = (base_url or "").strip().rstrip("/") or DEFAULT_AI_BASE_URL
    if not value.lower().startswith(("http://", "https://")):
        value = _normalize_ipv6_netloc(value)
        host = _base_url_origin(value).lower()
        scheme = "http" if host in {"localhost", "127.0.0.1", "::1"} else "https"
        try:
            if ipaddress.ip_address(host).is_private:
                scheme = "http"
        except ValueError:
            pass
        value = f"{scheme}://{value}"
    lowered = value.lower()
    if lowered.endswith("/chat/completions"):
        value = value[: -len("/chat/completions")]
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc and not parsed.path.strip("/"):
        value = f"{value}/v1"
    return value.rstrip("/")


def is_private_base_url(base_url: str) -> bool:
    host = _base_url_origin(base_url).lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def resolve_api_key(settings: AiSettings) -> str:
    value = str(settings.api_key or "").strip()
    if settings.key_mode == "环境变量":
        return os.getenv(value, "") if value else ""
    return value


def validate_ai_request(settings: AiSettings) -> tuple[bool, str, str]:
    api_key = resolve_api_key(settings)
    if api_key:
        return True, api_key, ""
    if is_private_base_url(normalize_base_url(settings.base_url)):
        return True, "EMPTY", ""
    return False, "", "公网 API 地址需要填写 API Key，或在环境变量模式中填写环境变量名。"


AI_REQUEST_TIMEOUT = 30.0  # 秒，OpenAI-compatible API 请求超时


def _client(settings: AiSettings, api_key: str) -> OpenAI:
    from openai import OpenAI

    return OpenAI(
        base_url=normalize_base_url(settings.base_url),
        api_key=api_key,
        timeout=AI_REQUEST_TIMEOUT,
        max_retries=1,
    )


def _friendly_ai_error(exc: Exception) -> ValueError:
    name = exc.__class__.__name__
    text = str(exc)
    if name in {"APITimeoutError", "TimeoutException"} or "timed out" in text.lower():
        return ValueError("AI 服务响应超时，请检查网络或接口配置。")
    if name in {"APIConnectionError", "ConnectError", "ConnectTimeout"}:
        return ValueError("无法连接 AI 服务，请检查网络、Base URL 或代理配置。")
    return ValueError(text or "AI 服务请求失败，请检查接口配置。")


def chat_completion(
    settings: AiSettings,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 500,
) -> str:
    ok, api_key, error = validate_ai_request(settings)
    if not ok:
        raise ValueError(error)
    try:
        response = _client(settings, api_key).chat.completions.create(
            model=settings.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        raise _friendly_ai_error(exc) from exc
    return response.choices[0].message.content or ""


def test_chat_completion(settings: AiSettings) -> str:
    content = chat_completion(
        settings,
        messages=[{"role": "user", "content": "请只回复 OK"}],
        temperature=0,
        max_tokens=8,
    ).strip()
    if not content:
        raise ValueError("接口返回为空。")
    return f"测试成功：{content}"
