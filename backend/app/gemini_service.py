import base64
import json
import logging
import re
from typing import Optional
from app.config import settings
from app.schemas import StepInput, ProcessAnalysisResponse, OnboardingStep

logger = logging.getLogger("bpmn_recorder.gemini")

SYSTEM_INSTRUCTION = """
Você é um Arquiteto de Processos Corporativos e Especialista Sênior em Notação BPMN 2.0 (OMG) e Engenharia de Software.
Sua missão é analisar uma sequência cronológica de interações web capturadas de um usuário executando um processo corporativo através de múltiplos sistemas web.

Para cada passo registrado, você receberá:
- Metadados técnicos: URL, Título da Página, Tag do Elemento, Texto do Elemento clicado, ID e Coordenadas.
- Imagem 'image_during' contendo um marcador visual vermelho (círculo semitransparente) exatamente sobre o elemento clicado.
- Imagem 'image_before' que preserva o estado da tela momentos antes do clique (útil para menus dropdown abertos, janelas modais ou hover).

SUAS TAREFAS:
1. Identifique os sistemas web participantes através dos domínios das URLs e títulos de tela (ex: "ERP SAP", "Jira Software", "Portal de Compras", "Google Workspace", etc.).
2. Atribua um título corporativo claro ao processo em `process_name`.
3. Escreva um resumo executivo completo e profissional em `summary`.
4. Elabore um guia sequencial de onboarding em `onboarding_guide`. Para cada passo, inclua:
   - `step_number`: número sequencial (1, 2, 3...)
   - `system_name`: nome amigável do sistema
   - `action_title`: ação executada em tom de comando (ex: "Acessar menu Financeiro", "Clicar no botão Novo Pedido")
   - `detailed_instruction`: explicação de onde encontrar o elemento, preenchimentos necessários e finalidade
   - `business_rule_or_tip`: dica de negócio, validações exigidas ou boas práticas observadas
5. Gere o XML BPMN 2.0 completo e rigorosamente válido em `bpmn_xml`:
   - Utilize a declaração XML e os namespaces oficiais:
     xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
     xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
     xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
     xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
   - Crie uma <bpmn:collaboration> com um <bpmn:participant> (Pool) representando o processo geral.
   - Dentro do <bpmn:process>, adicione um <bpmn:laneSet> com uma <bpmn:lane> para CADA sistema web identificado em `systems_involved`.
   - Adicione os elementos do fluxo: <bpmn:startEvent>, nós de tarefa <bpmn:userTask> (com atributo name claro descrevendo a ação) associados a cada raia correspondente, nós de decisão <bpmn:exclusiveGateway> se houver caminhos condicionais óbvios, e um <bpmn:endEvent>.
   - Conecte todos os nós através de <bpmn:sequenceFlow>.
   - Crie a seção <bpmndi:BPMNDiagram> e <bpmndi:BPMNPlane bpmnElement="Collaboration_1"> contendo:
     * O <bpmndi:BPMNShape> da Pool com largura suficiente (ex: x="160", y="80", width="calculada", height="calculada").
     * Um <bpmndi:BPMNShape> para cada Lane, dividindo a altura total da Pool.
     * Os <bpmndi:BPMNShape> de cada StartEvent (width="36", height="36"), UserTask (width="110", height="70"), Gateway (width="50", height="50") e EndEvent (width="36", height="36").
     * Posicione os nós horizontalmente da esquerda para a direita (espaçamento de ~160px entre nós sucessivos) e verticalmente centralizados dentro da raia correspondente, evitando QUALQUER sobreposição.
     * Todos os <bpmndi:BPMNEdge> para os sequenceFlows com os <di:waypoint> calculados (saindo do lado direito do nó anterior e entrando no lado esquerdo do nó seguinte).
   - Garanta que o XML não contenha caracteres soltos ou tags não fechadas, pois ele será carregado diretamente pela biblioteca `bpmn-js`.
"""


