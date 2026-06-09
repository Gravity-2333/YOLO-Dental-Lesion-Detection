from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
import ipaddress
import json
import os
from pathlib import Path
import re
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
DEFAULT_AI_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_AI_MODEL = "deepseek-chat"
DEFAULT_AI_KEY_ENV = "DEEPSEEK_API_KEY"
DEFAULT_AI_PROMPT = (
    "你是牙科影像检测结果解释助手，服务对象可能是牙科医生、口腔科助理或普通用户。"
    "你只能基于用户提供的 YOLO 检测结果文本生成辅助建议，不接收、不分析、不猜测牙片图片本身。"
    "必须在建议开头包含原句：本结果仅供辅助参考，不能替代专业牙科医生诊断。"
    "不要输出最终诊断，不要给处方，不要给具体药物剂量，不要建议自行用药，也不要使用“确诊、一定、必须治疗”等绝对表达。"
    "请按检测类别、数量、置信度和检测框位置描述需要关注的区域，并把建议限制在复查确认、预约就医、携带原始影像和检测结果沟通、观察症状、保持口腔卫生、定期口腔检查等范围。"
    "如果检测结果为空，请说明模型未检测到明确目标框，但仍建议结合症状、原始影像质量和专业牙科检查复核。"
    "输出应简洁、分条、中文，不超过 260 字。"
)
CLASS_ADVICE = {
    "Caries": "疑似龋坏相关区域。建议关注该区域是否有冷热刺激痛、食物嵌塞或颜色改变，并预约牙科检查确认。",
    "Periapical Lesion": "疑似根尖周相关异常区域。建议结合疼痛、咬合不适、牙龈肿胀等症状，由牙科医生复查根尖区域。",
    "Impacted": "疑似阻生牙相关区域。建议关注局部清洁难度、反复发炎或邻牙受影响风险，并咨询牙科医生评估。",
}


def _normalize_class_name(name: str) -> str:
    """将类别名统一为内部建议匹配使用的规范名称。

    UI 和导出仍保留模型返回的原始类别名；这里只消除空格、下划线、
    短横线、大小写等差异，避免专属建议静默回退成泛用建议。
    """
    token = re.sub(r"[^a-z0-9]+", " ", str(name).casefold()).strip()
    token = re.sub(r"\s+", " ", token)
    aliases = {
        "caries": "Caries",
        "periapical lesion": "Periapical Lesion",
        "periapical lesions": "Periapical Lesion",
        "impacted": "Impacted",
        "impacted tooth": "Impacted",
        "impacted teeth": "Impacted",
    }
    return aliases.get(token, str(name).replace("_", " ").strip())


@dataclass
class AiSettings:
    enabled: bool = False
    base_url: str = DEFAULT_AI_BASE_URL
    model: str = DEFAULT_AI_MODEL
    key_mode: str = "环境变量"
    api_key: str = DEFAULT_AI_KEY_ENV
    save_api_key: bool = False
    auto_save: bool = True
    storage_dir: str = str(APP_HOME)
    custom_prompt: str = DEFAULT_AI_PROMPT
    model_mode: str = "单模型"
    enable_compare: bool = True
    show_summary: bool = False
    model_dir: str = str(PROJECT_ROOT / "models")
    primary_model_path: str = str(
        PROJECT_ROOT
        / "models"
        / "final_candidates"
        / "yolov8m_c2f_faster_lite_1280_full"
        / "weights"
        / "best.pt"
    )
    compare_model_path: str = str(
        PROJECT_ROOT
        / "models"
        / "final_candidates"
        / "yolov8m_1280_full"
        / "weights"
        / "best.pt"
    )


def storage_root(storage_dir: str | None = None) -> Path:
    return Path(storage_dir).expanduser() if storage_dir else APP_HOME


def conversation_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "conversations"


def export_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "exports"


def case_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "cases"


def report_dir(storage_dir: str | None = None) -> Path:
    return storage_root(storage_dir) / "reports"


