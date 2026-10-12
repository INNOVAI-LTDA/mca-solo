# MCA Framework

**Arquitetura-molde genérica para composição de componentes de processamento normativo.**

## 🎯 Propósito

O **MCA Framework** é uma arquitetura de software que serve como **molde genérico** para a composição, orquestração e gestão de componentes heterogêneos de processamento de dados normativos.

Ele **não é** uma aplicação específica (como o Ro-DOU ou o Solo MCA), mas sim uma **infraestrutura reutilizável** que permite:

- **Acoplar componentes** de diferentes origens (Ro-DOU, APIs governamentais, LLMs, bancos de dados)
- **Garantir a execução** coordenada desses componentes via DAGs
- **Medir, monitorar e controlar** cada componente independentemente da ferramenta interna
- **Evoluir independentemente** dos componentes que acomoda

> **Analogia:** Se o Ro-DOU é um motor específico e o Solo MCA é um carro específico, o MCA Framework é a **plataforma automotiva** sobre a qual diferentes carros podem ser construídos.

---

## 🏛️ Fundamentação Teórica

A arquitetura é fundamentada na combinação de cinco padrões arquiteturais consolidados na literatura de engenharia de software:

| Padrão | Fonte | Contribuição |
|--------|-------|--------------|
| **Microkernel** | Buschmann et al. (1996) — POSA | Core mínimo + plugins intercambiáveis |
| **CBSE** | Szyperski & Clemens (2002) | Componentes como unidades de composição independentes |
| **Pipeline/Filter** | Garlan & Shaw (1994) | Execução coordenada com fluxo de dados |
| **Framework** | Fayad & Schmidt (1997) | Molde genérico com inversão de controle (IoC) |
| **Connectors** | Medvidovic & Taylor (2000) | Comunicação adaptável entre componentes |

O domínio de aplicação é fundamentado em:

- **Pirâmide de Kelsen** (1934) — Hierarquia normativa e derivação de validade
- **Modelo LRMoo** (IFLA, 2017) — Separação Work/Expression/Manifestation
- **Graph RAG Ontológico** — Recuperação determinística de normas via grafo de conhecimento

---

## 🧩 As Três Perspectivas

A arquitetura organiza o sistema em três perspectivas desacopladas:

```
┌─────────────────────────────────────────────────────────────────┐
│                      MCA FRAMEWORK                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  PERSPECTIVA 1: ARQUITETURA HEXAGONAL                     │  │
│  │  Ports (contratos) + Adapters (implementações)            │  │
│  │  → Permite trocar ferramentas sem alterar domínio         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          ↕                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  PERSPECTIVA 2: PIPELINE ORQUESTRADO                      │  │
│  │  DAGs (YAML) + Stages + Conectores                        │  │
│  │  → Define como componentes se comunicam                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          ↕                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  PERSPECTIVA 3: INFRAESTRUTURA & OBSERVABILIDADE          │  │
│  │  Deploy (Docker/K8s) + Métricas + Logs + Tracing          │  │
│  │  → Garante operação em produção                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔑 Gestão vs Orquestração

Uma distinção fundamental do framework:

| Conceito | Responsabilidade | Implementação | Escopo |
|----------|------------------|---------------|--------|
| **Gestão** | Medir, monitorar e controlar cada componente | **Framework** (nativo, transversal) | Todos os componentes |
| **Orquestração** | Definir como componentes se comunicam em um DAG | **DEV** (específico da composição) | Composição específica |

> **Regra de ouro:** A Gestão é **independente da ferramenta** (funciona igual para Airflow, Python, n8n). A Orquestração **depende das ferramentas** que cada componente usa.

---

## 📂 Estrutura de Diretórios

```
mca-framework/
│
├── framework/                    # 🏛️ CORE (IMUTÁVEL pelo DEV)
│   ├── core/
│   │   ├── dags/                 # Core DAGs (Gestão)
│   │   │   ├── metrics_collection.yaml
│   │   │   ├── health_check.yaml
│   │   │   ├── component_lifecycle.yaml
│   │   │   └── alerting.yaml
│   │   ├── ports.py              # Interfaces (Ports)
│   │   ├── entities.py           # Entidades de domínio
│   │   └── exceptions.py         # Exceções padronizadas
│   │
│   ├── management/               # Camada de Gestão (nativa)
│   │   ├── metrics/
│   │   ├── logging/
│   │   ├── tracing/
│   │   ├── alerting/
│   │   └── dashboard/
│   │
│   ├── execution/                # Engine de Execução
│   │   ├── parser.py             # Parser de DAGs YAML
│   │   ├── orchestrator.py
│   │   ├── connectors.py
│   │   └── lifecycle.py
│   │
│   └── infrastructure/           # Infraestrutura base
│       ├── Dockerfile.framework
│       ├── docker-compose.framework.yml
│       └── config/
│           ├── framework.env
│           └── logging.yaml
│
├── application/                  # 👨‍💻 APP (CONTROLADO pelo DEV)
│   ├── dags/                     # App DAGs (Orquestração)
│   │   ├── rodou_solo_pipeline.yaml
│   │   ├── senado_ncm_ingestion.yaml
│   │   └── comex_monitoring.yaml
│   │
│   ├── components/               # Componentes específicos
│   │   ├── rodou_adapter.py
│   │   ├── senado_adapter.py
│   │   ├── ncm_adapter.py
│   │   └── neo4j_adapter.py
│   │
│   └── config/                   # Configuração da aplicação
│       ├── app.env
│       ├── docker-compose.app.yml
│       └── secrets.yaml
│
├── deployment/                   # 🚀 DEPLOY
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── kubernetes/
│   └── helm/
│
├── tests/                        # 🧪 TESTES
│   ├── framework/
│   └── application/
│
├── docs/                         # 📚 DOCUMENTAÇÃO
│
├── config.yaml                   # Configuração raiz (merge framework + app)
├── .gitignore
└── requirements.txt
```

### Regras de Propriedade

| Diretório | Propriedade | Mutabilidade | Permissão de Escrita |
|-----------|-------------|--------------|----------------------|
| `framework/` | Framework | Imutável | Apenas mantenedores do framework |
| `application/` | DEV | Mutável | Qualquer DEV do projeto |
| `deployment/` | DevOps | Mutável (controlado) | Via pipelines de CI/CD |
| `tests/` | DEV | Mutável | Qualquer DEV do projeto |

---

## 🚀 Quick Start

### 1. Preparar o esqueleto

```powershell
# Windows PowerShell
.\scripts\create_dir.ps1 -RootPath "C:\Projetos\mca-framework"
```

```bash
# Linux/macOS
bash scripts/create_dir.sh --root /opt/mca-framework
```

### 2. Implementar um componente

```python
# application/components/meu_adapter.py
from framework.core.ports import FetcherPort, FetchResult

