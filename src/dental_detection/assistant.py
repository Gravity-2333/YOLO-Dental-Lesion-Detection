from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import ipaddress
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import PROJECT_ROOT

APP_DIR_NAME = "YOLO-Dental-Lesion-Detection"


def _resolve_app_home() -> Path:
    primary = Path.home() / APP_DIR_NAME
    try:
        primary.mkdir(parents=True, exist_ok=True)
        probe = primary / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return primary
    except OSError:
        fallback = PROJECT_ROOT.parent / f"{APP_DIR_NAME}-user-data"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


APP_HOME = _resolve_app_home()
CONFIG_PATH = APP_HOME / "settings.json"
CONVERSATION_DIR = APP_HOME / "conversations"
SAFETY_NOTICE = "结果仅供辅助参考，不能替代专业牙科医生诊断。"


@dataclass
class AiSettings:
    enabled: bool = False
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    key_mode: str = "环境变量"
    api_key: str = ""
    save_api_key: bool = False
    auto_save: bool = True
    storage_dir: str = str(CONVERSATION_DIR)


def ensure_app_dirs(storage_dir: str | None = None) -> Path:
    APP_HOME.mkdir(parents=True, exist_ok=True)
    target = Path(storage_dir).expanduser() if storage_dir else CONVERSATION_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def load_settings() -> AiSettings:
    if not CONFIG_PATH.exists():
        return AiSettings()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AiSettings()
    return AiSettings(**{**AiSettings().__dict__, **data})


def save_settings(settings: AiSettings) -> Path:
    ensure_app_dirs(settings.storage_dir)
    data = settings.__dict__.copy()
    if settings.key_mode == "直接 Key 值" and not settings.save_api_key:
        data["api_key"] = ""
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return CONFIG_PATH


def _base_url_origin(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc.split("@")[-1].split(":")[0]
    return base_url.split("/")[0].split(":")[0]


def is_private_base_url(base_url: str) -> bool:
    host = _base_url_origin(base_url).lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def resolve_api_key(settings: AiSettings) -> str:
    value = settings.api_key.strip()
    if settings.key_mode == "环境变量":
        return os.getenv(value, "") if value else ""
    return value


def validate_ai_request(settings: AiSettings) -> tuple[bool, str, str]:
    api_key = resolve_api_key(settings)
    if api_key:
        return True, api_key, ""
    if is_private_base_url(settings.base_url):
        return True, "EMPTY", ""
    return False, "", "公网 API 地址需要填写 API Key，或在环境变量模式中填写环境变量名。"


def _client(settings: AiSettings, api_key: str) -> OpenAI:
    from openai import OpenAI

    return OpenAI(base_url=settings.base_url.rstrip("/"), api_key=api_key)


def chat_completion(
    settings: AiSettings,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 500,
) -> str:
    ok, api_key, error = validate_ai_request(settings)
    if not ok:
        raise ValueError(error)
    response = _client(settings, api_key).chat.completions.create(
        model=settings.model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
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


def detection_prompt(detections: list[dict[str, Any]]) -> list[dict[str, str]]:
    summary = json.dumps(detections, ensure_ascii=False, indent=2)
    return [
        {
            "role": "system",
            "content": (
                "你是牙科影像检测结果解释助手。只能基于 YOLO 检测结果文本给出辅助建议。"
                "必须声明结果仅供辅助参考，不能替代专业牙科医生诊断。"
                "不要输出最终诊断，不要给处方，不要给具体药物剂量。"
                "建议范围限于复查、就医、关注区域、保持口腔卫生和携带影像资料咨询医生。"
            ),
        },
        {
            "role": "user",
            "content": f"请根据以下 YOLO 牙齿病变检测结果生成简洁建议：\n{summary}",
        },
    ]


def default_advice(detections: list[dict[str, Any]]) -> str:
    if not detections:
        return (
            f"{SAFETY_NOTICE}\n\n"
            "本次未检测到明确的目标病变框。若仍有疼痛、肿胀、冷热刺激痛或影像可疑区域，"
            "建议携带原始牙片咨询专业牙科医生复核。日常请保持刷牙、牙线和定期口腔检查。"
        )

    counts: dict[str, int] = {}
    for det in detections:
        label = str(det.get("class", "未知区域"))
        counts[label] = counts.get(label, 0) + 1
    count_text = "，".join(f"{name} {count} 处" for name, count in counts.items())
    high_conf = max(float(det.get("confidence", 0)) for det in detections)
    return (
        f"{SAFETY_NOTICE}\n\n"
        f"检测结果提示需要关注的区域包括：{count_text}。最高置信度约为 {high_conf:.2f}。"
        "建议结合原始影像和口腔症状，由专业牙科医生复查检测框附近区域；如存在疼痛、肿胀、"
        "咬合不适或反复发炎，应尽快就诊。平时注意清洁牙间隙，减少高糖饮食，并保留本次检测结果"
        "供医生参考。"
    )


def save_conversation(messages: list[dict[str, str]], storage_dir: str | None = None) -> Path:
    target_dir = ensure_app_dirs(storage_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = target_dir / f"dental_chat_{stamp}.json"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "safety_notice": SAFETY_NOTICE,
        "messages": messages,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
