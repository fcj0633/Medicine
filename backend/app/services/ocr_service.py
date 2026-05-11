import base64
import io
import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
import re
from typing import Optional
from pathlib import Path

from app.config import BAIDU_OCR_API_KEY, BAIDU_OCR_SECRET_KEY, BAIDU_OCR_TIMEOUT, OCR_PROVIDER

logger = logging.getLogger(__name__)

# Lazy-load OCR engines to avoid slow startup
_easyocr_reader = None
_rapidocr_reader = None
_baidu_token_cache = {"access_token": None, "expires_at": 0.0}
_baidu_token_lock = threading.Lock()

# EasyOCR 模型目录
MODEL_DIR = Path.home() / ".EasyOCR" / "model"
REQUIRED_MODELS = ["craft_mlt_25k.pth", "chinese_sim_g2.pth"]

BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_GENERAL_BASIC_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
BAIDU_MAX_IMAGE_SIZE = 8 * 1024 * 1024
BAIDU_MIN_SIDE = 15
BAIDU_MAX_SIDE = 4096
BAIDU_LOW_CONFIDENCE_THRESHOLD = 0.75

# 药品名称识别辅助词
NAME_SUFFIXES = ["片", "胶囊", "颗粒", "口服液", "滴眼液", "注射液", "软膏", "丸", "膏", "栓", "散", "冲剂", "糖浆", "胶丸", "口服溶液"]
NAME_FORBIDDEN = ["国药准字", "请仔细", "OTC", "有限公司", "使用", "指导", "福建", "用于"]
ENGLISH_SUFFIXES = ["TABLET", "TABLETS", "CAPSULE", "CAPSULES", "GRANULES", "SYRUP", "IBUPROFEN"]
CHINESE_REGEX = re.compile(r"[\u4e00-\u9fff]")
ENGLISH_GENERIC_MAP = {
    "IBUPROFEN": "布洛芬",
}
SECTION_STOP_HEADERS = [
    "药品名称",
    "通用名称",
    "商品名称",
    "成份",
    "成分",
    "性状",
    "功能主治",
    "作用类别",
    "功能与主治",
    "适应症",
    "功效",
    "规格",
    "用法用量",
    "用法与用量",
    "用法和用量",
    "用法",
    "不良反应",
    "禁忌",
    "注意事项",
    "药物相互作用",
    "贮藏",
    "藏",
    "包装",
    "有效期",
    "执行标准",
    "批准文号",
    "说明书修订日期",
    "生产企业",
]


class OCRInputError(ValueError):
    """上传图片格式、尺寸等不满足 OCR 约束。"""


class OCRNoTextError(RuntimeError):
    """OCR 成功但未识别到任何文字。"""