class MeuAdapter(FetcherPort):
    """Adapter que implementa FetcherPort."""
    
    def fetch(self, config: dict) -> FetchResult:
        # Sua lógica de extração aqui
        return FetchResult(items=[...], metadata={})
    
    def validate_config(self, config: dict) -> bool:
        return True
    
    def get_metadata(self) -> dict:
        return {"name": "meu_adapter", "version": "1.0.0"}
```

### 3. Definir uma App DAG

```yaml
# application/dags/minha_pipeline.yaml
dag:
  id: minha_pipeline
  description: "Pipeline específico do meu caso de uso"
  schedule: "0 8 * * MON-FRI"
  owner: dev_team

components:
  - id: meu_fetcher
    type: application.components.MeuAdapter
    config:
      endpoint: "https://api.exemplo.com"

pipeline:
  stages:
    - id: fetch
      component: meu_fetcher
      output: dados_extraidos

notifications:
  on_success:
    - type: log
      level: INFO
```

### 4. Executar

```bash
# Ambiente de desenvolvimento
docker-compose -f deployment/docker-compose.yml up -d

# Ver métricas (gestão nativa)
curl http://localhost:9090/metrics

# Ver dashboards
open http://localhost:3000
```

---

## 📊 Observabilidade Nativa

Todo componente registrado no framework automaticamente tem:

- **Métricas**: `execution_count`, `success_rate`, `average_duration`, `error_rate`
- **Logs estruturados**: Formato JSON com contexto rico
- **Tracing distribuído**: Rastreamento ponta-a-ponta
- **Alertas**: Configuração baseada em regras

```python
# Exemplo: métricas coletadas automaticamente
dashboard = framework.get_dashboard()

for component in dashboard.components:
    print(f"{component.name}:")
    print(f"  Execuções: {component.get_metricas().execution_count}")
    print(f"  Taxa de sucesso: {component.get_metricas().success_rate:.2%}")
    print(f"  Duração média: {component.get_metricas().average_duration:.2f}s")
