from __future__ import annotations

import base64
from dataclasses import dataclass
from html import escape
from pathlib import Path

import gradio as gr

from .config import PROJECT_ROOT


HOME_HERO_IMAGE_PATH = (
    PROJECT_ROOT / "assets" / "branding" / "real-dental-panorama-test-00021.jpg"
)


@dataclass(frozen=True)
class HomeCapability:
    number: str
    title: str
    description: str


HOME_CAPABILITIES = (
    HomeCapability(
        "01",
        "单张影像初筛",
        "上传牙科影像后，由检测模型标记需要医生重点复核的区域，并保留结构化结果。",
    ),
    HomeCapability(
        "02",
        "批量健康检查",
        "连续处理多张牙片，逐张查看检测结果、质量提示和汇总信息，减少重复操作。",
    ),
    HomeCapability(
        "03",
        "AI 辅助分析",
        "围绕模型输出生成文字说明并支持继续追问；不把辅助结论包装成最终诊断。",
    ),
)


def _image_data_uri(path: Path) -> str:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise FileNotFoundError(f"首页真实牙片素材不存在：{path}") from exc
    return f"data:image/jpeg;base64,{base64.b64encode(payload).decode('ascii')}"


def _capability_html(capability: HomeCapability) -> str:
    return (
        '<article class="home-capability">'
        '<div class="home-capability-heading">'
        f'<span class="home-capability-index">{escape(capability.number)}</span>'
        f'<h3>{escape(capability.title)}</h3>'
        "</div>"
        f'<p>{escape(capability.description)}</p>'
        '<span class="home-capability-line" aria-hidden="true"></span>'
        "</article>"
    )


def build_home_page_html(hero_image_path: Path = HOME_HERO_IMAGE_PATH) -> str:
    hero_image = _image_data_uri(hero_image_path)
    capabilities = "".join(_capability_html(item) for item in HOME_CAPABILITIES)
    return f"""
<main class="home-page">
  <section class="home-hero" aria-labelledby="home-hero-title">
    <img class="home-hero-image" src="{hero_image}" alt="真实牙科全景影像测试样本">
    <div class="home-hero-overlay" aria-hidden="true"></div>
    <div class="home-hero-content">
      <p class="home-kicker">面向医生的牙科影像辅助工作台</p>
      <h2 id="home-hero-title">智能健康牙齿分析</h2>
      <p class="home-hero-summary">面向临床初步筛查场景，结合目标检测与 AI 文字分析，支持单张和批量牙科影像检查，帮助医生更快定位需要重点复核的区域。</p>
      <div class="home-hero-actions" aria-label="开始使用">
        <button type="button" class="home-action home-action-primary" data-app-target="检测工作台" data-workbench-target="单张分析">开始单张分析</button>
        <button type="button" class="home-action home-action-secondary" data-app-target="检测工作台" data-workbench-target="批量分析">进入批量检查</button>
      </div>
    </div>
    <div class="home-hero-boundary"><strong>辅助筛查</strong><span>模型结果与 AI 建议均需由专业牙科医生复核</span></div>
  </section>

  <section class="home-capabilities" aria-labelledby="home-capabilities-title">
    <div class="home-section-heading">
      <p>核心能力</p>
      <h2 id="home-capabilities-title">从影像初筛到结果管理</h2>
      <span>围绕医生的重复工作流组织功能，而不是替代临床判断。</span>
    </div>
    <div class="home-capability-grid">{capabilities}</div>
  </section>

  <section class="home-workflow" aria-labelledby="home-workflow-title">
    <div class="home-workflow-intro">
      <p>工作方式</p>
      <h2 id="home-workflow-title">把复杂过程收进一条清晰路径</h2>
      <span>患者归属、影像输入、模型分析、报告与历史记录在同一工作区内衔接。</span>
    </div>
    <ol class="home-workflow-steps">
      <li><span>01</span><div><strong>选择患者</strong><p>明确当前影像和记录的归属，切换患者时自动清理会话状态。</p></div></li>
      <li><span>02</span><div><strong>上传真实牙片</strong><p>支持单张或批量输入，并在分析前给出基础影像质量提醒。</p></div></li>
      <li><span>03</span><div><strong>运行双模型</strong><p>可使用优化模型完成常规筛查，也可与原始 YOLOv8m 结果对比。</p></div></li>
      <li><span>04</span><div><strong>复核与归档</strong><p>查看检测框、辅助建议、病例记录、检测历史并导出报告。</p></div></li>
    </ol>
  </section>

  <section class="home-models" aria-labelledby="home-models-title">
    <div class="home-model-copy">
      <p>双模型能力</p>
      <h2 id="home-models-title">兼容基线，也保留优化路径</h2>
      <span>项目同时保留纯 YOLOv8m 训练得到的基线模型，以及采用 C2f-Faster-lite 结构的优化模型。医生可按当前环境和复核需求选择或比较结果。</span>
      <button type="button" class="home-text-action" data-app-target="设置">查看模型设置</button>
    </div>
    <div class="home-model-list">
      <article><span>BASELINE</span><h3>YOLOv8m 原始结构</h3><p>作为兼容基线和结果对照，保留标准网络结构与完整检测流程。</p></article>
      <article><span>OPTIMIZED</span><h3>C2f-Faster-lite</h3><p>面向当前牙齿病变数据训练的优化候选模型，作为日常分析的默认选择。</p></article>
    </div>
  </section>

  <section class="home-safety" aria-labelledby="home-safety-title">
    <div><p>使用边界</p><h2 id="home-safety-title">医生主导，模型辅助</h2></div>
    <p>系统用于牙科影像初步筛查、复核提示与记录整理，不替代临床检查、专业诊断或治疗决策。病例和检测历史默认保存在本机数据目录，原始牙片不会随记录自动上传云端。</p>
    <button type="button" class="home-action home-action-primary" data-app-target="检测工作台" data-workbench-target="单张分析">进入检测工作台</button>
  </section>
</main>
"""


def build_home_page() -> None:
    gr.HTML(build_home_page_html(), container=False)