class OCRServiceError(RuntimeError):
    """外部 OCR 服务不可用或返回异常。"""

    def __init__(self, message: str, *, retryable: bool = False, status_code: int = 502, error_code: Optional[int] = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.error_code = error_code


def check_ocr_models() -> list:
    """检查 EasyOCR 模型是否已下载，返回缺失的模型列表"""
    missing = []
    for m in REQUIRED_MODELS:
        if not (MODEL_DIR / m).exists():
            missing.append(m)
    return missing


def get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        missing = check_ocr_models()
        if missing:
            model_dir_str = str(MODEL_DIR)
            raise RuntimeError(
                f"OCR 模型文件未就绪，缺少: {', '.join(missing)}。"
                f"请手动下载模型到 {model_dir_str} 目录。"
                f"下载地址: craft_mlt_25k.pth → https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/craft_mlt_25k.zip , "
                f"chinese_sim_g2.pth → https://github.com/JaidedAI/EasyOCR/releases/download/v1.4/chinese_sim_g2.zip "
                f"（下载 zip 解压后放入上述目录）"
            )
        import easyocr
        _easyocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
    return _easyocr_reader


def get_rapidocr_reader():
    global _rapidocr_reader
    if _rapidocr_reader is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except Exception:
            _rapidocr_reader = None
        else:
            _rapidocr_reader = RapidOCR()
    return _rapidocr_reader


def _validate_provider(provider: str) -> str:
    provider = (provider or "hybrid").strip().lower()
    if provider not in {"baidu", "easyocr", "hybrid"}:
        return "hybrid"
    return provider


def _post_form(url: str, data: dict, timeout: float) -> dict:
    payload = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        try:
            return json.loads(body)
        except json.JSONDecodeError as json_exc:
            raise OCRServiceError("百度 OCR 服务响应异常，请稍后重试", retryable=True, status_code=502) from json_exc
    except urllib.error.URLError as exc:
        raise OCRServiceError("百度 OCR 服务连接失败，请稍后重试", retryable=True, status_code=502) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise OCRServiceError("百度 OCR 服务超时，请稍后重试", retryable=True, status_code=502) from exc


def get_baidu_access_token(force_refresh: bool = False) -> str:
    if not BAIDU_OCR_API_KEY or not BAIDU_OCR_SECRET_KEY:
        raise OCRServiceError("百度 OCR 凭证未配置", retryable=True, status_code=500)

    now = time.time()
    with _baidu_token_lock:
        cached_token = _baidu_token_cache.get("access_token")
        expires_at = float(_baidu_token_cache.get("expires_at") or 0.0)
        if not force_refresh and cached_token and expires_at - 300 > now:
            return cached_token

        response = _post_form(
            BAIDU_TOKEN_URL,
            {
                "grant_type": "client_credentials",
                "client_id": BAIDU_OCR_API_KEY,
                "client_secret": BAIDU_OCR_SECRET_KEY,
            },
            BAIDU_OCR_TIMEOUT,
        )

        access_token = response.get("access_token")
        expires_in = int(response.get("expires_in") or 0)
        if access_token and expires_in > 0:
            _baidu_token_cache["access_token"] = access_token
            _baidu_token_cache["expires_at"] = now + expires_in
            return access_token

        error_message = response.get("error_description") or response.get("error_msg") or response.get("error") or "获取 access_token 失败"
        raise OCRServiceError(f"百度 OCR 鉴权失败：{error_message}", retryable=True, status_code=502)


def normalize_image_for_baidu(image_bytes: bytes) -> bytes:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise OCRInputError("图片格式不支持，请上传清晰的 jpg、png 或 bmp 图片") from exc

    width, height = image.size
    if min(width, height) < BAIDU_MIN_SIDE:
        raise OCRInputError("图片尺寸过小，请上传更清晰的药盒或说明书图片")

    if max(width, height) > BAIDU_MAX_SIDE:
        scale = BAIDU_MAX_SIDE / float(max(width, height))
        resized = (
            max(BAIDU_MIN_SIDE, int(width * scale)),
            max(BAIDU_MIN_SIDE, int(height * scale)),
        )
        image = image.resize(resized, Image.Resampling.LANCZOS)

    if image.mode not in ("RGB", "L"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        if "A" in image.getbands():
            background.paste(image, mask=image.getchannel("A"))
        else:
            background.paste(image)
        image = background
    elif image.mode == "L":
        image = image.convert("RGB")

    current_image = image
    for _ in range(4):
        for quality in (90, 80, 70, 60, 50):
            buffer = io.BytesIO()
            current_image.save(buffer, format="JPEG", quality=quality, optimize=True)
            normalized = buffer.getvalue()
            encoded = urllib.parse.quote_plus(base64.b64encode(normalized).decode("ascii"))
            if len(encoded) <= BAIDU_MAX_IMAGE_SIZE:
                return normalized

        resized = (
            max(BAIDU_MIN_SIDE, int(current_image.width * 0.85)),
            max(BAIDU_MIN_SIDE, int(current_image.height * 0.85)),
        )
        if resized == current_image.size:
            break
        current_image = current_image.resize(resized, Image.Resampling.LANCZOS)

    raise OCRInputError("图片文件过大，请重新拍摄或压缩后再试")


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """图像预处理：去噪、增强、二值化"""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("无法解析上传的图片")

    # 转灰度
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 高斯去噪
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)

    # CLAHE 自适应直方图均衡化增强对比度
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # 自适应二值化
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    return binary


def enhance_for_ocr(img: np.ndarray, scale: float = 2.0) -> np.ndarray:
    h, w = img.shape[:2]
    resized = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharp = cv2.filter2D(gray, -1, kernel)
    binary = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def get_title_crops(img: np.ndarray) -> list:
    h, w = img.shape[:2]
    regions = [
        (0.18, 0.48, 0.22, 0.88),
        (0.20, 0.42, 0.26, 0.82),
        (0.16, 0.40, 0.20, 0.90),
    ]
    crops = []
    for top_r, bottom_r, left_r, right_r in regions:
        top = int(h * top_r)
        bottom = int(h * bottom_r)
        left = int(w * left_r)
        right = int(w * right_r)
        if bottom > top and right > left:
            crops.append((img[top:bottom, left:right], top))
    return crops


def _merge_collected_lines(collected: list) -> tuple[list[str], list[dict]]:
    collected.sort(key=lambda r: (r["y"], -r["conf"]))

    seen = set()
    merged_lines = []
    line_confidences = []
    for item in collected:
        normalized = re.sub(r"\s+", "", item["text"])
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged_lines.append(item["text"])
        line_confidences.append({
            "text": item["text"],
            "average": round(float(item["conf"]), 4),
            "min": round(float(item["conf"]), 4),
        })
    return merged_lines, line_confidences


def perform_ocr_easyocr(image_bytes: bytes) -> dict:
    """执行本地 OCR 识别，返回统一结构。"""
    nparr = np.frombuffer(image_bytes, np.uint8)
    original = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if original is None:
        raise OCRInputError("图片格式不支持，请上传清晰的 jpg、png 或 bmp 图片")

    processed = preprocess_image(image_bytes)
    processed_bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
    enlarged_original = enhance_for_ocr(original, 2.2)

    collected = []

    def add_result(text: str, conf: float, bbox=None, offset_y: float = 0.0):
        text = (text or "").strip()
        if not text:
            return
        if conf is None:
            conf = 0.0
        y_center = 0.0
        if bbox is not None:
            try:
                points = bbox.tolist() if hasattr(bbox, "tolist") else bbox
                if isinstance(points, (list, tuple)) and len(points) > 0:
                    y_center = sum(p[1] for p in points) / len(points) + offset_y
            except Exception:
                pass
        collected.append({"text": text, "conf": float(conf), "y": y_center})

    # EasyOCR 原图 + 预处理图
    try:
        easy_reader = get_easyocr_reader()
    except RuntimeError:
        easy_reader = None

    def run_easy(img: np.ndarray, offset_y: float = 0.0):
        if easy_reader is None:
            return
        try:
            ocr_results = easy_reader.readtext(img, detail=1, paragraph=False)
        except Exception:
            return
        for bbox, text, conf in ocr_results:
            if conf is None or conf < 0.15:
                continue
            add_result(text, conf, bbox, offset_y)

    run_easy(original)
    run_easy(processed_bgr)
    run_easy(enlarged_original)
    for crop, top in get_title_crops(original):
        run_easy(crop, top)
        run_easy(enhance_for_ocr(crop, 3.0), top)

    # RapidOCR （如可用）
    rapid_reader = get_rapidocr_reader()
    if rapid_reader is not None:
        try:
            rapid_results, _ = rapid_reader(original)
        except Exception:
            rapid_results = None
        if rapid_results:
            for item in rapid_results:
                if not isinstance(item, (list, tuple)) or len(item) < 3:
                    continue
                box, text, score = item[0], item[1], item[2]
                add_result(text, score, box)

    if not collected:
        raise OCRNoTextError("未识别到文字，请重新拍摄更清晰的药盒或说明书")

    merged_lines, line_confidences = _merge_collected_lines(collected)
    return {
        "raw_text": "\n".join(merged_lines),
        "provider": "easyocr",
        "low_confidence": False,
        "confidence_notice": None,
        "meta": {
            "line_probabilities": line_confidences,
        },
    }


def parse_baidu_ocr_response(response: dict) -> dict:
    error_code = response.get("error_code")
    if error_code:
        error_message = response.get("error_msg") or "百度 OCR 服务异常"
        retryable = int(error_code) in {17, 18, 19, 110, 111}
        raise OCRServiceError(
            f"百度 OCR 服务异常：{error_message}",
            retryable=retryable,
            status_code=502,
            error_code=int(error_code),
        )

    words_result = response.get("words_result") or []
    lines = []
    line_probabilities = []
    for item in words_result:
        text = (item.get("words") or "").strip()
        if not text:
            continue
        lines.append(text)
        probability = item.get("probability") or {}
        average = probability.get("average")
        minimum = probability.get("min")
        line_probabilities.append({
            "text": text,
            "average": round(float(average), 4) if average is not None else None,
            "min": round(float(minimum), 4) if minimum is not None else None,
        })

    if not lines:
        raise OCRNoTextError("未识别到文字，请重新拍摄更清晰的药盒或说明书")

    low_confidence = any(
        line.get("average") is not None and line["average"] < BAIDU_LOW_CONFIDENCE_THRESHOLD
        for line in line_probabilities
    )

    return {
        "raw_text": "\n".join(lines),
        "provider": "baidu",
        "low_confidence": low_confidence,
        "confidence_notice": "识别结果可能不准确，请手动核对" if low_confidence else None,
        "meta": {
            "log_id": response.get("log_id"),
            "direction": response.get("direction"),
            "words_result_num": response.get("words_result_num"),
            "line_probabilities": line_probabilities,
        },
    }


def perform_ocr_baidu(image_bytes: bytes) -> dict:
    normalized_image = normalize_image_for_baidu(image_bytes)
    encoded_image = base64.b64encode(normalized_image).decode("ascii")

    def request_ocr(access_token: str) -> dict:
        request_url = f"{BAIDU_GENERAL_BASIC_URL}?access_token={urllib.parse.quote_plus(access_token)}"
        return _post_form(
            request_url,
            {
                "image": encoded_image,
                "language_type": "CHN_ENG",
                "detect_direction": "true",
                "paragraph": "true",
                "probability": "true",
            },
            BAIDU_OCR_TIMEOUT,
        )

    started_at = time.perf_counter()
    access_token = get_baidu_access_token()
    response = request_ocr(access_token)

    try:
        parsed = parse_baidu_ocr_response(response)
    except OCRServiceError as exc:
        if exc.error_code not in {110, 111}:
            raise
        access_token = get_baidu_access_token(force_refresh=True)
        response = request_ocr(access_token)
        parsed = parse_baidu_ocr_response(response)

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "OCR completed provider=%s latency_ms=%s log_id=%s",
        parsed["provider"],
        elapsed_ms,
        parsed["meta"].get("log_id"),
    )
    return parsed


