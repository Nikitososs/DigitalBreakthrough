"""Служебные эндпоинты: health-check и ONNX-классификация."""

from fastapi import APIRouter, HTTPException

from app.classify_service import classify_appeals
from schemas import ClassifyRequest, ClassifyResponse, ClassifyResultItem

router = APIRouter()


@router.get("/health", summary="Проверка состояния API")
async def health_check():
    return {"status": "ok", "backend": "onnx", "service": "ZeroProblems", "message": "ML API is running"}


@router.post(
    "/classify",
    response_model=ClassifyResponse,
    summary="ONNX-классификация обращений (live)",
)
async def classify_appeals_api(body: ClassifyRequest):
    """Классифицирует 1–64 обращения через ONNX (тяжесть 0–4)."""
    try:
        payload = [item.model_dump() for item in body.items]
        results, latency_ms = classify_appeals(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Ошибка классификации: {exc}") from exc

    items = []
    for src, hit in zip(body.items, results, strict=True):
        items.append(
            ClassifyResultItem(
                id=src.id,
                severity=hit.severity,
                label=hit.label,
                confidence=hit.confidence,
                is_problem=hit.is_problem,
                text=src.text.strip()[:500],
                group=src.group,
                topic=src.topic,
                municipality=src.municipality,
                created_at=src.created_at,
            )
        )
    return ClassifyResponse(items=items, count=len(items), latency_ms=round(latency_ms, 1))
