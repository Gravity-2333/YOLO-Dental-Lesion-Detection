from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import ipaddress
import json
import os
from pathlib import Path
import shutil
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
SAFETY_NOTICE = "本结果仅供辅助参考，不能替代专业牙科医生诊断。"
DEFAULT_AI_PROMPT = (
    "你是牙科影像检测结果解释助手。请只基于 YOLO 检测结果文本生成辅助建议，"
    "不要声称已经完成诊断。必须包含“本结果仅供辅助参考，不能替代专业牙科医生诊断。”"
    "不要给处方，不要给具体药物剂量，不要建议自行用药。"
    "建议应聚焦于复查、就医沟通、关注检测框附近区域、保持口腔卫生、携带原始影像和检测结果咨询专业牙科医生。"
    "如果检测结果为空，请说明未检测到明确目标框，但仍建议结合症状和医生检查复核。"
)
CLASS_ADVICE = {
    "Caries": "疑似龋坏相关区域。建议关注该区域是否有冷热刺激痛、食物嵌塞或颜色改变，并预约牙科检查确认。",
    "Periapical_Lesion": "疑似根尖周相关异常区域。建议结合疼痛、咬合不适、牙龈肿胀等症状，由牙科医生复查根尖区域。",
    "Impacted": "疑似阻生牙相关区域。建议关注局部清洁难度、反复发炎或邻牙受影响风险，并咨询牙科医生评估。",
}


@dataclass
class AiSettings:
    enabled: bool = False
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    key_mode: str = "环境变量"
    api_key: str = ""
    save_api_key: bool = False
    auto_save: bool = True
    storage_dir: str = str(APP_HOME)
    custom_prompt: str = DEFAULT_AI_PROMPT


def storage_root(storage_dir: str | None = None) -> Path:
    return Path(storage_dir).expanduser() if storage_dir else APP_HOME


def conversation_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "conversations"


def export_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "exports"


def ensure_app_dirs(storage_dir: str | None = None) -> Path:
    APP_HOME.mkdir(parents=True, exist_ok=True)
    root = storage_root(storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    conversation_dir(str(root)).mkdir(parents=True, exist_ok=True)
    export_dir(str(root)).mkdir(parents=True, exist_ok=True)
    return root


def load_settings() -> AiSettings:
    if not CONFIG_PATH.exists():
        return AiSettings()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AiSettings()
    return AiSettings(**{**AiSettings().__dict__, **data})


def save_settings(settings: AiSettings) -> Path:
    previous = load_settings() if CONFIG_PATH.exists() else AiSettings()
    migrate_storage(previous.storage_dir, settings.storage_dir)
    ensure_app_dirs(settings.storage_dir)
    data = settings.__dict__.copy()
    if settings.key_mode == "直接 Key 值" and not settings.save_api_key:
        data["api_key"] = ""
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return CONFIG_PATH


def _is_empty_dir(path: Path) -> bool:
    return path.exists() and path.is_dir() and not any(path.iterdir())


def _move_contents(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        destination = target / child.name
        if child.is_dir() and destination.exists() and destination.is_dir():
            _move_contents(child, destination)
            if _is_empty_dir(child):
                child.rmdir()
        elif not destination.exists():
            shutil.move(str(child), str(destination))
        else:
            suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.move(str(child), str(target / f"{child.stem}_{suffix}{child.suffix}"))


def migrate_storage(old_storage_dir: str | None, new_storage_dir: str | None) -> None:
    old_root = storage_root(old_storage_dir).resolve()
    new_root = storage_root(new_storage_dir).resolve()
    if old_root == new_root or not old_root.exists() or not old_root.is_dir():
        return

    if old_root == APP_HOME.resolve():
        for child_name in ("conversations", "exports"):
            source = old_root / child_name
            if source.exists() and source.is_dir():
                _move_contents(source, new_root / child_name)
                if _is_empty_dir(source):
                    source.rmdir()
        return

    if old_root.name == "conversations":
        _move_contents(old_root, conversation_dir(str(new_root)))
        if _is_empty_dir(old_root):
            old_root.rmdir()
        return

    if old_root.name == "exports":
        _move_contents(old_root, export_dir(str(new_root)))
        if _is_empty_dir(old_root):
            old_root.rmdir()
        return

    if _is_empty_dir(old_root):
        old_root.rmdir()
        return
    _move_contents(old_root, new_root)
    if _is_empty_dir(old_root):
        old_root.rmdir()


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


def detection_prompt(
    detections: list[dict[str, Any]], custom_prompt: str | None = None
) -> list[dict[str, str]]:
    summary = json.dumps(detections, ensure_ascii=False, indent=2)
    system_prompt = (custom_prompt or "").strip() or DEFAULT_AI_PROMPT
    return [
        {
            "role": "system",
            "content": system_prompt,
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

    grouped: dict[str, list[dict[str, Any]]] = {}
    for det in detections:
        label = str(det.get("class", "未知区域"))
        grouped.setdefault(label, []).append(det)

    sections = [SAFETY_NOTICE]
    for label, items in sorted(grouped.items()):
        confidences = [float(item.get("confidence", 0) or 0) for item in items]
        high_conf = max(confidences)
        if high_conf >= 0.70:
            level = "重点关注"
        elif high_conf >= 0.40:
            level = "建议复查确认"
        else:
            level = "低置信度，仅供参考"

        advice = CLASS_ADVICE.get(
            label,
            "检测到模型标记的可疑区域。建议结合原始影像、症状和医生检查进行复核。",
        )
        sections.append(
            f"{label}：{level}。共 {len(items)} 处，最高置信度约 {high_conf:.2f}。{advice}"
        )

    sections.append(
        "请保留原始影像和检测结果，必要时携带给专业牙科医生复查。"
        "本建议不构成最终诊断，不提供处方，也不提供具体药物剂量。"
    )
    return "\n\n".join(sections)


def save_conversation(messages: list[dict[str, str]], storage_dir: str | None = None) -> Path:
    ensure_app_dirs(storage_dir)
    target_dir = conversation_dir(storage_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = target_dir / f"dental_chat_{stamp}.json"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "safety_notice": SAFETY_NOTICE,
        "messages": messages,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
