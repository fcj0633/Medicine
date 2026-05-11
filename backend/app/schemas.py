from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


# ========== Auth ==========
class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str
    role: str = "elderly"
    phone: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    phone: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


# ========== Family ==========
class FamilyBindRequest(BaseModel):
    elderly_username: str
    relation_name: str = "家属"


class FamilyRelationOut(BaseModel):
    id: int
    family_user_id: int
    elderly_user_id: int
    relation_name: str
    elderly_user: UserOut
    family_user: UserOut

    class Config:
        from_attributes = True


# ========== Drug ==========
class DrugCreate(BaseModel):
    name: str
    specification: Optional[str] = None
    efficacy: Optional[str] = None
    efficacy_simple: Optional[str] = None
    usage_dosage: Optional[str] = None
    usage_simple: Optional[str] = None
    frequency: Optional[str] = None
    caution: Optional[str] = None
    caution_simple: Optional[str] = None
    notes: Optional[str] = None
    target_user_id: Optional[int] = None


class DrugUpdate(BaseModel):
    name: Optional[str] = None
    specification: Optional[str] = None
    efficacy: Optional[str] = None
    efficacy_simple: Optional[str] = None
    usage_dosage: Optional[str] = None
    usage_simple: Optional[str] = None
    frequency: Optional[str] = None
    caution: Optional[str] = None
    caution_simple: Optional[str] = None
    notes: Optional[str] = None


class DrugOut(BaseModel):
    id: int
    user_id: int
    name: str
    specification: Optional[str] = None
    efficacy: Optional[str] = None
    efficacy_simple: Optional[str] = None
    usage_dosage: Optional[str] = None
    usage_simple: Optional[str] = None
    frequency: Optional[str] = None
    caution: Optional[str] = None
    caution_simple: Optional[str] = None
    image_path: Optional[str] = None
    ocr_raw_text: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ========== Reminder ==========
class ReminderCreate(BaseModel):
    drug_id: int
    reminder_time: str
    dosage: Optional[str] = None
    meal_relation: Optional[str] = None
    repeat_days: str = "everyday"
    target_user_id: Optional[int] = None


class ReminderUpdate(BaseModel):
    reminder_time: Optional[str] = None
    dosage: Optional[str] = None
    meal_relation: Optional[str] = None
    repeat_days: Optional[str] = None
    status: Optional[str] = None


class ReminderOut(BaseModel):
    id: int
    user_id: int
    drug_id: int
    reminder_time: str
    dosage: Optional[str] = None
    meal_relation: Optional[str] = None
    repeat_days: str
    status: str
    created_at: datetime
    drug: Optional[DrugOut] = None

    class Config:
        from_attributes = True


# ========== Medication Log ==========
class MedicationLogCreate(BaseModel):
    reminder_id: int


class MedicationLogOut(BaseModel):
    id: int
    user_id: int
    reminder_id: int
    scheduled_time: datetime
    actual_time: Optional[datetime] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ========== OCR Result ==========
class OCRResult(BaseModel):
    raw_text: str
    drug_name: Optional[str] = None
    specification: Optional[str] = None
    efficacy: Optional[str] = None
    efficacy_simple: Optional[str] = None
    usage_dosage: Optional[str] = None
    usage_simple: Optional[str] = None
    frequency: Optional[str] = None
    caution: Optional[str] = None
    caution_simple: Optional[str] = None
    ocr_provider: Optional[str] = None
    low_confidence: bool = False
    confidence_notice: Optional[str] = None
    ocr_meta: Optional[Dict[str, Any]] = None


# ========== Auto Reminder ==========
class AutoReminderResult(BaseModel):
    reminders: List[ReminderCreate]
    description: str
