from __future__ import annotations

from pathlib import Path


def friendly_error_message(exc: BaseException | str, context: str = "操作失败") -> str:
    raw = str(exc or "").strip()
    text = raw.casefold()

    if "cuda" in text and ("not available" in text or "不可用" in text or "invalid device" in text):
        return (
            "CUDA 设备当前不可用。\n\n"
            "可能原因：显卡驱动、CUDA 环境或 PyTorch GPU 版本未正确启用。\n\n"
            "建议处理：先在推理设备中选择 CPU；如果需要 GPU，请检查显卡驱动和 yolo 环境。"
        )
    if "ai 服务响应超时" in text or "timed out" in text or "timeout" in text:
        return (
            f"{context}：AI 服务响应超时。\n\n"
            "可能原因：网络不稳定、接口服务繁忙，或代理配置不可用。\n\n"
            "建议处理：稍后重试；如多次失败，请检查 Base URL、代理和网络连接。"
        )
    if "无法连接 ai 服务" in text or "connection" in text or "connect" in text:
        return (
            f"{context}：无法连接 AI 服务。\n\n"
            "可能原因：Base URL 填写错误、网络未连通，或本地代理没有生效。\n\n"
            "建议处理：检查 Base URL 和网络代理后，在设置中点击测试接口。"
        )
    if "no such file" in text or "not found" in text or "不存在" in text:
        return (
            f"{context}：相关文件不存在。\n\n"
            "可能原因：文件被移动、删除，或设置中的路径已经失效。\n\n"
            "建议处理：重新选择图片或模型文件，并在设置中点击测试模型确认路径有效。"
        )
    if "unsupported model format" in text or ("模型" in context and ("格式不支持" in context or "unsupported" in text)):
        return (
            f"{context}：模型文件格式不受支持。\n\n"
            "可能原因：选择的文件不是系统支持的 YOLO 权重或模型包。\n\n"
            "建议处理：请选择 .pt、.onnx、.engine、.mlmodel、.mlpackage 或 .torchscript 模型文件。"
        )
    if "file exists" in text or "not a directory" in text or "不是目录" in text:
        return (
            f"{context}：请选择一个文件夹作为存储目录。\n\n"
            "可能原因：当前填写的是文件路径，或该位置不能作为目录创建。\n\n"
            "建议处理：在设置中重新选择一个可写文件夹，例如用户文档目录下的新文件夹。"
        )
    if "model" in text or "模型" in context or Path(raw).suffix == ".pt":
        return (
            f"{context}：模型文件无法加载。\n\n"
            "可能原因：模型路径不正确、文件不是 YOLO 权重，或权重文件已损坏。\n\n"
            "建议处理：进入设置页重新选择 .pt 模型文件，并点击测试模型。"
        )
    if "permission" in text or "denied" in text or "不可写" in text or "access is denied" in text:
        return (
            f"{context}：当前目录没有写入权限。\n\n"
            "可能原因：目录受系统保护、被其他程序占用，或当前账号没有权限。\n\n"
            "建议处理：在设置中切换到用户文档目录下的存储位置后重试。"
        )
    if "api key" in text or "unauthorized" in text or "401" in text:
        return (
            "AI 接口鉴权失败。\n\n"
            "可能原因：API Key 缺失、填写错误或服务端拒绝访问。\n\n"
            "建议处理：在设置中检查 API Key、Base URL 和模型名称，然后点击测试接口。"
        )
    if "image" in text or "cannot identify" in text or "unsupported" in text or "format" in text:
        return (
            f"{context}：图片无法读取或格式不受支持。\n\n"
            "可能原因：图片文件损坏、格式异常，或文件后缀与真实内容不一致。\n\n"
            "建议处理：换用 PNG、JPG、JPEG、BMP、WEBP、TIF 或 TIFF 格式图片后重试。"
        )
    return (
        f"{context}。\n\n"
        f"错误信息：{raw or '未知错误'}\n\n"
        "建议处理：检查输入文件、模型路径和存储目录；如果问题持续，请保留当前操作步骤便于排查。"
    )
