import asyncio
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import UPLOAD_DIR
from app.database import get_db
from app.models import Drug, DrugCatalog, FamilyRelation, MedicationLog, Reminder, User
from app.schemas import (
    DrugCatalogCreate,
    DrugCatalogOut,
    DrugCreate,
    DrugOut,
    DrugUpdate,
    OCRResult,
)
from app.services.drug_catalog_service import maybe_enrich_ocr_info, search_drug_catalog
from app.services.ocr_service import (
    OCRInputError,
    OCRNoTextError,
    OCRServiceError,
    extract_drug_info,
    perform_ocr,
)
from app.services.semantic_service import simplify_caution, simplify_efficacy, simplify_usage
from app.services.tts_service import generate_drug_audio

router = APIRouter(prefix="/api/drugs", tags=["药品管理"])


def check_family_access(db: Session, current_user: User, target_user_id: int) -> bool:
    if current_user.id == target_user_id:
        return True
    if current_user.role == "family":
        relation = db.query(FamilyRelation).filter(
            FamilyRelation.family_user_id == current_user.id,
            FamilyRelation.elderly_user_id == target_user_id,
        ).first()
        return relation is not None
    return False


def _run_ocr(contents: bytes) -> dict:
    try:
        return perform_ocr(contents)
    except OCRInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OCRNoTextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OCRServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _build_drug_payload(info: dict) -> dict:
    efficacy = info.get("efficacy")
    usage_dosage = info.get("usage_dosage")
    caution = info.get("caution")

    return {
        "name": info.get("drug_name") or "未识别药品",
        "specification": info.get("specification"),
        "efficacy": efficacy,
        "efficacy_simple": info.get("efficacy_simple") or simplify_efficacy(efficacy),
        "usage_dosage": usage_dosage,
        "usage_simple": info.get("usage_simple") or simplify_usage(usage_dosage),
        "frequency": info.get("frequency"),
        "caution": caution,
        "caution_simple": info.get("caution_simple") or simplify_caution(caution),
    }


def _build_ocr_result(raw_text: str, ocr_result: dict, info: dict, catalog_match: Optional[DrugCatalog], enriched_fields: list[str]) -> OCRResult:
    payload = _build_drug_payload(info)
    return OCRResult(
        raw_text=raw_text,
        drug_name=payload["name"],
        specification=payload["specification"],
        efficacy=payload["efficacy"],
        efficacy_simple=payload["efficacy_simple"],
        usage_dosage=payload["usage_dosage"],
        usage_simple=payload["usage_simple"],
        frequency=payload["frequency"],
        caution=payload["caution"],
        caution_simple=payload["caution_simple"],
        ocr_provider=ocr_result.get("provider"),
        low_confidence=bool(ocr_result.get("low_confidence")),
        confidence_notice=ocr_result.get("confidence_notice"),
        ocr_meta=ocr_result.get("meta"),
        catalog_match_name=catalog_match.name if catalog_match else None,
        catalog_enriched=bool(enriched_fields),
        catalog_enriched_fields=enriched_fields,
    )


def _create_drug_instance(user_id: int, created_by: int, info: dict, *, image_path: Optional[str] = None, raw_text: Optional[str] = None) -> Drug:
    payload = _build_drug_payload(info)
    return Drug(
        user_id=user_id,
        name=payload["name"],
        specification=payload["specification"],
        efficacy=payload["efficacy"],
        efficacy_simple=payload["efficacy_simple"],
        usage_dosage=payload["usage_dosage"],
        usage_simple=payload["usage_simple"],
        frequency=payload["frequency"],
        caution=payload["caution"],
        caution_simple=payload["caution_simple"],
        image_path=image_path,
        ocr_raw_text=raw_text,
        created_by=created_by,
    )


