# Bug 修复记录

> 开始时间：2026-06-03
> 修复依据：`docs/代码bug.md`（筛选后的真实问题清单）
> 修复顺序：P0 → P1 → P2

---

## 修复总览

| 编号 | 问题 | 状态 | 验证结果 |
|---|---|---|---|
| P0-1 | 类别名不一致 | ✅ 已修复 | 编译通过 |
| P0-2 | 单图报告模型名 unknown | ✅ 已修复 | 编译通过 |
| P0-3 | 下载白名单不动态更新 | ✅ 已修复 | 编译通过 |
| P0-4 | OpenAI 配置被静默迁移 | ✅ 已修复 | 编译通过 |
| P0-5 | load_settings 缺少类型校验 | ✅ 已修复 | 编译通过 |
| P0-6 | _current_item 静默回退 | ✅ 已修复 | 编译通过 |

---

## P0 修复详情

### P0-1: 类别名不一致导致根尖病变建议静默丢失

**修改文件**：`src/dental_detection/assistant.py`

**改动**：
1. 新增 `_normalize_class_name()` 函数，将下划线替换为空格并 strip，统一类别名格式
2. `CLASS_ADVICE` 的 key 从 `"Periapical_Lesion"` 改为 `"Periapical Lesion"`（与 data yaml 一致）
3. `default_advice()` 中 CLASS_ADVICE 查找前先 normalize label，兜底保留原始 label 查找

**验证**：`python -m compileall src/dental_detection/assistant.py` 通过

---

### P0-2: 单图报告导出模型名始终 unknown

**修改文件**：`app.py`

**改动**：`export_single_report()` 中模型名提取逻辑改为：
1. 优先取 `result["model"]`（批量检测）
2. 其次取 `summary["模型结果"][0]["模型"]`（单图检测嵌套结构）
3. 再次取 `summary["模型"]`（批量检测 summary 顶层）
4. 最后兜底 `"unknown"`

**验证**：`python -m compileall app.py` 通过

---

### P0-3: 更换存储目录后下载白名单没有动态更新

**修改文件**：`app.py`

**改动**：`_allowed_file_roots()` 中动态读取 `load_settings().storage_dir`，追加到 roots 列表。添加 try/except 防止损坏的 storage_dir 导致异常。

**验证**：`python -m compileall app.py` 通过

---

### P0-4: _with_current_defaults 可能把 OpenAI 配置静默迁移成 DeepSeek

**修改文件**：`app.py`

**改动**：
1. `_with_current_defaults` 新增 `config_exists` 参数
2. 仅当 `settings.json` 不存在（首次运行）时才执行迁移
3. 若文件已存在（用户已保存过设置），不覆盖
4. 新增 `CONFIG_PATH` 导入

**验证**：`python -m compileall app.py` 通过

---

### P0-5: load_settings 缺少类型校验

**修改文件**：`src/dental_detection/assistant.py`

**改动**：`load_settings()` 中新增字段类型校验：
- 字符串字段（`storage_dir`, `base_url` 等）：int/float/bool 自动转 str，list/dict 丢弃
- 布尔字段（`enabled`, `save_api_key`, `auto_save`）：字符串 "true"/"1" 等转 True，int 非零转 True
- 非预期类型的字段值被丢弃，回退默认值

**验证**：`python -m compileall src/dental_detection/assistant.py` 通过

---

### P0-6: _current_item 未匹配到选中项时静默回退第一条

**修改文件**：`app.py`

**改动**：`_current_item()` 中，当 `selected_name` 非空但遍历完 `batch_state` 无匹配时，抛出 `gr.Error("当前选择的结果已失效，请重新选择图片。")` 而非静默返回第一条。

**验证**：`python -m compileall app.py` 通过

---