```

---

## 🔌 Componentes Plugáveis

O framework pode acomodar componentes de diversas naturezas:

| Categoria | Exemplos | Porta |
|-----------|----------|-------|
| **Fetchers** | Ro-DOU, API Senado, Tabela NCM, Scrapers | `FetcherPort` |
| **Transformers** | LLM Processors, Match Engines, Normalizers | `TransformerPort` |
| **Validators** | Schema Validators, Invariants Validators | `ValidatorPort` |
| **Ingestors** | Neo4j, PostgreSQL, OpenSearch, S3 | `IngestPort` |
| **Notifiers** | Apprise, Email, Slack, Webhooks | `IngestPort` |

---

## 📚 Documentação

| Documento | Descrição |
|-----------|-----------|
| [`docs/arquitetura_molde_fundamentacao.md`](docs/arquitetura_molde_fundamentacao.md) | Fundamentação teórica completa com referências bibliográficas |
| [`docs/arquitetura_molde_v2_orquestracao_gestao.md`](docs/arquitetura_molde_v2_orquestracao_gestao.md) | Separação entre Gestão (Framework) e Orquestração (DEV) |
| [`docs/arquitetura_molde_v3_dags_separacao.md`](docs/arquitetura_molde_v3_dags_separacao.md) | Separação Core DAGs vs App DAGs |
| [`docs/implementation_guide.md`](docs/implementation_guide.md) | Guia passo-a-passo para implementar componentes |
| [`docs/contracts.md`](docs/contracts.md) | Contratos e interfaces do framework |
| [`docs/observability.md`](docs/observability.md) | Sistema de observabilidade nativa |

---

## 🎓 Conceitos-Chave

### Pirâmide Normativa (9 Níveis)

O framework suporta a representação de 9 níveis hierárquicos do comércio exterior brasileiro:

| Nível | Descrição | Fonte Típica |
|-------|-----------|--------------|
| L1 | Constituição Federal | API Senado |
| L2 | Tratados Internacionais | API Senado + DOU |
| L3 | Leis Ordinárias/Complementares | API Senado + DOU |
| L4 | Decretos | DOU |
| L5 | Resoluções CAMEX/GECEX (NCM) | Tabela NCM JSON |
| L6 | Instruções Normativas RFB | Ro-DOU (INLABS) |
| L7 | Normas de Órgãos Anuentes | Ro-DOU + Sites oficiais |
| L8 | Soluções de Consulta | Ro-DOU |
| L9 | Notas Explicativas (NESH) | Portal RFB |

### Ontologia LRMoo

O framework segue o modelo LRMoo (Library Reference Model Object-Oriented):

- **Work** → `NormativeElement` (obra abstrata)
- **Expression** → `ComponentTemporalVersion` (versão temporal)
- **Manifestation** → `LanguageVersion` (realização textual)
- **Event** → `LegislativeAction` (evento causal)

### Invariantes de Integridade

O framework valida automaticamente:

- **H1-H3**: Consistência de subníveis
- **O1**: Órgão emissor obrigatório
- **P1**: Parentesco obrigatório
- **K1-K3**: Derivação kelseniana, anti-simetria, aciclicidade
- **I1-I3**: Cobertura temporal, causalidade fechada, consistência de profundidade

---

## 🧪 Testes

```bash
# Executar todos os testes
pytest tests/ -v

# Apenas testes do framework
pytest tests/framework/ -v

# Apenas testes da aplicação
pytest tests/application/ -v

# Com cobertura
pytest tests/ -v --cov=framework --cov=application --cov-report=html
```

**Meta de cobertura:** ≥ 80% para componentes críticos (domain, adapters).

---

## 🤝 Contribuindo

1. **Framework (`framework/`)**: Mudanças via PR revisado pelos mantenedores
2. **Application (`application/`)**: DEVs podem criar/adaptar livremente
3. **Documentação (`docs/`)**: Sempre atualizar junto com o código
4. **Testes (`tests/`)**: Obrigatórios para qualquer mudança

Ver [`CONTRIBUTING.md`](CONTRIBUTING.md) para guidelines detalhados.

---

## ⚖️ Licença

**GPL v3** — Ver [`LICENSE`](LICENSE)

Este projeto é software livre: você pode redistribuí-lo e/ou modificá-lo sob os termos da GNU General Public License conforme publicada pela Free Software Foundation, versão 3 da Licença.

---

## 📝 Créditos e Reconhecimentos

- **Ro-DOU** — Ministério da Gestão e da Inovação em Serviços Públicos (MGI)
- **API do Senado Federal** — Dados abertos legislativos
- **Tabela NCM** — Planalto/GECEX
- **IFLA LRMoo** — Modelo de referência para bibliotecas
- **Hans Kelsen** — Teoria pura do direito

---

## 📧 Contato

- **Issues**: [GitHub Issues](https://github.com/innovai-ltda/mca-framework/issues)
- **Discussões**: [GitHub Discussions](https://github.com/innovai-ltda/mca-framework/discussions)
- **Email**: contato@innovai.com.br

---

**Projeto desenvolvido no âmbito do PIPE FAPESP Fase 1 — Atividade AP5 (Graph-RAG Normativo)**

---

> *"A arquitetura é a organização significativa dos elementos, suas relações entre si e ao ambiente, e os princípios que governam seu design e evolução."* — IEEE 1471
