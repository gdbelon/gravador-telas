import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class ProcessModel(Base):
    """
    Representa o fluxo de processo mapeado pela IA a partir da gravação
    """
    __tablename__ = "processes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    process_name = Column(String(255), nullable=False, default="Processo Não Nomeado")
    summary = Column(Text, nullable=False, default="")
    systems_involved = Column(JSON, nullable=False, default=list)
    onboarding_guide = Column(JSON, nullable=False, default=list)
    bpmn_xml = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    steps = relationship(
        "ProcessStepModel",
        back_populates="process",
        cascade="all, delete-orphan",
        order_by="ProcessStepModel.step_number"
    )


class ProcessStepModel(Base):
    """
    Armazena os frames de evidência visual e os metadados brutos capturados pelo gravador
    """
    __tablename__ = "process_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    process_id = Column(String(36), ForeignKey("processes.id", ondelete="CASCADE"), nullable=False)
    step_number = Column(Integer, nullable=False)
    metadata_info = Column(JSON, nullable=False, default=dict)
    image_before = Column(Text, nullable=True)
    image_during = Column(Text, nullable=True)

    process = relationship("ProcessModel", back_populates="steps")
