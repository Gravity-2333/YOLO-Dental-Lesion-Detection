MODEL_SOURCE = "YOLOv8m 原始结构"
MODEL_MODE_SINGLE = "单模型"
MODEL_MODE_COMPARE = "对比模型"

# Batch results retain source and annotated images in the browser session so
# users can switch items and export reports without rerunning inference.
BATCH_FILE_LIMIT = 12

DETECTION_TABLE_COLUMNS = (
    "class",
    "中文名称",
    "confidence",
    "关注等级",
    "图像区域",
    "置信度解释",
    "x1",
    "y1",
    "x2",
    "y2",
)