@router.get("/catalog/search", response_model=List[DrugCatalogOut])
def search_catalog_drugs(
    keyword: str,
    limit: int = 8,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    limit = max(1, min(limit, 20))
    return search_drug_catalog(db, keyword, limit=limit)


@router.post("/catalog/add", response_model=DrugOut)
def add_drug_from_catalog(
    data: DrugCatalogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = data.target_user_id or current_user.id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权为该用户添加药品")

    catalog = db.query(DrugCatalog).filter(DrugCatalog.id == data.catalog_id).first()
    if not catalog:
        raise HTTPException(status_code=404, detail="药品标准库记录不存在")

    existing_drug = db.query(Drug).filter(
        Drug.user_id == uid,
        Drug.name == catalog.name,
        Drug.specification == catalog.specification,
    ).first()
    if existing_drug:
        return existing_drug

    info = {
        "drug_name": catalog.name,
        "specification": catalog.specification,
        "efficacy": catalog.efficacy,
        "efficacy_simple": catalog.efficacy_simple,
        "usage_dosage": catalog.usage_dosage,
        "usage_simple": catalog.usage_simple,
        "frequency": catalog.frequency,
        "caution": catalog.caution,
        "caution_simple": catalog.caution_simple,
    }

    drug = _create_drug_instance(uid, current_user.id, info)
    db.add(drug)
    db.commit()
    db.refresh(drug)
    return drug


@router.post("/recognize", response_model=OCRResult)
async def recognize_drug(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    contents = await file.read()

    loop = asyncio.get_running_loop()
    ocr_result = await loop.run_in_executor(None, _run_ocr, contents)
    raw_text = ocr_result["raw_text"]

    info = extract_drug_info(raw_text)
    info, catalog_match, enriched_fields = maybe_enrich_ocr_info(db, info)
    return _build_ocr_result(raw_text, ocr_result, info, catalog_match, enriched_fields)


@router.post("/upload-and-save", response_model=DrugOut)
async def upload_and_save_drug(
    file: UploadFile = File(...),
    target_user_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = target_user_id or current_user.id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权为该用户添加药品")

    contents = await file.read()

    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    img_name = f"{uuid.uuid4().hex}{ext}"
    img_path = os.path.join(UPLOAD_DIR, img_name)
    with open(img_path, "wb") as file_obj:
        file_obj.write(contents)

    loop = asyncio.get_running_loop()
    try:
        ocr_result = await loop.run_in_executor(None, _run_ocr, contents)
    except HTTPException:
        if os.path.exists(img_path):
            try:
                os.remove(img_path)
            except OSError:
                pass
        raise

    raw_text = ocr_result["raw_text"]
    info = extract_drug_info(raw_text)
    info, _, _ = maybe_enrich_ocr_info(db, info)

    drug = _create_drug_instance(
        uid,
        current_user.id,
        info,
        image_path=img_name,
        raw_text=raw_text,
    )
    db.add(drug)
    db.commit()
    db.refresh(drug)
    return drug


@router.post("/", response_model=DrugOut)
def create_drug(
    data: DrugCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = data.target_user_id or current_user.id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权为该用户添加药品")

    drug = Drug(
        user_id=uid,
        name=data.name,
        specification=data.specification,
        efficacy=data.efficacy,
        efficacy_simple=data.efficacy_simple or simplify_efficacy(data.efficacy),
        usage_dosage=data.usage_dosage,
        usage_simple=data.usage_simple or simplify_usage(data.usage_dosage),
        frequency=data.frequency,
        caution=data.caution,
        caution_simple=data.caution_simple or simplify_caution(data.caution),
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(drug)
    db.commit()
    db.refresh(drug)
    return drug


@router.get("/", response_model=List[DrugOut])
def get_drugs(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = user_id or current_user.id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权查看")

    return db.query(Drug).filter(Drug.user_id == uid).order_by(Drug.created_at.desc()).all()


@router.get("/{drug_id}", response_model=DrugOut)
def get_drug(
    drug_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    if not check_family_access(db, current_user, drug.user_id):
        raise HTTPException(status_code=403, detail="无权查看")
    return drug


@router.put("/{drug_id}", response_model=DrugOut)
def update_drug(
    drug_id: int,
    data: DrugUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    if not check_family_access(db, current_user, drug.user_id):
        raise HTTPException(status_code=403, detail="无权修改")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(drug, key, value)

    db.commit()
    db.refresh(drug)
    return drug


@router.delete("/{drug_id}")
def delete_drug(
    drug_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    if not check_family_access(db, current_user, drug.user_id):
        raise HTTPException(status_code=403, detail="无权删除")

    reminder_ids = [row.id for row in db.query(Reminder.id).filter(Reminder.drug_id == drug_id).all()]
    if reminder_ids:
        db.query(MedicationLog).filter(MedicationLog.reminder_id.in_(reminder_ids)).delete(synchronize_session=False)
        db.query(Reminder).filter(Reminder.id.in_(reminder_ids)).delete(synchronize_session=False)

    if getattr(drug, "image_path", None):
        img_path = os.path.join(UPLOAD_DIR, drug.image_path)
        if os.path.exists(img_path):
            try:
                os.remove(img_path)
            except OSError:
                pass

    db.delete(drug)
    db.commit()
    return {"message": "已删除"}


@router.get("/{drug_id}/audio")
def get_drug_audio(
    drug_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    if not check_family_access(db, current_user, drug.user_id):
        raise HTTPException(status_code=403, detail="无权查看")

    filename = generate_drug_audio(
        drug.name,
        drug.efficacy_simple,
        drug.usage_simple,
        drug.caution_simple,
    )
    return {"audio_file": filename, "url": f"/audio/{filename}"}