def perform_ocr(image_bytes: bytes) -> dict:
    """执行 OCR 识别并返回统一结构。"""
    provider = _validate_provider(OCR_PROVIDER)
    if provider == "easyocr":
        return perform_ocr_easyocr(image_bytes)
    if provider == "baidu":
        return perform_ocr_baidu(image_bytes)

    try:
        return perform_ocr_baidu(image_bytes)
    except OCRServiceError as exc:
        if not exc.retryable:
            raise
        logger.warning("Baidu OCR unavailable, falling back to EasyOCR: %s", exc)
        fallback = perform_ocr_easyocr(image_bytes)
        fallback_meta = fallback.setdefault("meta", {})
        fallback_meta["fallback_from"] = "baidu"
        fallback_meta["fallback_reason"] = str(exc)
        return fallback


def _section_header_pattern(headers: list[str]) -> str:
    escaped = [re.escape(h) for h in headers]
    return r"(?:【|\[)?\s*(?:" + "|".join(escaped) + r")\s*(?:】|\])?\s*[：:]?\s*"


def _extract_section(raw_text: str, headers: list[str], stop_headers: Optional[list[str]] = None) -> Optional[str]:
    stop_headers = stop_headers or SECTION_STOP_HEADERS
    header_pattern = _section_header_pattern(headers)
    stop_pattern = _section_header_pattern(stop_headers)
    pattern = re.compile(
        rf"{header_pattern}(.*?)(?=(?:\n\s*)?{stop_pattern}|$)",
        re.DOTALL,
    )
    match = pattern.search(raw_text)
    if not match:
        return None

    section = match.group(1)
    section = re.sub(r"\n(?=\d+[.、])", "\n", section)
    section = re.sub(r"[ \t]+", "", section)
    section = re.sub(r"\n{2,}", "\n", section)
    section = section.strip("：: \n\t")
    return section or None