def clean_base64(data_url: Optional[str]) -> Optional[bytes]:
    """
    Remove prefixos como 'data:image/jpeg;base64,' e decodifica a string base64 para bytes.
    """
    if not data_url:
        return None
    try:
        if "," in data_url:
            data_url = data_url.split(",", 1)[1]
        return base64.b64decode(data_url)
    except Exception as e:
        logger.warning(f"Falha ao decodificar base64 de imagem: {e}")
        return None


def extract_system_name_from_url(url: str, title: str = "") -> str:
    """
    Extrai um nome de sistema amigável com base na URL ou título da página
    """
    if not url:
        return title if title else "Portal Corporativo"
    try:
        from urllib.parse import urlparse
        hostname = urlparse(url).netloc
        if not hostname:
            return title if title else "Sistema Web"
        
        # Limpa www e portas
        clean_host = hostname.replace("www.", "").split(":")[0]
        parts = clean_host.split(".")
        if len(parts) >= 2:
            domain_name = parts[0].capitalize()
            return f"Sistema {domain_name}"
        return clean_host
    except Exception:
        return title if title else "Sistema Corporativo"


def generate_fallback_process(steps: list[StepInput]) -> ProcessAnalysisResponse:
    """
    Gera um processo BPMN 2.0 válido e estruturado caso a chave do Gemini não esteja configurada
    ou ocorra timeout/falha de quota, garantindo que o usuário consiga visualizar a tela completa.
    """
    first_title = steps[0].metadata.page_title if steps[0].metadata.page_title else "Navegação Corporativa"
    process_name = f"Processo: {first_title[:45]}"

    # Descobre sistemas envolvidos
    systems_set = set()
    onboarding_steps: list[OnboardingStep] = []

    for idx, s in enumerate(steps, start=1):
        meta = s.metadata
        sys_name = extract_system_name_from_url(meta.url, meta.page_title)
        systems_set.add(sys_name)

        action_name = meta.element_text.strip() if meta.element_text else f"Ação em {meta.tag_name}"
        if len(action_name) > 40:
            action_name = action_name[:37] + "..."

        onboarding_steps.append(
            OnboardingStep(
                step_number=idx,
                system_name=sys_name,
                action_title=f"Clicar em '{action_name}'",
                detailed_instruction=f"No sistema {sys_name}, acesse a página '{meta.page_title}' e clique no elemento <{meta.tag_name}> identificado com o texto '{meta.element_text}'.",
                business_rule_or_tip=f"Verifique se todos os campos necessários estão preenchidos antes de interagir com o elemento ({meta.element_id or 'sem ID'})."
            )
        )

    systems_list = sorted(list(systems_set))
    if not systems_list:
        systems_list = ["Sistema Corporativo"]

    summary = (
        f"Este processo mapeia a jornada operacional registrada com {len(steps)} interações "
        f"através de {len(systems_list)} sistema(s) corporativo(s): {', '.join(systems_list)}. "
        f"A sequência contempla a entrada de dados, transição entre interfaces e confirmação de ações chave."
    )

    # Gera BPMN XML válido com raias e coordenadas calculadas
    bpmn_xml = build_valid_bpmn_xml(process_name, systems_list, onboarding_steps)

    return ProcessAnalysisResponse(
        process_name=process_name,
        summary=summary,
        systems_involved=systems_list,
        onboarding_guide=onboarding_steps,
        bpmn_xml=bpmn_xml
    )