def ensure_app_dirs(storage_dir: str | None = None) -> Path:
    APP_HOME.mkdir(parents=True, exist_ok=True)
    root = storage_root(storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    conversation_dir(str(root)).mkdir(parents=True, exist_ok=True)
    export_dir(str(root)).mkdir(parents=True, exist_ok=True)
    case_dir(str(root)).mkdir(parents=True, exist_ok=True)
    report_dir(str(root)).mkdir(parents=True, exist_ok=True)
    return root


def _unique_corrupt_settings_backup() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = CONFIG_PATH.with_name(f"{CONFIG_PATH.stem}.{stamp}.corrupt{CONFIG_PATH.suffix}")
    counter = 1
    while backup.exists():
        backup = CONFIG_PATH.with_name(
            f"{CONFIG_PATH.stem}.{stamp}_{counter:02d}.corrupt{CONFIG_PATH.suffix}"
        )
        counter += 1
    return backup


def load_settings() -> AiSettings:
    if not CONFIG_PATH.exists():
        return AiSettings()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # 保留损坏文件的备份，方便用户恢复
        try:
            corrupt_backup = _unique_corrupt_settings_backup()
            CONFIG_PATH.replace(corrupt_backup)
        except OSError:
            pass
        return AiSettings()
    if not isinstance(data, dict):
        return AiSettings()
    allowed = {field.name for field in fields(AiSettings)}
    defaults = AiSettings().__dict__

    # 类型校验：防止损坏的 settings.json 在模块导入阶段导致 Path(123) 等 TypeError
    _STRING_FIELDS = {
        "base_url", "model", "key_mode", "api_key",
        "custom_prompt", "model_mode",
    }
    _PATH_FIELDS = {
        "storage_dir", "model_dir",
        "primary_model_path", "compare_model_path",
    }
    _BOOL_FIELDS = {"enabled", "save_api_key", "auto_save", "enable_compare", "show_summary"}

    filtered: dict[str, Any] = {}
    for key, value in data.items():
        if key not in allowed:
            continue
        if key in _STRING_FIELDS:
            if isinstance(value, (int, float, bool)):
                filtered[key] = str(value)
            elif isinstance(value, str):
                filtered[key] = value
            # 非字符串/数字/布尔类型（列表、字典等）丢弃，使用默认值
        elif key in _PATH_FIELDS:
            if isinstance(value, str) and value.strip():
                filtered[key] = value
        elif key in _BOOL_FIELDS:
            if isinstance(value, bool):
                filtered[key] = value
            elif isinstance(value, str):
                filtered[key] = value.lower() in {"true", "1", "yes", "on"}
            elif isinstance(value, (int, float)):
                filtered[key] = bool(value)
            # 其他类型丢弃
        else:
            filtered[key] = value
    if filtered.get("key_mode") not in {"环境变量", "直接 Key 值"}:
        filtered.pop("key_mode", None)
    if filtered.get("model_mode") not in {"单模型", "对比模型"}:
        filtered.pop("model_mode", None)
    return AiSettings(**{**defaults, **filtered})


def save_settings(settings: AiSettings) -> Path:
    previous = load_settings() if CONFIG_PATH.exists() else AiSettings()
    migrate_storage(previous.storage_dir, settings.storage_dir)
    ensure_app_dirs(settings.storage_dir)
    data = settings.__dict__.copy()
    if settings.key_mode == "直接 Key 值" and not settings.save_api_key:
        data["api_key"] = ""

    # 原子写入：先写临时文件，成功后再替换，防止写入中断导致配置损坏
    content = json.dumps(data, ensure_ascii=False, indent=2)
    tmp_path = CONFIG_PATH.with_suffix(".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(CONFIG_PATH)
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
            suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            shutil.move(str(child), str(target / f"{child.stem}_{suffix}{child.suffix}"))


def migrate_storage(old_storage_dir: str | None, new_storage_dir: str | None) -> None:
    old_root = storage_root(old_storage_dir).resolve()
    new_root = storage_root(new_storage_dir).resolve()
    if old_root == new_root or not old_root.exists() or not old_root.is_dir():
        return
    if old_root in new_root.parents:
        # 新目录位于旧目录内部时，直接搬迁旧目录会形成“目录搬进自己”的递归移动。
        # 这种情况下保留旧内容不动，新目录由后续 ensure_app_dirs 创建。
        return

    if old_root == APP_HOME.resolve():
        for child_name in ("conversations", "exports", "cases", "reports"):
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


def normalize_base_url(base_url: str) -> str:
    value = (base_url or "").strip().rstrip("/") or DEFAULT_AI_BASE_URL
    if not value.lower().startswith(("http://", "https://")):
        host = value.split("/")[0].split(":")[0].lower()
        scheme = "http" if host in {"localhost", "127.0.0.1", "::1"} else "https"
        try:
            if ipaddress.ip_address(host).is_private:
                scheme = "http"
        except ValueError:
            pass
        value = f"{scheme}://{value}"
    lowered = value.lower()
    for suffix in ("/v1/chat/completions", "/chat/completions"):
        if lowered.endswith(suffix):
            value = value[: -len(suffix)]
            lowered = value.lower()
            break
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
    value = settings.api_key.strip()
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

        normalized = _normalize_class_name(label)
        advice = CLASS_ADVICE.get(
            normalized,
            CLASS_ADVICE.get(
                label,
                "检测到模型标记的可疑区域。建议结合原始影像、症状和医生检查进行复核。",
            ),
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
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S_%f")  # 微秒级精度防止同秒覆盖
    path = target_dir / f"dental_chat_{stamp}.json"
    # 若极端情况下仍存在同名文件，追加序号
    if path.exists():
        counter = 1
        while path.exists():
            path = target_dir / f"dental_chat_{stamp}_{counter:02d}.json"
            counter += 1
    payload = {
        "created_at": now.isoformat(timespec="seconds"),
        "safety_notice": SAFETY_NOTICE,
        "messages": messages,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
