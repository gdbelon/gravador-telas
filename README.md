# Gravador de Tela & Mapeador de Processos (100% Web)

Sistema leve e moderno de gravação de telas e interações diretamente pelo navegador, **sem necessidade de instalar extensões no Chrome**.

A cada clique ou ação detectada na tela, o sistema captura automaticamente **duas fotos limpas**:
1. **Foto 1:** O estado da tela **0,5 segundo antes** da ação (contexto prévio).
2. **Foto 2:** O estado da tela **no momento exato** da ação.

O sistema conta com visualização instantânea das fotos capturadas em uma galeria comparativa lado a lado, com zoom em tela cheia e controle de exclusão individual ou total, além de um módulo opcional de backend em Python para geração de diagramas **BPMN 2.0**.

---

## Estrutura do Projeto

```text
gravador/
├── web-recorder.html        # Página Web independente de gravação e galeria de fotos
├── backend/
│   ├── app/
│   │   ├── main.py          # API FastAPI e servidor da página web
│   │   ├── config.py        # Configurações do ambiente
│   │   ├── database.py      # Banco de dados SQLite
│   │   ├── models.py        # Modelos relacionais
│   │   ├── schemas.py       # Validações Pydantic
│   │   ├── gemini_service.py# Mapeamento BPMN 2.0 com Gemini
│   │   └── templates/
│   │       ├── recorder.html# Template do gravador web servido pelo backend
│   │       └── embed.html   # Visualizador BPMN interativo embutível
│   ├── .env                 # Variáveis de ambiente
│   └── requirements.txt     # Dependências Python
└── README.md
```

---

## Como Usar

### Opção 1: Abrir Diretamente no Navegador (Sem Instalar Nada)
Basta dar **dois cliques** no arquivo `web-recorder.html` ou abri-lo em qualquer navegador (Chrome, Edge, Brave, etc.).

1. Clique em **"Iniciar Gravação"** e selecione a tela ou janela desejada.
2. Navegue por qualquer página, programa ou sistema. A cada clique/ação, o sistema grava automaticamente as 2 fotos.
3. Clique em **"Finalizar Gravação"**.
4. Clique em **"Ver Fotos"** para visualizar a galeria comparativa instantaneamente.
5. Você pode clicar nas imagens para dar zoom em tela cheia ou usar os botões de **Excluir** para remover cliques indesejados.

---

### Opção 2: Rodar com o Backend Python (FastAPI)

Se desejar rodar com o servidor local:

1. Abra o terminal na pasta `backend`:
   ```bash
   cd backend
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

3. Inicie o servidor:
   ```bash
   python -m uvicorn app.main:app --port 8000 --reload
   ```

4. Acesse no navegador:
   👉 **[http://localhost:8000/](http://localhost:8000/)**

---

## Funcionalidades

- **100% Web Nativo**: Utiliza a Web Screen Capture API (`getDisplayMedia`), sem extensões.
- **Janela de 0,5s**: Buffer contínuo em memória que resgata o frame de exatamente 500ms antes da interação.
- **Capturas Limpas**: Fotos fiéis da tela, sem marcações ou interferências visuais.
- **Exclusão de Fotos**: Permite excluir pares individuais de ações ou limpar toda a galeria com um clique.
- **Visualizador em Tela Cheia**: Lightbox com zoom de alta resolução ao clicar em qualquer foto.
- **BPMN 2.0 (Opcional)**: Integração com IA Gemini 2.5 Flash no backend para conversão das evidências em diagramas BPMN 2.0 padronizados com raias por sistema.