def build_valid_bpmn_xml(process_name: str, systems: list[str], guide_steps: list[OnboardingStep]) -> str:
    """
    Constrói um XML BPMN 2.0 diagramado geometricamente sem sobreposição para visualização imediata no bpmn-js.
    """
    lane_height = 140
    pool_height = max(180, len(systems) * lane_height)
    step_width = 170
    pool_width = max(800, 260 + (len(guide_steps) + 1) * step_width)

    pool_x = 160
    pool_y = 80

    # Dicionário de lanes para posições Y
    lane_y_map = {}
    for i, sys in enumerate(systems):
        lane_y_map[sys] = {
            "lane_id": f"Lane_{i+1}",
            "y": pool_y + (i * lane_height),
            "height": lane_height,
            "center_y": pool_y + (i * lane_height) + (lane_height // 2)
        }

    # Gera nós e fluxos
    lanes_xml_parts = []
    flow_nodes_xml = []
    sequence_flows_xml = []
    shapes_di_xml = []
    edges_di_xml = []

    # Start Event
    first_sys = guide_steps[0].system_name if guide_steps else systems[0]
    start_y = lane_y_map.get(first_sys, list(lane_y_map.values())[0])["center_y"] - 18
    start_x = pool_x + 50

    flow_nodes_xml.append(f'<bpmn:startEvent id="StartEvent_1" name="Início do Fluxo"><bpmn:outgoing>Flow_start</bpmn:outgoing></bpmn:startEvent>')
    shapes_di_xml.append(f'''<bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
      <dc:Bounds x="{start_x}" y="{start_y}" width="36" height="36" />
      <bpmndi:BPMNLabel><dc:Bounds x="{start_x - 10}" y="{start_y + 42}" width="60" height="14" /></bpmndi:BPMNLabel>
    </bpmndi:BPMNShape>''')

    prev_node_id = "StartEvent_1"
    prev_x = start_x + 36
    prev_y = start_y + 18

    # Cria nós para cada passo
    nodes_by_lane = {sys: ["StartEvent_1"] if sys == first_sys else [] for sys in systems}

    for idx, step in enumerate(guide_steps, start=1):
        task_id = f"Activity_Step_{idx}"
        sys_info = lane_y_map.get(step.system_name, list(lane_y_map.values())[0])
        nodes_by_lane.setdefault(step.system_name, []).append(task_id)

        task_x = pool_x + 70 + (idx * step_width)
        task_y = sys_info["center_y"] - 38
        task_w = 110
        task_h = 75

        flow_id = f"Flow_{idx}"
        incoming_flow = "Flow_start" if idx == 1 else f"Flow_{idx-1}"
        outgoing_flow = flow_id

        # Nome limpo e seguro para XML
        safe_action_title = step.action_title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', '&quot;')

        flow_nodes_xml.append(f'''<bpmn:userTask id="{task_id}" name="{safe_action_title}">
      <bpmn:incoming>{incoming_flow}</bpmn:incoming>
      <bpmn:outgoing>{outgoing_flow}</bpmn:outgoing>
    </bpmn:userTask>''')

        shapes_di_xml.append(f'''<bpmndi:BPMNShape id="{task_id}_di" bpmnElement="{task_id}">
      <dc:Bounds x="{task_x}" y="{task_y}" width="{task_w}" height="{task_h}" />
    </bpmndi:BPMNShape>''')

        # Flow ligando o nó anterior
        sequence_flows_xml.append(f'<bpmn:sequenceFlow id="{incoming_flow}" sourceRef="{prev_node_id}" targetRef="{task_id}" />')
        edges_di_xml.append(f'''<bpmndi:BPMNEdge id="{incoming_flow}_di" bpmnElement="{incoming_flow}">
      <di:waypoint x="{prev_x}" y="{prev_y}" />
      <di:waypoint x="{task_x}" y="{task_y + (task_h // 2)}" />
    </bpmndi:BPMNEdge>''')

        prev_node_id = task_id
        prev_x = task_x + task_w
        prev_y = task_y + (task_h // 2)

    # End Event
    end_x = prev_x + 50
    end_y = prev_y - 18
    final_flow_id = f"Flow_{len(guide_steps)}"
    last_sys = guide_steps[-1].system_name if guide_steps else systems[0]
    nodes_by_lane.setdefault(last_sys, []).append("EndEvent_1")

    flow_nodes_xml.append(f'<bpmn:endEvent id="EndEvent_1" name="Fim do Fluxo"><bpmn:incoming>{final_flow_id}</bpmn:incoming></bpmn:endEvent>')
    shapes_di_xml.append(f'''<bpmndi:BPMNShape id="EndEvent_1_di" bpmnElement="EndEvent_1">
      <dc:Bounds x="{end_x}" y="{end_y}" width="36" height="36" />
      <bpmndi:BPMNLabel><dc:Bounds x="{end_x - 10}" y="{end_y + 42}" width="60" height="14" /></bpmndi:BPMNLabel>
    </bpmndi:BPMNShape>''')

    sequence_flows_xml.append(f'<bpmn:sequenceFlow id="{final_flow_id}" sourceRef="{prev_node_id}" targetRef="EndEvent_1" />')
    edges_di_xml.append(f'''<bpmndi:BPMNEdge id="{final_flow_id}_di" bpmnElement="{final_flow_id}">
      <di:waypoint x="{prev_x}" y="{prev_y}" />
      <di:waypoint x="{end_x}" y="{end_y + 18}" />
    </bpmndi:BPMNEdge>''')

    # Monta Lanes XML
    lane_shapes_di = []
    for sys in systems:
        lane_info = lane_y_map[sys]
        node_refs = "".join([f"<bpmn:flowNodeRef>{n}</bpmn:flowNodeRef>" for n in nodes_by_lane.get(sys, [])])
        safe_sys = sys.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lanes_xml_parts.append(f'''<bpmn:lane id="{lane_info['lane_id']}" name="{safe_sys}">
        {node_refs}
      </bpmn:lane>''')

        lane_shapes_di.append(f'''<bpmndi:BPMNShape id="{lane_info['lane_id']}_di" bpmnElement="{lane_info['lane_id']}" isHorizontal="true">
        <dc:Bounds x="{pool_x + 30}" y="{lane_info['y']}" width="{pool_width - 30}" height="{lane_info['height']}" />
      </bpmndi:BPMNShape>''')

    safe_proc_name = process_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
  id="Definitions_AutoGenerated"
  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:collaboration id="Collaboration_1">
    <bpmn:participant id="Participant_1" name="{safe_proc_name}" processRef="Process_1" />
  </bpmn:collaboration>
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:laneSet id="LaneSet_1">
      {"".join(lanes_xml_parts)}
    </bpmn:laneSet>
    {"".join(flow_nodes_xml)}
    {"".join(sequence_flows_xml)}
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Collaboration_1">
      <bpmndi:BPMNShape id="Participant_1_di" bpmnElement="Participant_1" isHorizontal="true">
        <dc:Bounds x="{pool_x}" y="{pool_y}" width="{pool_width}" height="{pool_height}" />
      </bpmndi:BPMNShape>
      {"".join(lane_shapes_di)}
      {"".join(shapes_di_xml)}
      {"".join(edges_di_xml)}
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>"""
    return xml


async def test_gemini_connection() -> dict:
    """
    Testa a chave e conectividade com a API Gemini
    """
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        return {"ok": False, "reason": "GEMINI_API_KEY está vazia no arquivo .env."}

    if not api_key.startswith("AIzaSy"):
        return {
            "ok": False,
            "reason": (
                f"A chave configurada ('{api_key[:8]}...') não possui o padrão do Google AI Studio. "
                "Chaves do Gemini geralmente iniciam com 'AIzaSy' e possuem 39 caracteres. "
                "Gere uma chave gratuita em: https://aistudio.google.com/apikey"
            )
        }

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Responda apenas 'OK'."
        )
        return {"ok": True, "model": "gemini-2.5-flash", "response": response.text.strip()}
    except Exception as e:
        # Tenta com gemini-2.0-flash ou 1.5-flash
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents="Responda apenas 'OK'."
            )
            return {"ok": True, "model": "gemini-2.0-flash", "response": response.text.strip()}
        except Exception as e2:
            return {"ok": False, "error": str(e), "fallback_error": str(e2)}


async def analyze_process_with_gemini(steps: list[StepInput]) -> ProcessAnalysisResponse:
    """
    Envia as evidências multimodais (prints com marcador e metadados) para o Gemini
    utilizando Structured Outputs com o SDK oficial 'google-genai'.
    """
    api_key = settings.GEMINI_API_KEY.strip()

    if not api_key:
        logger.warning("GEMINI_API_KEY não informada. Utilizando síntese algorítmica para BPMN 2.0.")
        return generate_fallback_process(steps)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # Monta a lista multimodal intercalando metadados descritivos e partes de imagens
        contents_parts = []
        contents_parts.append(
            f"Por favor, analise a sequência abaixo contendo {len(steps)} interações capturadas do usuário. "
            f"Extraia o fluxo de processos, sistemas envolvidos, o guia de onboarding passo a passo "
            f"e o XML BPMN 2.0 completo com raias e coordenadas geométricas exatas."
        )

        for step in steps:
            meta = step.metadata
            coords = meta.coordinates or {}
            step_desc = (
                f"\n--- PASSO {step.step_number} ---\n"
                f"• URL: {meta.url}\n"
                f"• Título da Página: {meta.page_title}\n"
                f"• Elemento Clicado: <{meta.tag_name}> (ID: '{meta.element_id}')\n"
                f"• Texto do Elemento: '{meta.element_text}'\n"
                f"• Coordenadas X/Y: ({coords.get('clientX', 'N/A')}, {coords.get('clientY', 'N/A')})\n"
            )
            contents_parts.append(step_desc)

            # Imagem com o marcador do clique (image_during)
            during_bytes = clean_base64(step.image_during)
            if during_bytes:
                contents_parts.append(
                    types.Part.from_bytes(data=during_bytes, mime_type="image/jpeg")
                )
                contents_parts.append(f"[Print no momento exato do clique no Passo {step.step_number} com marcador vermelho]")

            # Imagem anterior (image_before) se existir
            before_bytes = clean_base64(step.image_before)
            if before_bytes and before_bytes != during_bytes:
                contents_parts.append(
                    types.Part.from_bytes(data=before_bytes, mime_type="image/jpeg")
                )
                contents_parts.append(f"[Print antes do clique no Passo {step.step_number} (contexto prévio)]")

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=ProcessAnalysisResponse,
            temperature=0.2
        )

        # Lista de modelos por ordem de preferência
        models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        last_error = None

        for model_name in models_to_try:
            try:
                logger.info(f"Tentando gerar BPMN com modelo '{model_name}'...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents_parts,
                    config=config
                )

                if response.text:
                    parsed_data = json.loads(response.text)
                    result = ProcessAnalysisResponse.model_validate(parsed_data)

                    # Validação do XML BPMN
                    if "```" in result.bpmn_xml:
                        cleaned_xml = re.sub(r"^```(?:xml)?\s*", "", result.bpmn_xml.strip(), flags=re.MULTILINE)
                        cleaned_xml = re.sub(r"\s*```$", "", cleaned_xml.strip(), flags=re.MULTILINE)
                        result.bpmn_xml = cleaned_xml

                    if "<bpmn:definitions" not in result.bpmn_xml:
                        result.bpmn_xml = build_valid_bpmn_xml(result.process_name, result.systems_involved, result.onboarding_guide)

                    logger.info(f"BPMN gerado com sucesso pelo modelo '{model_name}'.")
                    return result

            except Exception as model_err:
                logger.warning(f"Tentativa com '{model_name}' falhou: {model_err}. Tentando próximo modelo...")
                last_error = model_err

        # Se nenhum modelo funcionou, registra e usa síntese estruturada
        logger.error(f"Todos os modelos falharam. Último erro: {last_error}. Aplicando gerador geométrico de fallback.")
        return generate_fallback_process(steps)

    except Exception as e:
        logger.error(f"Erro geral no Gemini service: {e}. Aplicando gerador geométrico de fallback.")
        return generate_fallback_process(steps)
