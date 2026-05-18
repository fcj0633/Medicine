from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    Drug,
    FamilyRelation,
    MedicationLog,
    MedicationLogStatus,
    Reminder,
    ReminderStatus,
    User,
)
from app.schemas import (
    AutoReminderResult,
    MedicationLogCreate,
    MedicationLogOut,
    ReminderCreate,
    ReminderOut,
    ReminderUpdate,
)
from app.services.semantic_service import generate_reminder_description
from app.services.tts_service import generate_reminder_audio

router = APIRouter(prefix="/api/reminders", tags=["服药提醒"])


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


def _load_drug_or_404(db: Session, drug_id: int) -> Drug:
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    return drug


@router.post("/auto-generate/{drug_id}", response_model=AutoReminderResult)
def auto_generate_reminders(
    drug_id: int,
    target_user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    drug = _load_drug_or_404(db, drug_id)

    uid = target_user_id or drug.user_id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权操作")
    if drug.user_id != uid:
        raise HTTPException(status_code=400, detail="药品与提醒所属用户不一致")

    plan = generate_reminder_description(drug.frequency, drug.usage_dosage)
    reminders = [
        ReminderCreate(
            drug_id=drug_id,
            reminder_time=reminder_time,
            dosage=plan["dosage"],
            meal_relation=plan["meal_relation"],
            repeat_days="everyday",
            target_user_id=uid,
        )
        for reminder_time in plan["time_suggestions"]
    ]

    meal_map = {
        "before_meal": "饭前",
        "after_meal": "饭后",
        "empty_stomach": "空腹",
        "before_sleep": "睡前",
    }
    meal_text = meal_map.get(plan["meal_relation"], "")
    desc = (
        f"建议每天服用 {plan['times_per_day']} 次，"
        f"{meal_text or '按说明书'}服用，"
        f"提醒时间：{', '.join(plan['time_suggestions'])}，"
        f"{plan['dosage']}。"
    )
    return AutoReminderResult(reminders=reminders, description=desc)


@router.post("/", response_model=ReminderOut)
def create_reminder(
    data: ReminderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = data.target_user_id or current_user.id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权操作")

    drug = _load_drug_or_404(db, data.drug_id)
    if drug.user_id != uid:
        raise HTTPException(status_code=400, detail="药品与提醒所属用户不一致")

    reminder = Reminder(
        user_id=uid,
        drug_id=data.drug_id,
        reminder_time=data.reminder_time,
        dosage=data.dosage,
        meal_relation=data.meal_relation,
        repeat_days=data.repeat_days,
        created_by=current_user.id,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    return db.query(Reminder).options(joinedload(Reminder.drug)).filter(Reminder.id == reminder.id).first()


@router.post("/batch", response_model=List[ReminderOut])
def create_reminders_batch(
    data: List[ReminderCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = []

    for item in data:
        uid = item.target_user_id or current_user.id
        if not check_family_access(db, current_user, uid):
            raise HTTPException(status_code=403, detail="无权操作")

        drug = _load_drug_or_404(db, item.drug_id)
        if drug.user_id != uid:
            raise HTTPException(status_code=400, detail="药品与提醒所属用户不一致")

        reminder = Reminder(
            user_id=uid,
            drug_id=item.drug_id,
            reminder_time=item.reminder_time,
            dosage=item.dosage,
            meal_relation=item.meal_relation,
            repeat_days=item.repeat_days,
            created_by=current_user.id,
        )
        db.add(reminder)
        results.append(reminder)

    db.commit()
    for reminder in results:
        db.refresh(reminder)

    reminder_ids = [reminder.id for reminder in results]
    return db.query(Reminder).options(joinedload(Reminder.drug)).filter(Reminder.id.in_(reminder_ids)).all()


@router.get("/", response_model=List[ReminderOut])
def get_reminders(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = user_id or current_user.id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权查看")

    return db.query(Reminder).options(joinedload(Reminder.drug)).filter(
        Reminder.user_id == uid,
        Reminder.status == ReminderStatus.ACTIVE,
    ).order_by(Reminder.reminder_time).all()


@router.put("/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    reminder_id: int,
    data: ReminderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")
    if not check_family_access(db, current_user, reminder.user_id):
        raise HTTPException(status_code=403, detail="无权修改")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(reminder, key, value)

    db.commit()
    db.refresh(reminder)
    return db.query(Reminder).options(joinedload(Reminder.drug)).filter(Reminder.id == reminder.id).first()


@router.delete("/{reminder_id}")
def delete_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")
    if not check_family_access(db, current_user, reminder.user_id):
        raise HTTPException(status_code=403, detail="无权删除")

    db.delete(reminder)
    db.commit()
    return {"message": "已删除"}


@router.get("/{reminder_id}/audio")
def get_reminder_audio(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reminder = db.query(Reminder).options(joinedload(Reminder.drug)).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")
    if not check_family_access(db, current_user, reminder.user_id):
        raise HTTPException(status_code=403, detail="无权查看")

    drug_name = reminder.drug.name if reminder.drug else "药品"
    dosage = reminder.dosage or "按说明书服用"
    meal_map = {
        "before_meal": "饭前",
        "after_meal": "饭后",
        "empty_stomach": "空腹",
        "before_sleep": "睡前",
    }
    meal_text = meal_map.get(reminder.meal_relation, "")
    speech_text = f"吃药提醒：请{meal_text}服用{drug_name}，{dosage}。"

    try:
        filename = generate_reminder_audio(drug_name, dosage, reminder.meal_relation)
        return {"audio_file": filename, "url": f"/audio/{filename}", "text": speech_text}
    except Exception:
        return {"audio_file": None, "url": None, "text": speech_text}


@router.post("/logs/confirm", response_model=MedicationLogOut)
def confirm_medication(
    data: MedicationLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reminder = db.query(Reminder).filter(Reminder.id == data.reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")
    if not check_family_access(db, current_user, reminder.user_id):
        raise HTTPException(status_code=403, detail="无权操作")

    now = datetime.utcnow()
    today_str = now.strftime("%Y-%m-%d")
    scheduled = datetime.strptime(f"{today_str} {reminder.reminder_time}", "%Y-%m-%d %H:%M")

    diff = (now - scheduled).total_seconds() / 60
    status = MedicationLogStatus.LATE if diff > 30 else MedicationLogStatus.TAKEN

    log = MedicationLog(
        user_id=reminder.user_id,
        reminder_id=data.reminder_id,
        scheduled_time=scheduled,
        actual_time=now,
        status=status,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("/logs/", response_model=List[MedicationLogOut])
def get_medication_logs(
    user_id: Optional[int] = None,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = user_id or current_user.id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权查看")

    query = db.query(MedicationLog).filter(MedicationLog.user_id == uid)
    if date:
        try:
            current_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            current_date = None
        if current_date is not None:
            query = query.filter(
                MedicationLog.scheduled_time >= current_date,
                MedicationLog.scheduled_time < current_date + timedelta(days=1),
            )

    return query.order_by(MedicationLog.scheduled_time.desc()).all()


@router.get("/logs/today-status")
def get_today_status(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = user_id or current_user.id
    if not check_family_access(db, current_user, uid):
        raise HTTPException(status_code=403, detail="无权查看")

    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_start = datetime.strptime(today, "%Y-%m-%d")
    today_end = today_start + timedelta(days=1)

    reminders = db.query(Reminder).options(joinedload(Reminder.drug)).filter(
        Reminder.user_id == uid,
        Reminder.status == ReminderStatus.ACTIVE,
    ).all()
    logs = db.query(MedicationLog).filter(
        MedicationLog.user_id == uid,
        MedicationLog.scheduled_time >= today_start,
        MedicationLog.scheduled_time < today_end,
    ).all()

    log_map = {log.reminder_id: log for log in logs}
    items = []
    for reminder in reminders:
        log = log_map.get(reminder.id)
        items.append(
            {
                "reminder_id": reminder.id,
                "drug_name": reminder.drug.name if reminder.drug else "未知",
                "drug_image": reminder.drug.image_path if reminder.drug else None,
                "reminder_time": reminder.reminder_time,
                "dosage": reminder.dosage,
                "meal_relation": reminder.meal_relation,
                "status": log.status if log else "pending",
                "actual_time": log.actual_time.isoformat() if log and log.actual_time else None,
            }
        )

    items.sort(key=lambda item: item["reminder_time"])

    total = len(items)
    taken = sum(1 for item in items if item["status"] in ["taken", "late"])
    missed = sum(1 for item in items if item["status"] == "missed")

    return {
        "date": today,
        "total": total,
        "taken": taken,
        "missed": missed,
        "pending": total - taken - missed,
        "items": items,
    }
