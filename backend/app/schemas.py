from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


# -------------------------------------------------------------
# Schemas de Entrada (Recebimento da Chrome Extension)
# -------------------------------------------------------------

class StepMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    timestamp: Optional[int] = Field(default=None)
    url: str = Field(default="")
    page_title: Optional[str] = Field(default="", validation_alias="pageTitle")
    tag_name: Optional[str] = Field(default="UNKNOWN", validation_alias="tagName")
    element_text: Optional[str] = Field(default="", validation_alias="elementText")
    element_id: Optional[str] = Field(default="", validation_alias="elementId")
    coordinates: Optional[dict[str, Any]] = Field(default_factory=dict)


class StepInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    step_number: Optional[int] = Field(default=1, validation_alias="stepNumber")
    metadata: StepMetadata = Field(default_factory=StepMetadata)
    image_before: Optional[str] = Field(default=None, validation_alias="imageBefore")
    image_during: Optional[str] = Field(default=None, validation_alias="imageDuring")


class ProcessFlowRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    steps: list[StepInput] = Field(..., min_length=1)


# -------------------------------------------------------------
# Schemas Estruturados para o Gemini (response_schema)
# -------------------------------------------------------------

class OnboardingStep(BaseModel):
    step_number: int = Field(description="Número sequencial do passo (1, 2, 3...)")
    system_name: str = Field(description="Nome amigável do sistema web identificado (ex: Salesforce, Jira, ERP Interno, etc.)")
    action_title: str = Field(description="Título curto e direto da ação executada (ex: Clicar em Novo Chamado)")
    detailed_instruction: str = Field(description="Instrução detalhada explicando onde o usuário deve clicar e o que preencher")
    business_rule_or_tip: str = Field(description="Regra de negócio inferida, validação esperada ou dica para o colaborador")


class ProcessAnalysisResponse(BaseModel):
    process_name: str = Field(description="Título executivo e padronizado do processo mapeado (ex: Abertura de Chamado de Suporte)")
    summary: str = Field(description="Resumo executivo em 2 a 4 parágrafos sobre a finalidade, fluxo geral e resultado esperado deste processo")
    systems_involved: list[str] = Field(description="Lista contendo os nomes dos diferentes sistemas web identificados ao longo do fluxo")
    onboarding_guide: list[OnboardingStep] = Field(description="Guia passo a passo ilustrado e sequencial de onboarding para execução do processo")
    bpmn_xml: str = Field(
        description="Código XML BPMN 2.0 rigorosamente válido contendo bpmn:collaboration, bpmn:laneSet com uma lane por sistema envolvido, nós bpmn:task/userTask, nós de início/fim, sequenceFlows e coordenadas bpmndi:BPMNDiagram sem sobreposição de nós."
    )


# -------------------------------------------------------------
# Schemas de Resposta da API
# -------------------------------------------------------------

class ProcessFlowResponse(BaseModel):
    process_id: str
    viewer_url: str
    process_name: str


class ProcessDetailResponse(BaseModel):
    process_id: str
    process_name: str
    summary: str
    systems_involved: list[str]
    onboarding_guide: list[dict[str, Any]]
    bpmn_xml: str
    created_at: str
    steps_count: int
