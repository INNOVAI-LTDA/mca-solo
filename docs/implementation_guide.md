# Guia de Implementação do MCA Framework

| Campo | Valor |
|---|---|
| **Documento** | `docs/implementation_guide.md` |
| **Versão** | 1.0 |
| **Data** | 2026-10-13 |
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
6. [Passo 4 — Definir uma App DAG](#6-passo-4--definir-uma-app-dag)
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

**Tempo estimado**: 2-4 horas para um desenvolvedor experiente, do zero até o primeiro deploy funcional.

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
| API do Senado Federal | Extrair normas L1-L4 | Pública (sem autenticação) |
| INLABS (Ro-DOU) | Extrair publicações DOU L6-L8 | `INLABS_PORTAL_LOGIN`, `INLABS_PORTAL_PASSWORD` |
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
            errors=errors
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

O framework descobre componentes automaticamente a partir do diretório `application/components/`. Para registrar explicitamente:

```python
# application/bootstrap.py

from framework.core.registry import ComponentRegistry
from application.components.senado_adapter import SenadoAdapter

registry = ComponentRegistry()

registry.register(
    component_id="senado_adapter",
    component_class=SenadoAdapter,
    config={"normas": [("EMC", 33, 2001)]}
)
```

### 5.3. Verificar registro

```python
# Verificar se o componente foi registrado
print(registry.list_components())
# Saída esperada: ["senado_adapter"]

# Verificar metadados
print(registry.get_metadata("senado_adapter"))
# Saída esperada: {"name": "senado_adapter", "version": "1.0.0", ...}
```

---

## 6. Passo 4 — Definir uma App DAG

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
  immutable: false  # Obrigatório para App DAGs
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

### 6.3. Validar a DAG

```bash
# Validar sintaxe YAML
python -m framework.execution.parser --validate application/dags/minha_pipeline.yaml

# Validar schema
python -m framework.execution.parser --schema application/dags/minha_pipeline.yaml
```

**Resultado esperado**:

```
[OK] YAML válido
[OK] Schema válido
[OK] immutable=false (App DAG)
[OK] Componentes registrados: meu_fetcher, meu_ingestor
[OK] Dependências válidas: extrair_dados -> ingerir_dados
[OK] DAG válida
```

### 6.4. Executar a DAG

```bash
# Executar manualmente
python -m framework.execution.orchestrator --dag application/dags/minha_pipeline.yaml

# Executar com agendamento
python -m framework.execution.orchestrator --dag application/dags/minha_pipeline.yaml --schedule
```

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

O framework segue a pirâmide de testes (ver `tests/README.md`):

```
┌─────────────┐
│   E2E (10%) │  ← tests/integration/
├─────────────┤
│ Integração  │  ← tests/adapters/
│   (20%)     │
├─────────────┤
│  Unitários  │  ← tests/domain/
│   (70%)     │
└─────────────┘
```

### 8.2. Escrever testes unitários

```python
# tests/application/test_senado_adapter.py

import pytest
from unittest.mock import patch, MagicMock
from application.components.senado_adapter import SenadoAdapter


def test_senado_adapter_buscar():
    """Testa busca de normas."""
    # Mock da API
    with patch("requests.Session.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "DetalheDocumento": {
                "documentos": {
                    "documento": [{
                        "identificacao": {
                            "tipo": "LEI",
                            "numero": "10865",
                            "dataassinatura": "01/03/2004"
                        },
                        "ementa": "Teste de ementa"
                    }]
                }
            }
        }
        mock_get.return_value = mock_response

        # Executar
        adapter = SenadoAdapter({"normas": [("LEI", 10865, 2004)]})
        result = adapter.buscar({"normas": [("LEI", 10865, 2004)]})

        # Verificar
        assert result.items_count == 1
        assert result.items[0]["urn"] == "urn:lex:br:federal:lei:2004-03-01;10865"


def test_senado_adapter_validar_config():
    """Testa validacao de configuracao."""
    adapter = SenadoAdapter({})

    # Configuracao valida
    config_valida = {"normas": [("LEI", 10865, 2004)]}
    assert adapter.validar_config(config_valida) == True

    # Configuracao invalida
    config_invalida = {"normas": "nao_eh_lista"}
    assert adapter.validar_config(config_invalida) == False
```

### 8.3. Executar testes

```bash
# Executar todos os testes
pytest tests/ -v

# Executar apenas testes de um componente
pytest tests/application/test_senado_adapter.py -v

# Executar com cobertura
pytest tests/ -v --cov=application --cov-report=html

# Abrir relatório de cobertura
open htmlcov/index.html  # Linux/macOS
# ou: start htmlcov\index.html  # Windows
```

### 8.4. Meta de cobertura

**Meta**: Cobertura ≥ 80% para componentes críticos (domain, adapters).

```bash
# Verificar cobertura
pytest tests/ --cov=application --cov-report=term-missing

# Saída esperada:
# Name                                      Stmts   Miss  Cover   Missing
# -----------------------------------------------------------------------
# application/components/senado_adapter.py     45      4    91%   23-26
```

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
- [ ] Retorna tipos corretos (`FetchResult`, `IngestResult`, etc.)
- [ ] Inclui proveniência nos metadados (source, timestamp, version)
- [ ] Trata erros sem interromper o lote (quando aplicável)
- [ ] Não implementa lógica de observabilidade (responsabilidade do framework)
- [ ] Tem testes unitários com cobertura ≥ 80%
- [ ] Tem manifesto YAML (`component.yaml`)
- [ ] Está registrado no framework

### 11.2. Checklist de App DAG

- [ ] Tem `immutable: false` (ou ausente)
- [ ] Reside em `application/dags/`
- [ ] Não colide com IDs de Core DAGs
- [ ] Tem schema YAML válido
- [ ] Tem componentes registrados
- [ ] Tem dependências válidas (grafo acíclico)
- [ ] Tem conectores configurados
- [ ] Tem notificações configuradas
- [ ] Foi testada em ambiente de desenvolvimento

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

#### 12.1.1. "Componente não encontrado"

**Causa**: Componente não registrado no framework.

**Solução**:

```python
# Verificar registro
from framework.core.registry import ComponentRegistry
registry = ComponentRegistry()
print(registry.list_components())

# Registrar componente
registry.register(
    component_id="meu_componente",
    component_class=MeuComponente,
    config={...}
)
```

#### 12.1.2. "App DAG com immutable=true"

**Causa**: App DAG marcada como imutável (proibido).

**Solução**:

```yaml
# Corrigir no YAML da App DAG
dag:
  id: minha_pipeline
  immutable: false  # Obrigatório para App DAGs
```

#### 12.1.3. "Colisão de IDs entre Core e App DAGs"

**Causa**: App DAG com mesmo ID de uma Core DAG.

**Solução**:

```yaml
# Alterar ID da App DAG
dag:
  id: minha_pipeline_v2  # ID único
```

#### 12.1.4. "Ciclo detectado no grafo da DAG"

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

#### 12.1.5. "Métricas não sendo coletadas"

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

#### 12.1.6. "LLM não retorna explicabilidade"

**Causa**: Componente de IA não emite explicabilidade.

**Solução**:

```python
# Implementar emissão de explicabilidade
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

# Executar testes
pytest tests/ -v

# Validar DAGs
python -m framework.execution.parser --validate application/dags/*.yaml

# Listar componentes registrados
python -c "from framework.core.registry import ComponentRegistry; print(ComponentRegistry().list_components())"
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

### 13.4. Matriz de traçabilidade

| Passo deste guia | Documento de referência | Seção |
|---|---|---|
| Passo 1 (Esqueleto) | v3 (seção 4) | Estrutura de diretórios |
| Passo 2 (Componente) | contracts.md (seção 3) | Contratos de domínio |
| Passo 3 (Registro) | v1 (AX-02) | Todo componente é gerido |
| Passo 4 (App DAG) | v3 (seção 6) | App DAGs |
| Passo 5 (Observabilidade) | observability.md (seção 2) | Seis sinais |
| Passo 6 (Testes) | tests/README.md | Estratégia de testes |
| Passo 7 (Deploy) | v3 (seção 8) | Integração com infraestrutura |
| Passo 8 (Operação) | observability.md (seção 7) | Dashboards e alertas |

---

## Fechamento

Este guia forneceu um caminho passo-a-passo para implementar componentes, composições e testes no MCA Framework. A propriedade que unifica todos os passos é:

> **Todo componente implementa um contrato explícito. Toda composição é declarativa em YAML. Toda execução é observável pelos seis sinais. Toda decisão é rastreável e auditável.**

Toda decisão, checklist e exemplo deste guia deriva dessa propriedade.

---

*Guia prático de implementação. Os passos aqui descritos são a base para desenvolvedores implementarem componentes e composições. Novos passos devem ser adicionados conforme o framework evolui.*