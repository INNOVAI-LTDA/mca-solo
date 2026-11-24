# Guia de Implementação do MCA Framework

| Campo | Valor |
|---|---|
| **Documento** | `docs/implementation_guide.md` |
| **Versão** | 1.1 |
| **Data** | 2026-11-24 |
| **Status** | Guia prático consolidado |
| **Dependência** | `docs/arquitetura_molde_fundamentacao.md` (v1); `docs/arquitetura_molde_v2_orquestracao_gestao.md` (v2); `docs/arquitetura_molde_v3_dags_separacao.md` (v3); `docs/contracts.md`; `docs/observability.md`; `docs/examples.md` |
| **Escopo** | Guia passo-a-passo para desenvolvedores implementarem componentes, composições e testes no MCA Framework |
| **Fora de escopo** | Fundamentação teórica (ver v1, v2, v3); exemplos detalhados de código (ver `docs/examples.md`) |
| **Público** | Desenvolvedores de componentes, desenvolvedores de composição, arquitetos, QA |

---

## Sumário

1. [Introdução e propósito](#1-introducao-e-proposito)
2. [Pré-requisitos](#2-pre-requisitos)
3. [Passo 1 — Preparar o esqueleto](#3-passo-1--preparar-o-esqueleto)
4. [Passo 2 — Implementar um componente](#4-passo-2--implementar-um-componente)
5. [Passo 3 — Registrar o componente](#5-passo-3--registrar-o-componente)
6. [Passo 4 — Definir e executar uma App DAG](#6-passo-4--definir-e-executar-uma-app-dag)
7. [Passo 5 — Configurar observabilidade](#7-passo-5--configurar-observabilidade)
8. [Passo 6 — Testar](#8-passo-6--testar)
9. [Passo 7 — Deploy](#9-passo-7--deploy)
10. [Passo 8 — Monitorar e operar](#10-passo-8--monitorar-e-operar)
11. [Checklist de conformidade](#11-checklist-de-conformidade)
12. [Troubleshooting](#12-troubleshooting)
13. [Referências cruzadas](#13-referencias-cruzadas)

---

## 1. Introdução e propósito

### 1.1. Para quem é este guia

Este guia é destinado a desenvolvedores que precisam:

- **Implementar um componente** (Fetcher, Ingestor, Transformer, Validator, URN Generator)
- **Definir uma composição** (App DAG) que orquestra componentes
- **Configurar observabilidade** (métricas, logs, traces, explicabilidade, responsabilização, auditabilidade)
- **Testar** componentes e composições
- **Implantar** o framework em ambiente de desenvolvimento ou produção

### 1.2. O que este guia não é

Este guia **não é**:

- Um documento de fundamentação teórica (ver v1, v2, v3)
- Um catálogo de exemplos de código (ver `docs/examples.md`)
- Uma especificação de contratos (ver `docs/contracts.md`)
- Uma referência de observabilidade (ver `docs/observability.md`)

### 1.3. Como usar este guia

Este guia é **processual**: cada passo constrói sobre o anterior. A sequência recomendada é:

```mermaid
flowchart LR
    P1["Passo 1<br/>Esqueleto"] --> P2["Passo 2<br/>Componente"]
    P2 --> P3["Passo 3<br/>Registro"]
    P3 --> P4["Passo 4<br/>App DAG"]
    P4 --> P5["Passo 5<br/>Observabilidade"]
    P5 --> P6["Passo 6<br/>Testes"]
    P6 --> P7["Passo 7<br/>Deploy"]
    P7 --> P8["Passo 8<br/>Operação"]

    style P1 fill:#E8F5E9,stroke:#2E7D32
    style P2 fill:#E3F2FD,stroke:#1565C0
    style P3 fill:#FFF3E0,stroke:#E65100
    style P4 fill:#F3E5F5,stroke:#7B1FA2
    style P5 fill:#FFF8E1,stroke:#F57F17
    style P6 fill:#E0F2F1,stroke:#00695C
    style P7 fill:#FBE9E7,stroke:#BF360C
    style P8 fill:#ECEFF1,stroke:#37474F
```

**Tempo estimado**: 2–4 horas para um desenvolvedor experiente, do zero até o primeiro deploy funcional.

### 1.4. Convenções deste guia

- **Código**: blocos de código Python e YAML são executáveis (podem ser copiados e colados)
- **Caminhos**: caminhos de arquivo são relativos à raiz do projeto (`mca-framework/`)
- **Variáveis**: `${VARIAVEL}` indica variável de ambiente ou placeholder
- **Comandos**: comandos de shell são mostrados com `$` (Linux/macOS) ou `PS>` (Windows PowerShell)
- **Notas**: caixas destacadas com "Nota:", "Atenção:" ou "Dica:"

---

## 2. Pré-requisitos

### 2.1. Ambiente de desenvolvimento

| Requisito | Versão mínima | Verificação |
|---|---|---|
| Python | 3.11 | `python --version` |
| pip | 23.0 | `pip --version` |
| Git | 2.30 | `git --version` |
| Docker | 24.0 | `docker --version` |
| Docker Compose | 2.20 | `docker-compose --version` |
| Neo4j | 5.20 | (via Docker) |
| PostgreSQL | 17 | (via Docker) |

### 2.2. Ferramentas opcionais

| Ferramenta | Finalidade | Instalação |
|---|---|---|
| VS Code | Editor de código | [vscode.dev](https://vscode.dev) |
| Neo4j Desktop | Interface gráfica do Neo4j | [neo4j.com/download](https://neo4j.com/download/) |
| pgAdmin | Interface gráfica do PostgreSQL | [pgadmin.org](https://www.pgadmin.org/) |
| Prometheus | Backend de métricas | (via Docker) |
| Grafana | Dashboards | (via Docker) |

### 2.3. Conhecimentos necessários

| Conhecimento | Nível | Referência |
|---|---|---|
| Python (básico) | Intermediário | [docs.python.org](https://docs.python.org/3/) |
| YAML (básico) | Básico | [yaml.org](https://yaml.org/) |
| Docker (básico) | Básico | [docs.docker.com](https://docs.docker.com/) |
| Neo4j (básico) | Básico | [neo4j.com/docs](https://neo4j.com/docs/) |
| Arquitetura Hexagonal | Conceitual | `docs/arquitetura_molde_fundamentacao.md` (v1, seção 3.3.3) |
| LRMoo | Conceitual | `SPEC_SOLO_MCA.md` (seção 2.2) |

### 2.4. Acesso a APIs externas

| API | Finalidade | Credenciais |
|---|---|---|
| API do Senado Federal | Extrair normas L1–L4 | Pública (sem autenticação) |
| INLABS (Ro-DOU) | Extrair publicações DOU L6–L8 | `INLABS_PORTAL_LOGIN`, `INLABS_PORTAL_PASSWORD` |
| OpenAI (ou outro LLM) | Extração de metadados | `OPENAI_API_KEY` |
| n8n (opcional) | Orquestração visual | `N8N_WEBHOOK_URL` |

---

## 3. Passo 1 — Preparar o esqueleto

### 3.1. Clonar o repositório

```bash
# Linux/macOS
git clone https://github.com/innovai-ltda/mca-framework.git
cd mca-framework

# Windows PowerShell
git clone https://github.com/innovai-ltda/mca-framework.git
cd mca-framework
```

### 3.2. Executar o script de criação de esqueleto

```powershell
# Windows PowerShell
.\scripts\create_dir.ps1 -RootPath "."
```

```bash
# Linux/macOS
bash scripts/create_dir.sh --root .
```

**Resultado esperado**:

```
[OK]   DIR  framework/core/dags (Core DAGs - Gestão)
[OK]   FILE metrics_collection.yaml
[OK]   FILE health_check.yaml
[OK]   FILE component_lifecycle.yaml
[OK]   FILE alerting.yaml
[OK]   FILE core/ports.py
[OK]   FILE core/entities.py
[OK]   FILE core/exceptions.py
...
[OK]   DIR  application/dags (App DAGs - Orquestração)
[OK]   FILE dags/rodou_solo_pipeline.yaml
[OK]   FILE dags/senado_ncm_ingestion.yaml
...
```

### 3.3. Verificar a estrutura

```bash
tree -L 3 -d
```

**Estrutura esperada**:

```
mca-framework/
├── framework/
│   ├── core/
│   │   └── dags/
│   ├── management/
│   │   ├── metrics/
│   │   ├── logging/
│   │   ├── tracing/
│   │   ├── alerting/
│   │   └── dashboard/
│   ├── execution/
│   └── infrastructure/
│       └── config/
├── application/
│   ├── dags/
│   ├── components/
│   └── config/
├── deployment/
│   ├── kubernetes/
│   └── helm/
├── tests/
│   ├── framework/
│   └── application/
└── docs/
```

### 3.4. Instalar dependências

```bash
# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/macOS
# ou: venv\Scripts\activate  # Windows

# Instalar dependências
pip install -e ".[dev,ai]"
```

### 3.5. Verificar instalação

```bash
python -c "import framework; print(framework.__version__)"
# Saída esperada: 1.0.0
```

---

## 4. Passo 2 — Implementar um componente

### 4.1. Escolher o tipo de componente

Antes de implementar, identifique qual contrato seu componente deve implementar:

| Tipo de componente | Contrato | Quando usar |
|---|---|---|
| **Fetcher** | `FetcherPort` | Extrair dados de fonte externa (API, arquivo, banco) |
| **Ingestor** | `IngestPort` | Persistir dados em destino (Neo4j, PostgreSQL, S3) |
| **Transformer** | `TransformerPort` | Transformar dados (LLM, normalização, enriquecimento) |
| **Validator** | `ValidatorPort` | Validar invariantes de domínio (Kelsen, temporal, schema) |
| **URN Generator** | `URNPort` | Gerar e validar URNs canônicos |

### 4.2. Criar o arquivo do componente

```bash
# Exemplo: criar um Fetcher para a API do Senado
touch application/components/senado_adapter.py
```

### 4.3. Implementar o contrato

Abra o arquivo e implemente o contrato. Veja `docs/examples.md` para exemplos completos.

**Exemplo mínimo (Fetcher)**:

```python
# application/components/senado_adapter.py
from framework.core.ports import FetcherPort, FetchResult
from typing import Dict, Any


class SenadoAdapter(FetcherPort):
    """Adapter para API do Senado Federal (Níveis 1-4)."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def buscar(self, config: Dict[str, Any]) -> FetchResult:
        """Extrai dados da API do Senado."""
        # Sua lógica de extração aqui
        items = []  # Lista de dicionários com dados extraídos
        metadata = {"source": "senado", "timestamp": "..."}
        errors = []  # Lista de erros não fatais
        return FetchResult(
            items=items,
            metadata=metadata,
            errors=errors,
        )

    def validar_config(self, config: Dict[str, Any]) -> bool:
        """Valida se a configuração é válida."""
        return "normas" in config

    def metadados(self) -> Dict[str, Any]:
        """Retorna metadados do adapter."""
        return {
            "name": "senado_adapter",
            "version": "1.0.0",
        }
```

### 4.4. Verificar conformidade do contrato

Seu componente deve:

- [ ] Implementar todos os métodos do contrato (ver `docs/contracts.md`)
- [ ] Retornar os tipos corretos (`FetchResult`, `IngestResult`, etc.)
- [ ] Incluir proveniência nos metadados (source, timestamp, version)
- [ ] Tratar erros sem interromper o lote (quando aplicável)
- [ ] Não implementar lógica de observabilidade (isso é responsabilidade do framework)
- [ ] **Herdar nominalmente** da ABC de porta (Regra de Ouro — duck-typing é rejeitado pelo `ComponentRegistry`)

### 4.5. Exemplos completos

Para exemplos completos de implementação, consulte:

- `docs/examples.md` — Seção 2 (Fetchers), Seção 3 (Ingestors), etc.
- `application/components/` — Diretório com adapters de referência

---

## 5. Passo 3 — Registrar o componente

### 5.1. Criar o manifesto do componente

Crie um arquivo YAML descrevendo seu componente:

```yaml
# application/components/senado_adapter.yaml
component:
  id: senado_adapter
  type: application.components.senado_adapter.SenadoAdapter
  version: 1.0.0
  contract_version: 1.0.0
  description: "Adapter para API do Senado Federal (Níveis 1-4)"
dependencies:
  required_interfaces: [FetcherPort]
  required_services: []
  environment_variables: []
metadata:
  author: "Seu Nome"
  license: "GPL-3.0"
  repository: "https://github.com/innovai-ltda/mca-framework"
```

### 5.2. Registrar no framework

O registro é feito via `ComponentRegistry` (ID 2.1), que valida **herança nominal** da ABC de porta (Regra de Ouro: `REG-02`). Objetos que apenas "parecem" uma porta (duck-typing) são rejeitados.

```python
# application/bootstrap.py
from framework.execution.orchestrator import ComponentRegistry, Orchestrator
from application.components.senado_adapter import SenadoAdapter

registry = ComponentRegistry()
registry.register(
    component_id="senado_adapter",
    component=SenadoAdapter({"normas": [("EMC", 33, 2001)]}),
)

# Alternativamente, registre diretamente via Orchestrator:
orchestrator = Orchestrator()
orchestrator.register_component(
    "senado_adapter",
    SenadoAdapter({"normas": [("EMC", 33, 2001)]}),
)
```

### 5.3. Verificar registro

```python
# Verificar se o componente foi registrado
print(registry.list())
# Saída esperada: ["senado_adapter"]

# Verificar presença
print(registry.has("senado_adapter"))
# Saída esperada: True

# Recuperar a instância
componente = registry.get("senado_adapter")
print(componente.metadados())
# Saída esperada: {"name": "senado_adapter", "version": "1.0.0", ...}
```

---

## 6. Passo 4 — Definir e executar uma App DAG

### 6.1. Criar o arquivo da App DAG

```bash
# Criar uma nova App DAG
touch application/dags/minha_pipeline.yaml
```

### 6.2. Definir a estrutura da DAG

```yaml
# application/dags/minha_pipeline.yaml
dag:
  id: minha_pipeline
  description: "Minha primeira pipeline no MCA Framework"
  schedule: "0 8 * * MON-FRI"  # 8h da manhã, dias úteis
  owner: dev_team
  immutable: false  # Obrigatório para App DAGs (VAL-09)
  tags: [exemplo, tutorial]

components:
  - id: meu_fetcher
    type: application.components.senado_adapter.SenadoAdapter
    config:
      normas:
        - tipo: EMC
          numero: 33
          ano: 2001
  - id: meu_ingestor
    type: application.components.neo4j_adapter.Neo4jAdapter
    config:
      uri: bolt://localhost:7687
      user: neo4j
      password: ${NEO4J_PASSWORD}

pipeline:
  stages:
    - id: extrair_dados
      component: meu_fetcher
      output: dados_extraidos
    - id: ingerir_dados
      component: meu_ingestor
      input: dados_extraidos
      output: resultado_ingestao
      depends_on: [extrair_dados]

connectors:
  - source: extrair_dados
    target: ingerir_dados
    type: synchronous
    protocol: memory  # ou http, webhook, bolt, etc.

notifications:
  on_success:
    - type: log
      level: INFO
  on_failure:
    - type: alert
      channel: pipeline_alerts
      severity: HIGH
```

### 6.3. Validar a DAG (via `DAGParser` — ID 1.4)

A validação é **programática**, via `DAGParser`. Não há CLI dedicado — o parser é a API pública.

```python
# scripts/validar_dag.py
from pathlib import Path
from framework.execution.parser import DAGParser
from framework.core.exceptions import ConfigurationError

# Instanciar o parser com os dois diretórios (Core :ro e App :rw)
parser = DAGParser(
    framework_dags_dir="framework/core/dags",
    app_dags_dir="application/dags",
)

try:
    # Validar um arquivo individual (sem registrar no catálogo global)
    dag = parser.parse_file(Path("application/dags/minha_pipeline.yaml"))

    print("[OK] YAML válido")
    print(f"[OK] DAG id: {dag.id}")
    print(f"[OK] immutable: {dag.immutable} (App DAG → deve ser False)")
    print(f"[OK] owner: {dag.owner}")
    print(f"[OK] Componentes declarados: {[c['id'] for c in dag.components]}")
    print(f"[OK] Estágios: {[s['id'] for s in dag.pipeline.get('stages', [])]}")
    print("[OK] Grafo acíclico (VAL-06)")

except ConfigurationError as e:
    print(f"[ERRO] {e.message}")
    print(f"       regra violada: {e.context.get('rule')}")
    print(f"       caminho: {e.context.get('path')}")
    raise
```

**Resultado esperado**:

```
[OK] YAML válido
[OK] DAG id: minha_pipeline
[OK] immutable: False (App DAG → deve ser False)
[OK] owner: dev_team
[OK] Componentes declarados: ['meu_fetcher', 'meu_ingestor']
[OK] Estágios: ['extrair_dados', 'ingerir_dados']
[OK] Grafo acíclico (VAL-06)
```

**Regras validadas automaticamente pelo parser** (Seção 5.1 da spec ID 1.4):

| Regra | O que valida | Exceção em caso de violação |
|---|---|---|
| VAL-01 | Core DAG tem `immutable: true` | `ConfigurationError(rule="VAL-01")` |
| VAL-02 | Core DAG tem `owner: "framework"` | `ConfigurationError(rule="VAL-02")` |
| VAL-03 | Core DAG tem prefixo `core_` | `ConfigurationError(rule="VAL-03")` |
| VAL-04 | Core DAG reside em `framework/core/dags/` | `ConfigurationError(rule="VAL-04")` |
| VAL-05 | Schema YAML (chaves obrigatórias) | `ConfigurationError(rule="VAL-05")` |
| VAL-06 | Grafo `depends_on` acíclico | `ConfigurationError(rule="VAL-06")` |
| VAL-07 | Tipos `management.*` em Core DAGs | `ConfigurationError(rule="VAL-07")` |
| VAL-08 | IDs Core/App disjuntos | `ConfigurationError(rule="VAL-08")` |
| VAL-09 | App DAG não pode ser imutável | `ConfigurationError(rule="VAL-09")` |

### 6.4. Executar a DAG (via `Orchestrator` — ID 2.1)

A execução é **programática**, via `Orchestrator`. O motor:

1. Resolve o grafo de dependências em **ordem topológica** (`TopologicalSorter`)
2. Detecta ciclos remanescentes (defesa em profundidade — regra `TOPO-02`)
3. Executa cada estágio chamando o componente registrado via sua porta (`FetcherPort`, `IngestPort`, etc.)
4. **Propaga o resultado** de um estágio como entrada do próximo (Pipeline/Filter)
5. Produz um `ExecutionResult` **imutável** (`frozen=True`) com proveniência completa

```python
# scripts/executar_dag.py
from pathlib import Path
from framework.execution.parser import DAGParser
from framework.execution.orchestrator import Orchestrator, ExecutionStatus
from application.components.senado_adapter import SenadoAdapter
from application.components.neo4j_adapter import Neo4jAdapter


def main() -> None:
    # 1. Parsear todas as DAGs (Core + App)
    parser = DAGParser(
        framework_dags_dir="framework/core/dags",
        app_dags_dir="application/dags",
    )
    dags = parser.parse_all()

    # 2. Instanciar o Orchestrator e registrar componentes
    orchestrator = Orchestrator()
    orchestrator.register_component(
        "meu_fetcher",
        SenadoAdapter({"normas": [("EMC", 33, 2001)]}),
    )
    orchestrator.register_component(
        "meu_ingestor",
        Neo4jAdapter({"uri": "bolt://localhost:7687"}),
    )

    # 3. Executar a DAG alvo
    result = orchestrator.execute_dag("minha_pipeline", dags)

    # 4. Inspecionar o snapshot imutável
    print(f"DAG: {result.dag_id}")
    print(f"Status: {result.status.value}")
    print(f"Início: {result.started_at.isoformat()}")
    print(f"Término: {result.finished_at.isoformat()}")
    print(f"Estágios executados: {list(result.stage_results)}")

    if result.has_errors:
        print(f"Erros: {result.errors}")

    # 5. Reagir ao status final
    if result.status is ExecutionStatus.SUCCESS:
        print("✅ Pipeline concluído com sucesso.")
    elif result.status is ExecutionStatus.PARTIAL_FAILURE:
        print("⚠️  Pipeline concluído com falhas parciais.")
    else:
        print("❌ Pipeline falhou. Consulte result.errors.")


if __name__ == "__main__":
    main()
```

**Execução**:

```bash
python scripts/executar_dag.py
```

**Saída esperada**:

```
DAG: minha_pipeline
Status: SUCCESS
Início: 2026-11-24T10:15:23.456789+00:00
Término: 2026-11-24T10:15:25.789012+00:00
Estágios executados: ['extrair_dados', 'dados_extraidos', 'ingerir_dados', 'resultado_ingestao']
✅ Pipeline concluído com sucesso.
```

### 6.5. Comportamento em falha (Princípio da Falha Explícita)

O `Orchestrator` **nunca degrada silenciosamente**. Toda violação produz um `ExecutionResult` com `status=FAILED` e `errors` preenchido:

| Cenário | Regra | Comportamento |
|---|---|---|
| DAG inexistente | `ORCH-01` | `ConfigurationError` com `context={"dag_id": ..., "rule": "ORCH-01"}` |
| DAG sem `pipeline.stages` nem `tasks` | `ORCH-02` | `ConfigurationError(rule="ORCH-02")` |
| Componente não registrado | `REG-03` | `ExecutionResult(status=FAILED, errors=[{...}])` |
| Ciclo em `depends_on` | `TOPO-02` | `ExecutionResult(status=FAILED)` com trilha do ciclo |
| Dependência inexistente | `TOPO-01` | `ExecutionResult(status=FAILED)` com lista de IDs desconhecidos |
| Input incompatível com porta | `EXEC-01..04` | `ExecutionResult(status=FAILED)` com tipo esperado vs. recebido |
| Componente que não herda de `*Port` | `REG-02` | Rejeição no `register()` com `ConfigurationError` |

**Nota**: o `ExecutionResult` é sempre produzido — mesmo em falha — preservando a proveniência (`started_at`, `finished_at`, `dag_id`) para a camada de Observabilidade.

---

## 7. Passo 5 — Configurar observabilidade

### 7.1. Entender os seis sinais

O framework coleta automaticamente seis sinais de observabilidade (ver `docs/observability.md`):

| Sinal | Família | Finalidade |
|---|---|---|
| Métricas | Clássica | "O que está acontecendo?" |
| Logs | Clássica | "O que aconteceu?" |
| Traces | Clássica | "Por onde passou?" |
| Explicabilidade | IA | "Por que decidiu isso?" |
| Responsabilização | IA | "Quem decidiu?" |
| Auditabilidade | IA | "Como reconstruir?" |

### 7.2. Configurar backends de observabilidade

Edite o arquivo de configuração:

```yaml
# framework/infrastructure/config/observability.yaml
observability:
  metrics:
    backend: prometheus
    config:
      endpoint: "http://localhost:9090"
      push_interval_seconds: 10
  logs:
    backend: console  # ou loki, file, etc.
    config:
      level: INFO
      format: json
  traces:
    backend: console  # ou tempo, jaeger, etc.
    config:
      sampling_rate: 1.0
  explicabilidade:
    backend: file
    config:
      path: "/var/log/mca/explicabilidade.jsonl"
  responsabilizacao:
    backend: postgres
    config:
      uri: postgresql://mca:mca_senha@localhost:5432/mca_audit
  auditabilidade:
    backend: postgres
    config:
      uri: postgresql://mca:mca_senha@localhost:5432/mca_audit
      immutable: true
```

### 7.3. Verificar coleta de sinais

Após executar uma DAG, verifique se os sinais foram coletados:

```python
from framework.management.dashboard import Dashboard

dashboard = Dashboard()

# Métricas
print(dashboard.get_metrics())
# Saída esperada: {"component.execution.count": 1, ...}

# Logs
print(dashboard.get_logs(limit=10))
# Saída esperada: [{"timestamp": "...", "level": "INFO", ...}, ...]

# Traces
print(dashboard.get_traces(limit=10))
# Saída esperada: [{"trace_id": "...", "spans": [...]}, ...]
```

### 7.4. Configurar alertas

```yaml
# framework/core/dags/alerting.yaml (já existe)
dag:
  id: core_alerting
  description: "Sistema de alertas do framework"
  schedule: "*/2 * * * *"
  owner: framework
  immutable: true

  tasks:
    - id: evaluate_alert_rules
      type: management.alerting.evaluate_rules
      config:
        rules:
          - name: high_error_rate
            condition: "error_rate > 0.05"
            severity: HIGH
            channels: [email, slack]
          - name: high_latency
            condition: "average_duration > 300"
            severity: MEDIUM
            channels: [slack]
```

---

## 8. Passo 6 — Testar

### 8.1. Estratégia de testes

O framework segue a pirâmide de testes (ver `tests/framework/README.md`):

```
┌─────────────┐
│   E2E (10%) │  ← tests/application/test_integration.py
├─────────────┤
│ Integração  │  ← tests/framework/test_execution.py (ID 2.1)
│   (20%)     │     + tests/framework/test_core_dags.py (ID 1.4)
├─────────────┤
│  Unitários  │  ← tests/framework/test_core_*.py (IDs 1.1, 1.2, 1.3)
│   (70%)     │
└─────────────┘
```

### 8.2. Suites de teste disponíveis

| Suite | Artefato testado | Spec ID | Categorias |
|---|---|---|---|
| `test_core_exceptions.py` | `framework/core/exceptions.py` | 1.1 | 6.1–6.4 |
| `test_core_entities.py` | `framework/core/entities.py` | 1.2 | 6.1–6.5 |
| `test_core_ports.py` | `framework/core/ports.py` | 1.3 | 6.1–6.6 |
| `test_core_dags.py` | `framework/execution/parser.py` + Core DAGs | 1.4 | 6.1–6.9 |
| `test_execution.py` | `framework/execution/orchestrator.py` | 2.1 | 6.1–6.7 |

### 8.3. Executar testes

```bash
# Executar todos os testes
pytest tests/ -v

# Executar apenas testes do framework
pytest tests/framework/ -v

# Executar apenas a suite do Orchestrator (ID 2.1)
pytest tests/framework/test_execution.py -v

# Executar apenas a suite do Parser (ID 1.4)
pytest tests/framework/test_core_dags.py -v

# Executar com cobertura
pytest tests/ -v --cov=framework --cov=application --cov-report=html

# Abrir relatório de cobertura
open htmlcov/index.html  # Linux/macOS
# ou: start htmlcov\index.html  # Windows
```

### 8.4. Meta de cobertura

**Meta**: Cobertura **≥ 95%** para módulos críticos do framework (`core/*`, `execution/orchestrator.py`, `execution/parser.py`).

```bash
# Verificar cobertura do Orchestrator (ID 2.1)
pytest tests/framework/test_execution.py \
    --cov=framework.execution.orchestrator \
    --cov-report=term-missing

# Verificar cobertura do Parser (ID 1.4)
pytest tests/framework/test_core_dags.py \
    --cov=framework.execution.parser \
    --cov-report=term-missing

# Saída esperada (exemplo):
# Name                                        Stmts   Miss  Cover   Missing
# ------------------------------------------------------------------------
# framework/execution/orchestrator.py           180      4    97%   142-145
# framework/execution/parser.py                 220      8    96%   201-208
```

### 8.5. Validação estática (obrigatória antes do merge)

A Seção 7 da spec ID 2.1 exige que **todos** os comandos abaixo passem sem erros:

```bash
# Type hints (PEP 484 / 585 / 604)
mypy framework/execution/orchestrator.py

# Formatação PEP 8
black --check framework/execution/orchestrator.py

# Linter rápido
ruff check framework/execution/orchestrator.py

# Linhas ≤ 88 colunas (compatível com black)
# (verificado automaticamente pelo black --check)
```

**Comando de validação completa** (copie e cole):

```bash
pytest tests/framework/test_execution.py -v \
    --cov=framework.execution.orchestrator \
    --cov-report=term-missing \
&& mypy framework/execution/orchestrator.py \
&& black --check framework/execution/orchestrator.py \
&& ruff check framework/execution/orchestrator.py
```

### 8.6. Categorias de teste da suite `test_execution.py` (ID 2.1)

A suite cobre integralmente a Seção 6 da spec:

| Seção | Categoria | O que valida |
|---|---|---|
| 6.1 | Instanciação e Contratos | `ExecutionResult` é `frozen=True`; `ComponentRegistry` rejeita duck-typing (`REG-02`) |
| 6.2 | Ordem Topológica | Estágios executam em ordem topológica, não declarada; despacho por tipo de porta |
| 6.3 | Ciclos e Dependências Inválidas | `TOPO-01` (dependência inexistente) e `TOPO-02` (ciclo) |
| 6.4 | Propagação de Dados | `output` alias no contexto; pipeline fetch→transform→ingest |
| 6.5 | Resolução de Componentes | `REG-01` (duplicata), `REG-02` (não-porta), `REG-03` (inexistente) |
| 6.6 | Falha Explícita | `ORCH-01`, `ORCH-02`, `EXEC-01..04` — nenhuma violação é silenciada |
| 6.7 | Integração com DAGDefinition | Core vs App DAG; teste `@pytest.mark.integration` com `DAGParser` real |

---

## 9. Passo 7 — Deploy

### 9.1. Ambiente de desenvolvimento (Docker Compose)

```bash
# Subir ambiente de desenvolvimento
docker-compose -f deployment/docker-compose.yml up -d

# Verificar status
docker-compose ps

# Ver logs
docker-compose logs -f framework-core
```

**Serviços iniciados**:

| Serviço | Porta | Finalidade |
|---|---|---|
| framework-core | 8080, 9090 | Núcleo do framework |
| application | - | Aplicação (App DAGs) |
| neo4j | 7474, 7687 | Grafo de conhecimento |
| postgres | 5432 | Banco de dados relacional |
| prometheus | 9091 | Métricas |
| grafana | 3000 | Dashboards |

### 9.2. Ambiente de produção (Kubernetes)

```bash
# Aplicar manifests Kubernetes
kubectl apply -f deployment/kubernetes/namespace.yaml
kubectl apply -f deployment/kubernetes/configmap-core.yaml
kubectl apply -f deployment/kubernetes/configmap-app.yaml
kubectl apply -f deployment/kubernetes/deployment.yaml
kubectl apply -f deployment/kubernetes/service.yaml

# Verificar status
kubectl get pods -n mca-framework
kubectl get services -n mca-framework
```

### 9.3. Helm (opcional)

```bash
# Instalar via Helm
helm install mca-framework deployment/helm/

# Verificar status
helm list

# Upgrade
helm upgrade mca-framework deployment/helm/
```

---

## 10. Passo 8 — Monitorar e operar

### 10.1. Acessar dashboards

```bash
# Grafana (dashboards)
open http://localhost:3000
# Usuário: admin
# Senha: admin (alterar em produção)

# Prometheus (métricas)
open http://localhost:9091

# Neo4j Browser
open http://localhost:7474
```

### 10.2. Consultar métricas

```python
from framework.management.dashboard import Dashboard

dashboard = Dashboard()

# Métricas de todos os componentes
for component in dashboard.components:
    metricas = component.metricas()
    print(f"{component.nome}:")
    print(f"  Execuções: {metricas['execution_count']}")
    print(f"  Taxa de sucesso: {metricas['success_rate']:.2%}")
    print(f"  Duração média: {metricas['average_duration']:.2f}s")
```

### 10.3. Consultar logs

```python
# Logs de todos os componentes
logs = dashboard.get_logs(level="ERROR", limit=10)
for log in logs:
    print(f"[{log['timestamp']}] {log['level']}: {log['message']}")
```

### 10.4. Consultar traces

```python
# Traces de execuções recentes
traces = dashboard.get_traces(limit=5)
for trace in traces:
    print(f"Trace ID: {trace['trace_id']}")
    for span in trace['spans']:
        print(f"  {span['component_id']}: {span['duration_ms']}ms")
```

### 10.5. Gerenciar alertas

```python
# Alertas ativos
alertas = dashboard.get_alertas()
for alerta in alertas:
    print(f"[{alerta['severity']}] {alerta['component']}: {alerta['message']}")

# Reconhecer alerta
dashboard.acknowledge_alert(alerta_id="alert-123")
```

### 10.6. Métricas de governança (Solo MCA)

Se você está operando o Solo MCA, monitore as métricas de governança (ver `SPEC_SOLO_MCA.md`, seção 6.9):

| Métrica | Objetivo | Como consultar |
|---|---|---|
| Taxa de Aprovação Humana | > 60% | `dashboard.get_metrica("taxa_aprovacao_humana")` |
| Taxa de Override Humano | < 10% | `dashboard.get_metrica("taxa_override_humano")` |
| Tempo Médio de Revisão | < 24h | `dashboard.get_metrica("tempo_medio_revisao")` |
| Precisão do LLM (Extração) | > 85% | `dashboard.get_metrica("precisao_llm_extracao")` |
| Precisão do LLM (Fundamento) | > 70% | `dashboard.get_metrica("precisao_llm_fundamento")` |

---

## 11. Checklist de conformidade

Antes de submeter seu componente ou composição, verifique:

### 11.1. Checklist de componente

- [ ] Implementa contrato correto (`FetcherPort`, `IngestPort`, etc.)
- [ ] **Herdar nominalmente** da ABC (duck-typing é rejeitado — Regra de Ouro)
- [ ] Retorna tipos corretos (`FetchResult`, `IngestResult`, etc.)
- [ ] Inclui proveniência nos metadados (source, timestamp, version)
- [ ] Trata erros sem interromper o lote (quando aplicável)
- [ ] Não implementa lógica de observabilidade (responsabilidade do framework)
- [ ] Tem testes unitários com cobertura ≥ 80%
- [ ] Tem manifesto YAML (`component.yaml`)
- [ ] Está registrado no framework via `ComponentRegistry`

### 11.2. Checklist de App DAG

- [ ] Tem `immutable: false` (ou ausente) — VAL-09
- [ ] Reside em `application/dags/`
- [ ] Não colide com IDs de Core DAGs — VAL-08
- [ ] Tem schema YAML válido — VAL-05
- [ ] Tem componentes registrados no `ComponentRegistry`
- [ ] Tem dependências válidas (grafo acíclico) — VAL-06
- [ ] Tem conectores configurados
- [ ] Tem notificações configuradas
- [ ] Foi testada via `Orchestrator.execute_dag()` (ID 2.1)

### 11.3. Checklist de observabilidade

- [ ] Backends de observabilidade configurados
- [ ] Métricas sendo coletadas
- [ ] Logs sendo registrados
- [ ] Traces sendo gerados
- [ ] Alertas configurados (se aplicável)
- [ ] Explicabilidade registrada (para componentes de IA)
- [ ] Responsabilização registrada (para decisões humanas)
- [ ] Auditabilidade habilitada (log imutável)

### 11.4. Checklist de deploy

- [ ] Ambiente de desenvolvimento funcional (Docker Compose)
- [ ] Ambiente de produção configurado (Kubernetes/Helm)
- [ ] Variáveis de ambiente configuradas
- [ ] Segredos injetados (não versionados)
- [ ] Health checks configurados
- [ ] Dashboards acessíveis
- [ ] Alertas funcionando

---

## 12. Troubleshooting

### 12.1. Problemas comuns

#### 12.1.1. "Componente não encontrado" (REG-03)

**Causa**: Estágio referencia `component_id` não registrado no `ComponentRegistry`.

**Solução**:

```python
from framework.execution.orchestrator import Orchestrator

orchestrator = Orchestrator()

# Verificar registro
print(orchestrator._registry.list())

# Registrar componente
orchestrator.register_component("meu_componente", MeuComponente())
```

#### 12.1.2. "Componente não herda de nenhuma ABC de porta" (REG-02)

**Causa**: Objeto registrado não herda nominalmente de `FetcherPort`, `IngestPort`, etc. (duck-typing).

**Solução**:

```python
# ❌ Errado (duck-typing — rejeitado):
class DuckFetcher:
    def buscar(self, config): ...

# ✅ Correto (herança nominal):
from framework.core.ports import FetcherPort

class MeuFetcher(FetcherPort):
    def buscar(self, config): ...
    def validar_config(self, config): ...
    def metadados(self): ...
```

#### 12.1.3. "App DAG com immutable=true" (VAL-09)

**Causa**: App DAG marcada como imutável (proibido).

**Solução**:

```yaml
# Corrigir no YAML da App DAG
dag:
  id: minha_pipeline
  immutable: false  # Obrigatório para App DAGs
```

#### 12.1.4. "Colisão de IDs entre Core e App DAGs" (VAL-08)

**Causa**: App DAG com mesmo ID de uma Core DAG.

**Solução**:

```yaml
# Alterar ID da App DAG
dag:
  id: minha_pipeline_v2  # ID único
```

#### 12.1.5. "Ciclo detectado em depends_on" (TOPO-02)

**Causa**: Dependências circulares entre estágios.

**Solução**:

```yaml
# Verificar dependências
pipeline:
  stages:
    - id: A
      depends_on: [C]  # Ciclo: A -> B -> C -> A
    - id: B
      depends_on: [A]
    - id: C
      depends_on: [B]

# Corrigir: remover dependência circular
pipeline:
  stages:
    - id: A
      depends_on: []
    - id: B
      depends_on: [A]
    - id: C
      depends_on: [B]
```

#### 12.1.6. "DAG não encontrada" (ORCH-01)

**Causa**: `execute_dag(dag_id, dags)` chamado com `dag_id` inexistente no dicionário retornado pelo `DAGParser`.

**Solução**:

```python
dags = parser.parse_all()
print(sorted(dags.keys()))  # Ver IDs disponíveis
result = orchestrator.execute_dag("id_correto", dags)
```

#### 12.1.7. "Métricas não sendo coletadas"

**Causa**: Backend de métricas não configurado ou indisponível.

**Solução**:

```yaml
# Verificar configuração
# framework/infrastructure/config/observability.yaml
observability:
  metrics:
    backend: prometheus
    config:
      endpoint: "http://localhost:9090"

# Verificar se Prometheus está rodando
docker-compose ps prometheus
```

#### 12.1.8. "LLM não retorna explicabilidade"

**Causa**: Componente de IA não emite explicabilidade.

**Solução**:

```python
class MeuLLMProcessor(TransformerPort):
    def transformar(self, dados: FetchResult) -> FetchResult:
        # ... lógica de transformação ...
        # Emitir explicabilidade
        contexto.registrar_explicacao(
            ExplicacaoIA(
                execution_id=contexto.execution_id,
                component_id="meu_llm",
                model="gpt-4",
                prompt_template="meu_prompt_v1",
                raw_output=resposta_bruta,
                confidence_score=0.87,
                # ... outros campos ...
            )
        )
        return resultado
```

### 12.2. Comandos úteis

```bash
# Ver logs do framework
docker-compose logs -f framework-core

# Ver logs da aplicação
docker-compose logs -f application

# Reiniciar serviços
docker-compose restart

# Parar todos os serviços
docker-compose down

# Limpar volumes (cuidado: apaga dados)
docker-compose down -v

# Executar todos os testes
pytest tests/ -v

# Validar todas as App DAGs via parser
python -c "from framework.execution.parser import DAGParser; DAGParser('framework/core/dags', 'application/dags').parse_all(); print('OK')"

# Listar componentes registrados
python -c "from framework.execution.orchestrator import ComponentRegistry; print(ComponentRegistry().list())"
```

### 12.3. Recursos adicionais

- **Documentação**: `docs/` (todos os documentos do framework)
- **Exemplos**: `docs/examples.md` (exemplos de código)
- **Contratos**: `docs/contracts.md` (especificação de contratos)
- **Observabilidade**: `docs/observability.md` (seis sinais)
- **Especificação Solo MCA**: `SPEC_SOLO_MCA.md` (domínio)
- **Issues**: [GitHub Issues](https://github.com/innovai-ltda/mca-framework/issues)
- **Discussões**: [GitHub Discussions](https://github.com/innovai-ltda/mca-framework/discussions)

---

## 13. Referências cruzadas

### 13.1. Documentos de fundamentação

| Documento | Finalidade | Quando consultar |
|---|---|---|
| `docs/arquitetura_molde_fundamentacao.md` (v1) | Fundamentação teórica | Para entender os padrões arquiteturais |
| `docs/arquitetura_molde_v2_orquestracao_gestao.md` (v2) | Gestão × Orquestração | Para entender a separação de responsabilidades |
| `docs/arquitetura_molde_v3_dags_separacao.md` (v3) | Core DAGs × App DAGs | Para entender a separação de artefatos |

### 13.2. Documentos técnicos

| Documento | Finalidade | Quando consultar |
|---|---|---|
| `docs/contracts.md` | Contratos e interfaces | Para implementar componentes |
| `docs/observability.md` | Observabilidade (6 sinais) | Para configurar métricas, logs, traces |
| `docs/examples.md` | Exemplos de código | Para ver implementações de referência |

### 13.3. Especificações de domínio

| Documento | Finalidade | Quando consultar |
|---|---|---|
| `SPEC_SOLO_MCA.md` | Especificação do Solo MCA | Para entender o domínio (LRMoo, Kelsen, COMEX) |
| `solo_mca_rodou_01102026_1215.txt` | Snapshot do repositório | Para entender a estrutura original |

### 13.4. Especificações técnicas (Milestones)

| Spec ID | Milestone | Artefato | Quando consultar |
|---|---|---|---|
| ID 1.1 | M1 — Core Framework | `framework/core/exceptions.py` | Hierarquia de exceções |
| ID 1.2 | M1 — Core Framework | `framework/core/entities.py` | Contratos de dados imutáveis |
| ID 1.3 | M1 — Core Framework | `framework/core/ports.py` | ABCs de porta (Arquitetura Hexagonal) |
| ID 1.4 | M1 — Core Framework | `framework/execution/parser.py` | Parser unificado de DAGs YAML |
| ID 2.1 | M2 — Execution & Management | `framework/execution/orchestrator.py` | Motor de orquestração |

### 13.5. Matriz de traçabilidade

| Passo deste guia | Documento de referência | Seção |
|---|---|---|
| Passo 1 (Esqueleto) | v3 (seção 4) | Estrutura de diretórios |
| Passo 2 (Componente) | `contracts.md` (seção 3) | Contratos de domínio |
| Passo 3 (Registro) | v1 (AX-02) + spec ID 2.1 (REG-01..03) | Todo componente é gerido + herança nominal |
| Passo 4 (App DAG) | v3 (seção 6) + spec ID 1.4 (VAL-01..09) + spec ID 2.1 | App DAGs + validação + execução |
| Passo 5 (Observabilidade) | `observability.md` (seção 2) | Seis sinais |
| Passo 6 (Testes) | specs ID 1.1–1.4 e 2.1 (Seção 6 de cada) | Estratégias de teste por ID |
| Passo 7 (Deploy) | v3 (seção 8) | Integração com infraestrutura |
| Passo 8 (Operação) | `observability.md` (seção 7) | Dashboards e alertas |

---

## Fechamento

Este guia forneceu um caminho passo-a-passo para implementar componentes, composições e testes no MCA Framework. A propriedade que unifica todos os passos é:

> **Todo componente implementa um contrato explícito. Toda composição é declarativa em YAML. Toda execução é observável pelos seis sinais. Toda decisão é rastreável e auditável.**

Toda decisão, checklist e exemplo deste guia deriva dessa propriedade.

---

*Guia prático de implementação. Os passos aqui descritos são a base para desenvolvedores implementarem componentes e composições. Novos passos devem ser adicionados conforme o framework evolui.*
```

---

## 📋 Resumo das Alterações

| Seção | O que mudou | Justificativa |
|---|---|---|
| **Cabeçalho** | Versão 1.0 → **1.1**; data → **2026-11-24** | Rastreabilidade da mudança |
| **Sumário** | "Passo 4 — Definir uma App DAG" → **"Passo 4 — Definir e executar uma App DAG"** | Reflete que execução agora é parte do passo |
| **4.4** | Adicionado item "**Herdar nominalmente** da ABC (Regra de Ouro)" | Alinhamento com `REG-02` do `ComponentRegistry` |
| **5.2** | Substituído `framework.core.registry.ComponentRegistry` por `framework.execution.orchestrator.ComponentRegistry` | API real da ID 2.1 |
| **5.3** | `list_components()` → `list()`; `get_metadata()` → `has()` + `get()` | Métodos reais do `ComponentRegistry` |
| **6.3** | Comandos CLI `python -m framework.execution.parser --validate` → **código Python** com `DAGParser.parse_file()` | Parser não tem CLI; API é programática |
| **6.4** | Comandos CLI `python -m framework.execution.orchestrator --dag` → **código Python** com `Orchestrator.execute_dag()` | Orchestrator não tem CLI; API é programática |
| **6.5 (nova)** | Nova subseção "**Comportamento em falha**" com tabela de regras `ORCH-01/02`, `REG-03`, `TOPO-01/02`, `EXEC-01..04` | Materializa o Princípio da Falha Explícita |
| **8.2 (nova)** | Nova subseção "**Suites de teste disponíveis**" com tabela mapeando suite → artefato → spec ID | Matriz de traçabilidade |
| **8.4** | Meta de cobertura 80% → **95%** (para módulos críticos); comandos específicos para `orchestrator.py` e `parser.py` | Alinhamento com spec ID 2.1 |
| **8.5 (nova)** | Nova subseção "**Validação estática**" com `mypy`, `black`, `ruff` | Exigência da Seção 7 da spec ID 2.1 |
| **8.6 (nova)** | Nova subseção "**Categorias de teste**" detalhando as 7 categorias (6.1–6.7) da spec ID 2.1 | Rastreabilidade spec → teste |
| **11.2** | Adicionados itens VAL-08, VAL-09, VAL-05, VAL-06 e referência ao `Orchestrator.execute_dag()` | Checklist agora reflete regras reais |
| **12.1.2 (nova)** | Novo troubleshooting para `REG-02` (duck-typing rejeitado) | Erro comum ao registrar componentes |
| **12.1.6 (nova)** | Novo troubleshooting para `ORCH-01` (DAG inexistente) | Erro comum na execução |
| **13.4 (nova)** | Nova subseção "**Especificações técnicas (Milestones)**" com IDs 1.1–1.4 e 2.1 | Matriz de traçabilidade |
| **13.5** | Atualizada para referenciar spec ID 2.1 nos Passos 3 e 4 | Rastreabilidade completa |