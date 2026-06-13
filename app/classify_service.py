"""ONNX-классификация в реальном времени (кэш сессии)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import numpy as np

from pipeline.inference import LEVEL_LABELS, resolve_model_dir, resolve_onnx_providers, _build_ort_inputs
from training_utils import CLASS_NAMES, format_appeal_text

_MAX_BATCH = 64
_runtime_lock = threading.Lock()
_runtime: dict | None = None


@dataclass(frozen=True)
class ClassifiedAppeal:
    severity: int
    label: str
    confidence: float
    is_problem: bool


def _load_runtime() -> dict:
    global _runtime
    if _runtime is not None:
        return _runtime

    with _runtime_lock:
        if _runtime is not None:
            return _runtime

        import onnxruntime as ort
        from transformers import AutoTokenizer

        from pipeline.inference import _ensure_cuda_dlls

        _ensure_cuda_dlls()
        model_dir = resolve_model_dir(None)
        model_path = model_dir / "model.onnx"
        if not model_path.is_file():
            raise FileNotFoundError(f"ONNX-модель не найдена: {model_path}")

        providers = resolve_onnx_providers()
        session = ort.InferenceSession(str(model_path), providers=providers)
        tokenizer = AutoTokenizer.from_pretrained(str(model_dir))

        max_length = 512
        label_map_path = model_dir / "label_map.json"
        if label_map_path.is_file():
            import json

            with label_map_path.open(encoding="utf-8") as fh:
                max_length = int(json.load(fh).get("max_length", max_length))

        _runtime = {
            "session": session,
            "tokenizer": tokenizer,
            "max_length": max_length,
            "providers": session.get_providers(),
        }
        print(f"Live classify: ONNX ready providers={_runtime['providers']}", flush=True)
        return _runtime


def classify_appeals(
    items: list[dict],
    *,
    batch_size: int = 16,
) -> tuple[list[ClassifiedAppeal], float]:
    """
    Классифицирует обращения. Каждый item: text (обяз.), group, topic.
    Возвращает (результаты, latency_ms).
    """
    if not items:
        return [], 0.0
    if len(items) > _MAX_BATCH:
        raise ValueError(f"Не более {_MAX_BATCH} обращений за запрос")

    texts: list[str] = []
    for item in items:
        text = format_appeal_text(
            group=item.get("group", ""),
            topic=item.get("topic", ""),
            text=item.get("text", ""),
        )
        if len(text.strip()) < 3:
            raise ValueError("Поле text обязательно (минимум 3 символа в обращении)")
        texts.append(text)

    started = time.perf_counter()
    rt = _load_runtime()
    session = rt["session"]
    tokenizer = rt["tokenizer"]
    max_length = rt["max_length"]

    all_labels: list[int] = []
    all_conf: list[float] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        encoded = tokenizer(
            batch,
            truncation=True,
            padding=True,
            max_length=max_length,
            return_tensors="np",
            return_token_type_ids=True,
        )
        ort_inputs = _build_ort_inputs(session, encoded)
        logits = session.run(None, ort_inputs)[0]
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
        batch_labels = np.argmax(probs, axis=1)
        all_labels.extend(batch_labels.tolist())
        all_conf.extend(probs[np.arange(len(batch_labels)), batch_labels].tolist())

    latency_ms = (time.perf_counter() - started) * 1000
    results = []
    for sev, conf in zip(all_labels, all_conf, strict=True):
        sev = int(sev)
        label = LEVEL_LABELS.get(sev, CLASS_NAMES[sev])
        results.append(
            ClassifiedAppeal(
                severity=sev,
                label=label,
                confidence=round(float(conf), 4),
                is_problem=sev > 0,
            )
        )
    return results, latency_ms
