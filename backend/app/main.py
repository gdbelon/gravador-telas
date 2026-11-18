import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import init_db, get_db
from app.models import ProcessModel, ProcessStepModel
from app.schemas import ProcessFlowRequest, ProcessFlowResponse, ProcessDetailResponse
from app.gemini_service import analyze_process_with_gemini, test_gemini_connection

# Configuração de logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("bpmn_recorder.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Inicializa o banco de dados e recursos globais na subida da aplicação
    """
    logger.info("Inicializando banco de dados...")
    init_db()
    logger.info("Banco de dados pronto.")
    yield


app = FastAPI(
    title="BPMN Process Recorder API",
    description="API para mapeamento automático de processos e geração de diagramas BPMN 2.0 via Gemini",
    version="1.0.0",
    lifespan=lifespan
)


# -------------------------------------------------------------
# Middlewares: CORS e Liberação Total para <iframe> (Embed)
# -------------------------------------------------------------

class IframeEmbedHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware para garantir que qualquer rota da API (especialmente /embed/{id})
    possa ser incorporada via <iframe> por qualquer aplicação externa.
    Remove 'X-Frame-Options' e define 'Content-Security-Policy: frame-ancestors *'.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if "x-frame-options" in response.headers:
            del response.headers["x-frame-options"]
        if "X-Frame-Options" in response.headers:
            del response.headers["X-Frame-Options"]

        response.headers["Content-Security-Policy"] = "frame-ancestors *"
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response


app.add_middleware(IframeEmbedHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Configuração dos Templates Jinja2
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


# -------------------------------------------------------------
# Endpoints de Visualização e Gravador Web (Sem Extensão)
# -------------------------------------------------------------

@app.get("/recorder", response_class=HTMLResponse, tags=["Gravador Web"])
async def web_recorder(request: Request):
    """
    Página web 100% simples para gravação de tela nativa no navegador sem extensões.
    """
    return templates.TemplateResponse("recorder.html", {"request": request})


@app.get("/", tags=["Health"])
async def root(request: Request):
    # Se o cliente aceitar HTML (como o navegador), abre o gravador web direto!
    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header:
        return templates.TemplateResponse("recorder.html", {"request": request})

    return {
        "status": "online",
        "service": "BPMN Process Recorder API",
        "version": "1.0.0",
        "web_recorder": "/recorder",
        "docs_url": "/docs",
        "embed_info": "Use GET /embed/{process_id} para visualizar um processo salvo."
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}


@app.get("/api/status-gemini", tags=["Diagnóstico"])
async def diagnostico_gemini():
    """
    Testa a chave configurada em GEMINI_API_KEY e retorna o diagnóstico de conexão.
    """
    result = await test_gemini_connection()
    return result


# -------------------------------------------------------------
# Endpoints Principais
# -------------------------------------------------------------

@app.post("/api/processar-fluxo", response_model=ProcessFlowResponse, status_code=status.HTTP_201_CREATED, tags=["Processos"])
async def processar_fluxo(
    payload: ProcessFlowRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Recebe os passos gravados com imagens antes/durante e metadados,
    processa com o Gemini gerando o XML BPMN 2.0 e guia de onboarding,
    e persiste tudo no banco de dados.
    """
    if not payload.steps:
        raise HTTPException(status_code=400, detail="A lista de passos não pode estar vazia.")

    logger.info(f"==> Iniciando processamento de fluxo com {len(payload.steps)} passos gravados...")

    # 1. Processamento com Gemini
    analysis = await analyze_process_with_gemini(payload.steps)

    # 2. Persistência no Banco de Dados
    process_id = str(uuid.uuid4())
    onboarding_dict_list = [step.model_dump() for step in analysis.onboarding_guide]

    process_record = ProcessModel(
        id=process_id,
        process_name=analysis.process_name,
        summary=analysis.summary,
        systems_involved=analysis.systems_involved,
        onboarding_guide=onboarding_dict_list,
        bpmn_xml=analysis.bpmn_xml
    )
    db.add(process_record)

    # Salva os passos gravados com as evidências visuais
    for step_in in payload.steps:
        step_record = ProcessStepModel(
            process_id=process_id,
            step_number=step_in.step_number or 1,
            metadata_info=step_in.metadata.model_dump(),
            image_before=step_in.image_before,
            image_during=step_in.image_during
        )
        db.add(step_record)

    db.commit()
    db.refresh(process_record)

    # 3. Monta a URL do visualizador
    base_url = settings.BASE_URL.rstrip("/")
    if "localhost" in base_url and request.base_url:
        base_url = str(request.base_url).rstrip("/")

    viewer_url = f"{base_url}/embed/{process_id}"

    logger.info(f"==> Processo '{process_record.process_name}' gerado com sucesso!")
    logger.info(f"==> Visualizador disponível em: {viewer_url}")

    return ProcessFlowResponse(
        process_id=process_id,
        viewer_url=viewer_url,
        process_name=process_record.process_name
    )


@app.get("/api/processos/{process_id}", response_model=ProcessDetailResponse, tags=["Processos"])
async def obter_processo(process_id: str, db: Session = Depends(get_db)):
    """
    Retorna o JSON completo do processo salvo.
    """
    process = db.query(ProcessModel).filter(ProcessModel.id == process_id).first()
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")

    return ProcessDetailResponse(
        process_id=process.id,
        process_name=process.process_name,
        summary=process.summary,
        systems_involved=process.systems_involved or [],
        onboarding_guide=process.onboarding_guide or [],
        bpmn_xml=process.bpmn_xml,
        created_at=process.created_at.isoformat() if process.created_at else "",
        steps_count=len(process.steps)
    )


@app.get("/embed/{process_id}", response_class=HTMLResponse, tags=["Visualizador"])
async def embed_viewer(process_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Renderiza a interface limpa, moderna e responsiva do BPMN Viewer e Guia Ilustrado,
    totalmente pronta para incorporação via <iframe>.
    """
    process = db.query(ProcessModel).filter(ProcessModel.id == process_id).first()
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")

    steps_db = sorted(process.steps, key=lambda s: s.step_number)
    onboarding_map = {item.get("step_number"): item for item in (process.onboarding_guide or [])}

    combined_steps = []
    for step_db in steps_db:
        num = step_db.step_number
        guide_info = onboarding_map.get(num, {})
        meta = step_db.metadata_info or {}

        combined_steps.append({
            "step_number": num,
            "action_title": guide_info.get("action_title") or f"Ação no elemento <{meta.get('tag_name', 'HTML')}>",
            "system_name": guide_info.get("system_name") or "Sistema Web",
            "detailed_instruction": guide_info.get("detailed_instruction") or f"Interação com o elemento '{meta.get('element_text', '')}'.",
            "business_rule_or_tip": guide_info.get("business_rule_or_tip") or "",
            "metadata": meta,
            "image_during": step_db.image_during,
            "image_before": step_db.image_before
        })

    if not combined_steps and process.onboarding_guide:
        for item in process.onboarding_guide:
            combined_steps.append({
                "step_number": item.get("step_number", 1),
                "action_title": item.get("action_title", "Ação"),
                "system_name": item.get("system_name", "Sistema"),
                "detailed_instruction": item.get("detailed_instruction", ""),
                "business_rule_or_tip": item.get("business_rule_or_tip", ""),
                "metadata": {},
                "image_during": None,
                "image_before": None
            })

    return templates.TemplateResponse(
        "embed.html",
        {
            "request": request,
            "process": process,
            "steps": steps_db,
            "combined_steps": combined_steps
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