def extract_drug_info(raw_text: str) -> dict:
    """从 OCR 原始文本中提取药品结构化信息"""
    info = {
        "drug_name": None,
        "specification": None,
        "efficacy": None,
        "usage_dosage": None,
        "frequency": None,
        "caution": None,
    }

    text = raw_text.replace(" ", "")
    compact_text = re.sub(r"[ \t]+", "", raw_text)
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    upper_text = raw_text.upper()

    # 药品名称提取
    name_patterns = [
        r"(?:通用名称|药品名称|品名)[：:]\s*(.+?)(?:\n|$)",
        r"(?:商品名称|商品名)[：:]\s*(.+?)(?:\n|$)",
        r"([\u4e00-\u9fff]{2,16}(?:缓释|控释|肠溶|分散|咀嚼|复方)?(?:片|胶囊|颗粒|口服液|滴眼液|丸|糖浆|散|软膏|栓))",
    ]
    for p in name_patterns:
        m = re.search(p, text)
        if m:
            candidate = m.group(1).strip()
            if not any(f in candidate for f in NAME_FORBIDDEN):
                info["drug_name"] = candidate
                break

    # 如果没匹配到，取第一行非空文本作为药名
    if not info["drug_name"] and lines:
        def clean_line(line: str) -> str:
            return re.sub(r"[：:，,。.·\-_/\\|]", "", line).strip()

        chinese_candidates = []
        for idx, line in enumerate(lines):
            normalized = clean_line(line)
            if not normalized or any(f in normalized for f in NAME_FORBIDDEN):
                continue
            if CHINESE_REGEX.search(normalized):
                chinese_candidates.append((idx, normalized))

        for idx, normalized in chinese_candidates:
            if any(suffix in normalized for suffix in NAME_SUFFIXES) and 2 <= len(normalized) <= 20:
                info["drug_name"] = normalized
                break

        if not info["drug_name"]:
            for i in range(len(chinese_candidates) - 1):
                first_idx, first = chinese_candidates[i]
                second_idx, second = chinese_candidates[i + 1]
                if second_idx - first_idx != 1:
                    continue
                combined = first + second
                if any(suffix in combined for suffix in NAME_SUFFIXES) and 2 <= len(combined) <= 20 and not any(f in combined for f in NAME_FORBIDDEN):
                    info["drug_name"] = combined
                    break

        # 先寻找包含常见剂型后缀的中文
        for line in lines:
            if info["drug_name"]:
                break
            normalized = clean_line(line)
            if not normalized or any(f in normalized for f in NAME_FORBIDDEN):
                continue
            if any(suffix in normalized for suffix in NAME_SUFFIXES) and 2 <= len(normalized) <= 20:
                info["drug_name"] = normalized
                break

        # 再尝试英文药名
        if not info["drug_name"]:
            if ("IBUPROFEN" in upper_text or "VUPROFEN" in upper_text) and ("CAPS" in upper_text or "CAPSULE" in upper_text):
                if "SUSTAIN" in upper_text or "RELEASE" in upper_text:
                    info["drug_name"] = "布洛芬缓释胶囊"
                else:
                    info["drug_name"] = "布洛芬胶囊"

        if not info["drug_name"]:
            for line in lines:
                upper_line = line.upper().strip()
                if any(word in upper_line for word in ENGLISH_SUFFIXES) and len(upper_line) <= 30:
                    for english_name, chinese_name in ENGLISH_GENERIC_MAP.items():
                        if english_name in upper_line:
                            info["drug_name"] = chinese_name
                            break
                    if not info["drug_name"]:
                        info["drug_name"] = upper_line.title()
                    break

    # 规格
    info["specification"] = _extract_section(raw_text, ["规格", "规　格"], ["用法用量", "用法与用量", "用法和用量", "用法", "不良反应", "禁忌", "注意事项"])

    spec_patterns = [
        r"(?:规格|规　格)[：:]?\s*(.+?)(?:\n|$)",
        r"(每(?:片|粒|袋|支|瓶)装\d+(?:\.\d+)?(?:mg|g|ml|克|毫升))",
        r"(\d+(?:\.\d+)?(?:mg|g|ml|片|粒|袋|支)(?:/(?:片|粒|袋|支|瓶))?)",
    ]
    for p in spec_patterns:
        if info["specification"]:
            break
        m = re.search(p, compact_text)
        if m:
            info["specification"] = m.group(1).strip()
            break

    # 功效 / 适应症
    info["efficacy"] = _extract_section(
        raw_text,
        ["功能主治", "适应症", "功效", "作用类别", "功能与主治"],
        ["规格", "用法用量", "用法与用量", "用法和用量", "用法", "不良反应", "禁忌", "注意事项", "药物相互作用", "贮藏", "包装"],
    )
    if not info["efficacy"]:
        efficacy_patterns = [
            r"(?:功能主治|适应症|功效)[：:]?\s*(.+?)(?:(?:用法|用量|注意|不良|禁忌|规格|贮藏|包装|批准)|$)",
            r"(?:作用类别|功能与主治)[：:]?\s*(.+?)(?:(?:用法|用量|注意|不良|禁忌)|$)",
        ]
        for p in efficacy_patterns:
            m = re.search(p, compact_text, re.DOTALL)
            if m:
                info["efficacy"] = m.group(1).strip().replace("\n", "")
                break

    # 用法用量
    info["usage_dosage"] = _extract_section(
        raw_text,
        ["用法用量", "用法与用量", "用法和用量", "用法"],
        ["不良反应", "禁忌", "注意事项", "药物相互作用", "贮藏", "包装", "有效期", "批准文号"],
    )
    if not info["usage_dosage"]:
        usage_patterns = [
            r"(?:用法用量|用法与用量|用法和用量)[：:]?\s*(.+?)(?:(?:注意|不良|禁忌|贮藏|包装|有效|批准|功能|适应)|$)",
            r"(?:用法)[：:]?\s*(.+?)(?:\n|$)",
        ]
        for p in usage_patterns:
            m = re.search(p, compact_text, re.DOTALL)
            if m:
                usage_text = m.group(1).strip().replace("\n", "")
                info["usage_dosage"] = usage_text
                break

    # 频率提取
    frequency_source = info["usage_dosage"] or compact_text
    freq_patterns = [
        r"(?:一日|每日|每天)\s*(\d+)\s*次",
        r"(\d+)\s*次\s*/\s*(?:日|天)",
        r"(?:每|一)\s*(\d+)\s*小时",
    ]
    for p in freq_patterns:
        m = re.search(p, frequency_source)
        if m:
            info["frequency"] = m.group(0)
            break

    # 注意事项
    info["caution"] = _extract_section(
        raw_text,
        ["注意事项"],
        ["药物相互作用", "贮藏", "包装", "有效期", "执行标准", "批准文号", "说明书修订日期", "生产企业"],
    )
    if not info["caution"]:
        for caution_header in (["禁忌"], ["不良反应"]):
            caution_text = _extract_section(
                raw_text,
                caution_header,
                ["注意事项", "药物相互作用", "贮藏", "包装", "有效期", "执行标准", "批准文号", "说明书修订日期", "生产企业"],
            )
            if caution_text:
                info["caution"] = caution_text
                break

    if not info["caution"]:
        caution_patterns = [
            r"(?:注意事项|禁忌)[：:]?\s*(.+?)(?:(?:贮藏|包装|有效|批准|生产)|$)",
            r"(?:不良反应)[：:]?\s*(.+?)(?:(?:注意|禁忌|贮藏|包装)|$)",
        ]
        for p in caution_patterns:
            m = re.search(p, compact_text, re.DOTALL)
            if m:
                info["caution"] = m.group(1).strip().replace("\n", "")
                break

    return info
