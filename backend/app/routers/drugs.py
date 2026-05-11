import os
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import User, Drug, FamilyRelation, Reminder, MedicationLog
from app.schemas import DrugCreate, DrugUpdate, DrugOut, OCRResult
from app.auth import get_current_user
from app.config import UPLOAD_DIR
from app.services.ocr_service import (
    OCRInputError,
    OCRNoTextError,
    OCRServiceError,
    perform_ocr,
    extract_drug_info,
)
from app.services.semantic_service import simplify_efficacy, simplify_usage, simplify_caution
from app.services.tts_service import generate_drug_audio

router = APIRouter(prefix="/api/drugs", tags=["药品管理"])


def check_family_access(db: Session, current_user: User, target_user_id: int) -> bool:
    """检查家属是否有权限操作目标老人的数据"""
    if current_user.id == target_user_id:
        return True
    if current_user.role == "family":
        rel = db.query(FamilyRelation).filter(
            FamilyRelation.family_user_id == current_user.id,
            FamilyRelation.elderly_user_id == target_user_id
        ).first()
        return rel is not None
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


@router.post("/recognize", response_model=OCRResult)
async def recognize_drug(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """上传药品图片进行 OCR 识别"""
    contents = await file.read()

    # OCR 识别（CPU 密集型，放到线程池避免阻塞事件循环）
    loop = asyncio.get_running_loop()
    ocr_result = await loop.run_in_executor(None, _run_ocr, contents)
    raw_text = ocr_result["raw_text"]

    # 结构化提取
    info = extract_drug_info(raw_text)

    # 语义简化
    efficacy_simple = simplify_efficacy(info.get("efficacy"))
    usage_simple = simplify_usage(info.get("usage_dosage"))
    caution_simple = simplify_caution(info.get("caution"))

    return OCRResult(
        raw_text=raw_text,
        drug_name=info.get("drug_name"),
        specification=info.get("specification"),
        efficacy=info.get("efficacy"),
        efficacy_simple=efficacy_simple,
        usage_dosage=info.get("usage_dosage"),
        usage_simple=usage_simple,
        frequency=info.get("frequency"),
        caution=info.get("caution"),
        caution_simple=caution_simple,
        ocr_provider=ocr_result.get("provider"),
        low_confidence=bool(ocr_result.get("low_confidence")),
        confidence_notice=ocr_result.get("confidence_notice"),
        ocr_meta=ocr_result.get("meta"),
    )


@router.post("/upload-and-save", response_model=DrugOut)
async def upload_and_save_drug(
    file: UploadFile = File(...),
    target_user_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传药品图片，识别并直接保存到数据库"""
    uid = target_user_id or current_user.id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权操作该用户药品")

    contents = await file.read()

    # 保存图片
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    img_name = f"{uuid.uuid4().hex}{ext}"
    img_path = os.path.join(UPLOAD_DIR, img_name)
    with open(img_path, "wb") as f:
        f.write(contents)

    # OCR（线程池执行）
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

    drug = Drug(
        user_id=uid,
        name=info.get("drug_name") or "未识别药品",
        specification=info.get("specification"),
        efficacy=info.get("efficacy"),
        efficacy_simple=simplify_efficacy(info.get("efficacy")),
        usage_dosage=info.get("usage_dosage"),
        usage_simple=simplify_usage(info.get("usage_dosage")),
        frequency=info.get("frequency"),
        caution=info.get("caution"),
        caution_simple=simplify_caution(info.get("caution")),
        image_path=img_name,
        ocr_raw_text=raw_text,
        created_by=current_user.id,
    )
    db.add(drug)
    db.commit()
    db.refresh(drug)
    return drug


@router.post("/", response_model=DrugOut)
def create_drug(data: DrugCreate, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    """手动创建药品记录"""
    uid = data.target_user_id or current_user.id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权操作该用户药品")

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
        created_by=current_user.id,
    )
    db.add(drug)
    db.commit()
    db.refresh(drug)
    return drug


@router.get("/", response_model=List[DrugOut])
def get_drugs(user_id: Optional[int] = None, db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):
    """获取药品列表"""
    uid = user_id or current_user.id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权查看")
    return db.query(Drug).filter(Drug.user_id == uid).order_by(Drug.created_at.desc()).all()


@router.get("/{drug_id}", response_model=DrugOut)
def get_drug(drug_id: int, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    if not check_family_access(db, current_user, drug.user_id):
        raise HTTPException(status_code=403, detail="无权查看")
    return drug


@router.put("/{drug_id}", response_model=DrugOut)
def update_drug(drug_id: int, data: DrugUpdate, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    if not check_family_access(db, current_user, drug.user_id):
        raise HTTPException(status_code=403, detail="无权修改")

    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(drug, key, val)
    db.commit()
    db.refresh(drug)
    return drug


@router.delete("/{drug_id}")
def delete_drug(drug_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    if not check_family_access(db, current_user, drug.user_id):
        raise HTTPException(status_code=403, detail="无权删除")

    # 删除关联的提醒与服药记录
    reminder_ids = [r.id for r in db.query(Reminder.id).filter(Reminder.drug_id == drug_id).all()]
    if reminder_ids:
        db.query(MedicationLog).filter(MedicationLog.reminder_id.in_(reminder_ids)).delete(synchronize_session=False)
        db.query(Reminder).filter(Reminder.id.in_(reminder_ids)).delete(synchronize_session=False)

    # 删除药品图片文件
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
def get_drug_audio(drug_id: int, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    """获取药品语音说明文件名"""
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    if not check_family_access(db, current_user, drug.user_id):
        raise HTTPException(status_code=403, detail="无权查看")

    filename = generate_drug_audio(
        drug.name,
        drug.efficacy_simple,
        drug.usage_simple,
        drug.caution_simple
    )
    return {"audio_file": filename, "url": f"/audio/{filename}"}
