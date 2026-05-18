from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    ELDERLY = "elderly"
    FAMILY = "family"


class ReminderStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class MedicationLogStatus(str, enum.Enum):
    TAKEN = "taken"
    MISSED = "missed"
    LATE = "late"
    PENDING = "pending"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    role = Column(String(20), default=UserRole.ELDERLY)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    drugs = relationship("Drug", back_populates="user", foreign_keys="Drug.user_id")
    reminders = relationship("Reminder", back_populates="user", foreign_keys="Reminder.user_id")
    medication_logs = relationship("MedicationLog", back_populates="user", foreign_keys="MedicationLog.user_id")


class FamilyRelation(Base):
    __tablename__ = "family_relations"

    id = Column(Integer, primary_key=True, index=True)
    family_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    elderly_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    relation_name = Column(String(50), default="家属")
    created_at = Column(DateTime, default=datetime.utcnow)

    family_user = relationship("User", foreign_keys=[family_user_id])
    elderly_user = relationship("User", foreign_keys=[elderly_user_id])


class Drug(Base):
    __tablename__ = "drugs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(200), nullable=False)
    specification = Column(String(200), nullable=True)
    efficacy = Column(Text, nullable=True)
    efficacy_simple = Column(Text, nullable=True)
    usage_dosage = Column(Text, nullable=True)
    usage_simple = Column(Text, nullable=True)
    frequency = Column(String(100), nullable=True)
    caution = Column(Text, nullable=True)
    caution_simple = Column(Text, nullable=True)
    image_path = Column(String(500), nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="drugs", foreign_keys=[user_id])
    reminders = relationship("Reminder", back_populates="drug")


class DrugCatalog(Base):
    __tablename__ = "drug_catalog"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    normalized_name = Column(String(200), nullable=False, unique=True, index=True)
    category = Column(String(100), nullable=True)
    specification = Column(String(200), nullable=True)
    efficacy = Column(Text, nullable=True)
    efficacy_simple = Column(Text, nullable=True)
    usage_dosage = Column(Text, nullable=True)
    usage_simple = Column(Text, nullable=True)
    frequency = Column(String(100), nullable=True)
    caution = Column(Text, nullable=True)
    caution_simple = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    drug_id = Column(Integer, ForeignKey("drugs.id"), nullable=False)
    reminder_time = Column(String(10), nullable=False)  # HH:MM format
    dosage = Column(String(100), nullable=True)
    meal_relation = Column(String(20), nullable=True)  # before_meal / after_meal / empty
    repeat_days = Column(String(50), default="everyday")  # everyday / mon,tue,wed...
    status = Column(String(20), default=ReminderStatus.ACTIVE)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reminders", foreign_keys=[user_id])
    drug = relationship("Drug", back_populates="reminders")
    medication_logs = relationship("MedicationLog", back_populates="reminder")


class MedicationLog(Base):
    __tablename__ = "medication_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reminder_id = Column(Integer, ForeignKey("reminders.id"), nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    actual_time = Column(DateTime, nullable=True)
    status = Column(String(20), default=MedicationLogStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="medication_logs")
    reminder = relationship("Reminder", back_populates="medication_logs")
