# Observabilidade, Explicabilidade e Responsabilização no MCA Framework

| Campo | Valor |
|---|---|
| **Documento** | `docs/observability.md` |
| **Versão** | 1.0 |
| **Data** | 2026-10-13 |
| **Status** | Referência técnica consolidada |
| **Dependência** | `docs/arquitetura_molde_fundamentacao.md` (v1); `docs/arquitetura_molde_v2_orquestracao_gestao.md` (v2); `docs/contracts.md`; `SPEC_SOLO_MCA.md` |
| **Escopo** | Definição formal dos mecanismos de observabilidade clássica (métricas, logs, traces) e de observabilidade específica para sistemas de IA (explicabilidade, responsabilização, auditabilidade) |
| **Fora de escopo** | Implementação de componentes específicos de IA; lógica de negócio COMEX |
| **Público** | Desenvolvedores de framework, desenvolvedores de componentes, arquitetos, operação, curadores (despachantes), compliance |

---

## Sumário

1. [Introdução e propósito](#1-introducao-e-proposito)
2. [Os seis sinais do MCA Framework](#2-os-seis-sinais-do-mca-framework)
3. [Observabilidade clássica](#3-observabilidade-classica)
4. [Observabilidade de IA](#4-observabilidade-de-ia)
5. [Mecanismos de implementação](#5-mecanismos-de-implementacao)
6. [Backends intercambiáveis](#6-backends-intercambiaveis)
7. [Dashboards e alertas](#7-dashboards-e-alertas)
8. [Critérios de conformidade](#8-criterios-de-conformidade)
9. [Trade-offs e limites](#9-trade-offs-e-limites)
10. [Referências bibliográficas](#10-referencias-bibliograficas)
11. [Matriz de traçabilidade](#11-matriz-de-tracabilidade)

---

## 1. Introdução e propósito

### 1.1. O problema

O MCA Framework acomoda componentes heterogêneos, incluindo componentes baseados em modelos de linguagem (LLMs) para extração de metadados, sumarização e sugestão de fundamentos legais. A observabilidade clássica — métricas, logs e traces — é necessária mas **insuficiente** para sistemas que incorporam IA:

1. **Caixa-preta comportamental**: um LLM pode produzir saída plausível mas incorreta sem sinalizar incerteza.
2. **Não-determinismo**: a mesma entrada pode produzir saídas diferentes em execuções diferentes.
3. **Cadeia de decisão opaca**: quando um LLM sugere um fundamento legal e um despachante aprova, a proveniência da decisão é distribuída entre máquina e humano.
4. **Degradação silenciosa**: modelos podem degradar ao longo do tempo sem que métricas tradicionais capturem o fenômeno.

### 1.2. A solução

Este documento estende a noção de observabilidade do framework para **seis sinais**, organizados em duas famílias:

| Família | Sinais | Finalidade |
|---|---|---|
| **Clássica** | Métricas, Logs, Traces | Operacional — "o sistema está saudável?" |
| **IA** | Explicabilidade, Responsabilização, Auditabilidade | Cognitiva — "por que o sistema decidiu isso?" |

A propriedade fundamental que unifica os seis sinais é:

> **Todo sinal é coletado pelo invólucro de gestão, na fronteira do componente, independentemente da ferramenta interna.**

Isso significa que um componente baseado em LLM e um componente baseado em regra determinística recebem o mesmo tratamento de observabilidade, com extensões específicas para IA quando aplicáveis.

### 1.3. Relação com os documentos anteriores

Este documento materializa os seguintes axiomas e decisões dos documentos v1 e v2:

- **AX-02** (v1): "Todo componente registrado é gerido."
- **AX-03** (v1): "A gestão é invariante sob substituição de implementação."
- **ADR-001** (v1): "Separar Gestão de Orquestração."
- **ADR-006** (v1): "Gestão por invólucro, não por herança."

E se alinha com as métricas de governança definidas em `SPEC_SOLO_MCA.md` (seção 6.9):

- Taxa de Aprovação Humana > 60%
- Taxa de Override Humano < 10%
- Precisão do LLM (Extração) > 85%
- Precisão do LLM (Fundamento Legal) > 70%

---

## 2. Os seis sinais do MCA Framework

### 2.1. Visão geral

```mermaid
flowchart TB
    subgraph CLASSICA["Familia Classica (Operacional)"]
        M["Metricas<br/>O que esta acontecendo?"]
        L["Logs<br/>O que aconteceu?"]
        T["Traces<br/>Por onde passou?"]
    end

    subgraph IA["Familia IA (Cognitiva)"]
        E["Explicabilidade<br/>Por que decidiu isso?"]
        R["Responsabilizacao<br/>Quem decidiu?"]
        A["Auditabilidade<br/>Como reconstruir?"]
    end

    CLASSICA --> DASH["Dashboards Unificados"]
    IA --> DASH

    subgraph INV["Invólucro de Gestão"]
        COLETOR["Coletor de Sinais"]
    end

    M --> COLETOR
    L --> COLETOR
    T --> COLETOR
    E --> COLETOR
    R --> COLETOR
    A --> COLETOR

    style CLASSICA fill:#E3F2FD,stroke:#1565C0,stroke-width:3px
    style IA fill:#F3E5F5,stroke:#7B1FA2,stroke-width:3px
    style INV fill:#E8F5E9,stroke:#2E7D32,stroke-width:3px
```

### 2.2. Definição formal

Seja um componente $c$ envolvido pelo invólucro de gestão $G(c)$. O invólucro coleta seis funções de sinal:

$$G(c) = (M, L, T, E, R, A)$$

onde:

- $M : c \times \mathbb{R}_{\geq 0} \rightarrow \mathcal{M}$ — métricas operacionais
- $L : c \times \Sigma^* \rightarrow \mathcal{L}$ — logs estruturados
- $T : c \times \text{Exec} \rightarrow \mathcal{T}$ — traces distribuídos
- $E : c \times \text{Dec} \rightarrow \mathcal{E}$ — explicações de decisões
- $R : c \times \text{Dec} \rightarrow \mathcal{R}$ — responsabilização (humano ou máquina)
- $A : c \times \text{Exec} \rightarrow \mathcal{A}$ — auditabilidade (reconstrução completa)

**Propriedade de completude**: para toda execução $e$ de um componente $c$, os seis sinais são coletados:

$$\forall e \in \text{Exec}(c): M(e) \land L(e) \land T(e) \land E(e) \land R(e) \land A(e)$$

### 2.3. Tabela comparativa

| Sinal | Família | Pergunta respondida | Granularidade | Persistência |
|---|---|---|---|---|
| **Métricas** | Clássica | "O que está acontecendo?" | Tempo real | Longa (anos) |
| **Logs** | Clássica | "O que aconteceu?" | Evento | Média (meses) |
| **Traces** | Clássica | "Por onde passou?" | Execução | Curta (dias) |
| **Explicabilidade** | IA | "Por que decidiu isso?" | Decisão | Longa (anos) |
| **Responsabilização** | IA | "Quem decidiu?" | Decisão | Longa (anos) |
| **Auditabilidade** | IA | "Como reconstruir?" | Execução | Longa (anos) |

---

## 3. Observabilidade clássica

### 3.1. Métricas

#### 3.1.1. Definição

Métricas são medidas numéricas agregadas do comportamento de um componente ao longo do tempo. Elas respondem à pergunta "o que está acontecendo?" em tempo real.

#### 3.1.2. Métricas obrigatórias do framework

Todo componente registrado no framework coleta automaticamente as seguintes métricas, sem exigir código do DEV:

| Métrica | Tipo | Unidade | Descrição |
|---|---|---|---|
| `component.execution.count` | Contador | - | Número total de execuções |
| `component.execution.success` | Contador | - | Número de execuções bem-sucedidas |
| `component.execution.failure` | Contador | - | Número de execuções com falha |
| `component.execution.duration` | Histograma | segundos | Duração de cada execução |
| `component.execution.success_rate` | Gauge | percentual | Taxa de sucesso (janela deslizante) |
| `component.execution.error_rate` | Gauge | percentual | Taxa de erro (janela deslizante) |
| `component.items.processed` | Contador | - | Número de itens processados |
| `component.items.failed` | Contador | - | Número de itens com falha |
| `component.health.status` | Gauge | código | Estado de saúde (0=saudável, 1=degradado, 2=indisponível) |

#### 3.1.3. Métricas específicas de componente

Componentes podem emitir métricas adicionais via contexto de execução, sem implementar a mecânica de coleta:

```python
def executar(self, contexto):
    resultado = processar(contexto)

    # Emissão de métrica de negócio (permitido)
    contexto.emitir_metrica("itens_classificados", len(resultado))
    contexto.emitir_metrica("tempo_medio_por_item", tempo / len(resultado))

    return resultado
```

#### 3.1.4. Métricas específicas de IA

Componentes baseados em LLM emitem métricas adicionais obrigatórias:

| Métrica | Tipo | Unidade | Descrição |
|---|---|---|---|
| `llm.tokens.input` | Contador | tokens | Tokens de entrada consumidos |
| `llm.tokens.output` | Contador | tokens | Tokens de saída gerados |
| `llm.tokens.total` | Contador | tokens | Total de tokens (entrada + saída) |
| `llm.cost.estimated` | Contador | USD | Custo estimado da chamada |
| `llm.latency` | Histograma | segundos | Latência da chamada ao provedor |
| `llm.model` | Gauge | código | Modelo utilizado (codificado) |
| `llm.temperature` | Gauge | - | Temperatura utilizada |
| `llm.retry.count` | Contador | - | Número de tentativas |
| `llm.rate_limit.hits` | Contador | - | Número de vezes que rate limit foi atingido |

### 3.2. Logs

#### 3.2.1. Definição

Logs são registros estruturados de eventos discretos ocorridos durante a execução de um componente. Eles respondem à pergunta "o que aconteceu?" com contexto rico.

#### 3.2.2. Formato padronizado

Todo log emitido pelo framework segue o formato JSON estruturado:

```json
{
  "timestamp": "2026-10-13T08:15:23.456Z",
  "level": "INFO",
  "component_id": "llm_processor",
  "execution_id": "exec-abc-123",
  "span_id": "span-def-456",
  "trace_id": "trace-ghi-789",
  "message": "Execução bem-sucedida",
  "context": {
    "duration_seconds": 2.34,
    "items_processed": 15,
    "model": "gpt-4",
    "tokens_used": 1234
  }
}
```

#### 3.2.3. Níveis de severidade

| Nível | Uso | Exemplo |
|---|---|---|
| `DEBUG` | Informação detalhada para desenvolvimento | "Payload enviado ao LLM: ..." |
| `INFO` | Eventos operacionais normais | "Execução bem-sucedida" |
| `WARNING` | Eventos anômalos mas recuperáveis | "Rate limit atingido, aguardando" |
| `ERROR` | Falhas recuperáveis | "Timeout na chamada ao LLM" |
| `CRITICAL` | Falhas irrecuperáveis | "Componente indisponível" |

#### 3.2.4. Logs específicos de IA

Componentes baseados em LLM emitem logs adicionais obrigatórios:

```json
{
  "timestamp": "2026-10-13T08:15:23.456Z",
  "level": "INFO",
  "component_id": "llm_processor",
  "execution_id": "exec-abc-123",
  "message": "Chamada LLM concluída",
  "context": {
    "model": "gpt-4",
    "temperature": 0.2,
    "max_tokens": 300,
    "prompt_hash": "sha256:a1b2c3d4...",
    "prompt_version": "1.2.0",
    "tokens_input": 850,
    "tokens_output": 120,
    "cost_usd": 0.0234,
    "latency_seconds": 2.34,
    "response_hash": "sha256:e5f6g7h8..."
  }
}
```

### 3.3. Traces

#### 3.3.1. Definição

Traces são registros de cadeias de invocação distribuídas, permitindo reconstruir o caminho de uma execução através de múltiplos componentes. Eles respondem à pergunta "por onde passou?".

#### 3.3.2. Estrutura de um trace

```mermaid
flowchart LR
    subgraph TRACE["Trace: exec-abc-123"]
        S1["Span 1<br/>fetch_dou<br/>1.2s"]
        S2["Span 2<br/>llm_processor<br/>2.3s"]
        S3["Span 3<br/>neo4j_ingestor<br/>0.8s"]
    end

    S1 --> S2 --> S3

    style TRACE fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
```

Cada span contém:

```json
{
  "trace_id": "trace-ghi-789",
  "span_id": "span-def-456",
  "parent_span_id": "span-xyz-012",
  "component_id": "llm_processor",
  "operation": "processar",
  "start_time": "2026-10-13T08:15:21.116Z",
  "end_time": "2026-10-13T08:15:23.456Z",
  "duration_ms": 2340,
  "status": "OK",
  "attributes": {
    "model": "gpt-4",
    "tokens_input": 850,
    "tokens_output": 120,
    "cost_usd": 0.0234
  },
  "events": [
    {
      "timestamp": "2026-10-13T08:15:21.500Z",
      "name": "prompt_sent",
      "attributes": {"prompt_hash": "sha256:a1b2c3d4..."}
    },
    {
      "timestamp": "2026-10-13T08:15:23.000Z",
      "name": "response_received",
      "attributes": {"response_hash": "sha256:e5f6g7h8..."}
    }
  ]
}
```

#### 3.3.3. Correlação entre sinais

Todo log e métrica emitida durante uma execução carrega os identificadores `trace_id` e `span_id`, permitindo correlação entre os três sinais clássicos:

```mermaid
flowchart TB
    TRACE["Trace ID<br/>trace-ghi-789"]
    SPAN["Span ID<br/>span-def-456"]

    TRACE --> LOG1["Log 1<br/>component=fetch_dou"]
    TRACE --> LOG2["Log 2<br/>component=llm_processor"]
    TRACE --> LOG3["Log 3<br/>component=neo4j_ingestor"]

    SPAN --> METRIC1["Métrica<br/>duration=2.3s"]
    SPAN --> METRIC2["Métrica<br/>tokens=1234"]

    style TRACE fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    style SPAN fill:#FFF3E0,stroke:#E65100,stroke-width:2px
```

---

## 4. Observabilidade de IA

### 4.1. Por que observabilidade de IA é diferente

Sistemas baseados em LLM apresentam características que exigem extensões específicas da observabilidade clássica:

| Característica | Implicação para observabilidade |
|---|---|
| **Não-determinismo** | Mesma entrada pode produzir saídas diferentes |
| **Caixa-preta** | Não é possível inspecionar o processo interno |
| **Custo variável** | Cada chamada tem custo financeiro mensurável |
| **Latência alta** | Chamadas podem levar segundos ou minutos |
| **Alucinação** | Saída pode ser plausível mas incorreta |
| **Degradação silenciosa** | Modelo pode piorar ao longo do tempo |
| **Dependência de prompt** | Mudanças no prompt alteram comportamento |
| **Decisão distribuída** | Humano e máquina compartilham responsabilidade |

### 4.2. Explicabilidade (Explainability)

#### 4.2.1. Definição

Explicabilidade é a capacidade de reconstruir **por que** um componente baseado em IA tomou uma decisão específica, incluindo:

- Qual prompt foi utilizado
- Qual modelo foi invocado
- Quais parâmetros foram configurados
- Qual foi a saída bruta do modelo
- Qual foi o processo de pós-processamento

#### 4.2.2. Mecanismo de implementação

Todo componente baseado em LLM deve emitir um **registro de explicação** para cada decisão:

```python
@dataclass
class ExplicacaoIA:
    """Registro de explicação de decisão de IA."""
    execution_id: str
    component_id: str
    timestamp: datetime
    decision_type: str  # "extracao_metadados", "sugestao_fundamento", "sumarizacao"
    input_hash: str  # Hash do input (para privacidade)
    input_snapshot: Optional[str]  # Snapshot do input (se permitido)
    prompt_template: str  # Identificador do template de prompt
    prompt_version: str  # Versão do prompt
    prompt_hash: str  # Hash do prompt completo
    model: str  # Modelo utilizado
    model_version: str  # Versão do modelo
    temperature: float
    max_tokens: int
    top_p: float
    raw_output: str  # Saída bruta do modelo
    output_hash: str  # Hash da saída
    post_processing: List[str]  # Lista de transformações pós-modelo
    confidence_score: Optional[float]  # Score de confiança (se disponível)
    alternatives: List[Dict]  # Alternativas consideradas (se disponível)
    latency_seconds: float
    tokens_input: int
    tokens_output: int
    cost_usd: float
```

#### 4.2.3. Exemplo aplicado ao MCA

No contexto do Solo MCA, quando o LLM sugere um fundamento legal (seção 6.4.3 do `SPEC_SOLO_MCA.md`), a explicação registrada é:

```json
{
  "execution_id": "exec-abc-123",
  "component_id": "llm_processor",
  "timestamp": "2026-10-13T08:15:23.456Z",
  "decision_type": "sugestao_fundamento",
  "input_hash": "sha256:a1b2c3d4...",
  "prompt_template": "suggest_legal_basis_v1",
  "prompt_version": "1.2.0",
  "prompt_hash": "sha256:e5f6g7h8...",
  "model": "gpt-4",
  "model_version": "gpt-4-0613",
  "temperature": 0.2,
  "max_tokens": 300,
  "top_p": 1.0,
  "raw_output": "[\"urn:lex:br:federal:lei:1999-08-10;9782\", \"urn:lex:br:merc:resolucao:2023-...;125\"]",
  "output_hash": "sha256:i9j0k1l2...",
  "post_processing": ["json_parse", "urn_validate", "rank_by_relevance"],
  "confidence_score": 0.87,
  "alternatives": [
    {"urn": "urn:lex:br:federal:lei:1999-08-10;9782", "score": 0.87},
    {"urn": "urn:lex:br:merc:resolucao:2023-...;125", "score": 0.72}
  ],
  "latency_seconds": 2.34,
  "tokens_input": 850,
  "tokens_output": 120,
  "cost_usd": 0.0234
}
```

#### 4.2.4. Consulta de explicação

O framework oferece uma API para consultar explicações:

```python
explicacao = framework.get_explicacao(execution_id="exec-abc-123")

print(f"Modelo: {explicacao.model}")
print(f"Prompt: {explicacao.prompt_template} v{explicacao.prompt_version}")
print(f"Confiança: {explicacao.confidence_score:.2%}")
print(f"Custo: US$ {explicacao.cost_usd:.4f}")
print(f"Alternativas: {len(explicacao.alternatives)}")
```

### 4.3. Responsabilização (Accountability)

#### 4.3.1. Definição

Responsabilização é a capacidade de identificar **quem** (humano ou máquina) tomou uma decisão específica e **com que autoridade**. No contexto do Solo MCA, isso é crítico porque:

- O LLM sugere fundamentos legais, mas não decide
- O Despachante aprova ou rejeita a sugestão
- A decisão final é humana, mas informada por máquina
- Em caso de override humano, a justificativa deve ser registrada

#### 4.3.2. Cadeia de responsabilização

```mermaid
flowchart LR
    subgraph CADEIA["Cadeia de Responsabilização"]
        LLM["LLM<br/>Sugere fundamento"]
        VAL["Validador<br/>Verifica K1-K3"]
        DESP["Despachante<br/>Aprova/Rejeita"]
        OVER["Override<br/>(se aplicável)"]
    end

    LLM -->|sugestão| VAL
    VAL -->|resultado| DESP
    DESP -->|decisão| OVER
    OVER -->|justificativa| FINAL["Decisão Final<br/>Registrada com proveniência"]

    style CADEIA fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
```

#### 4.3.3. Mecanismo de implementação

Todo registro de decisão carrega uma **cadeia de responsabilização**:

```python
@dataclass
class CadeiaResponsabilizacao:
    """Cadeia de responsabilização de uma decisão."""
    decision_id: str
    decision_type: str  # "aprovacao", "rejeicao", "override"
    timestamp: datetime

    # Agente máquina
    machine_agent: Optional[MachineAgent]  # LLM, validador, etc.
    machine_confidence: Optional[float]
    machine_explanation_id: str  # Referência à explicação

    # Agente humano (se aplicável)
    human_agent: Optional[HumanAgent]  # Despachante
    human_authority: Optional[str]  # Nível de autoridade
    human_justification: Optional[str]  # Justificativa (obrigatória para override)

    # Resultado
    outcome: str  # "aprovado", "rejeitado", "override_autorizado"
    constraints_satisfied: List[str]  # ["H1", "H2", "K1", "K2"]
    constraints_violated: List[str]  # ["I1"] (se aplicável)

@dataclass
class MachineAgent:
    """Agente máquina na cadeia de decisão."""
    agent_type: str  # "llm", "validator", "classifier"
    agent_id: str  # Identificador do componente
    agent_version: str  # Versão do componente
    model: Optional[str]  # Modelo (se LLM)
    model_version: Optional[str]

@dataclass
class HumanAgent:
    """Agente humano na cadeia de decisão."""
    agent_id: str  # ID do despachante
    agent_name: str
    agent_role: str  # "despachante", "curador", "revisor"
    authentication_method: str  # "oauth2", "certificate", etc.
    session_id: str  # Sessão de trabalho
```

#### 4.3.4. Exemplo aplicado ao MCA

No contexto do Solo MCA, quando um Despachante aprova um candidato com override humano (seção 6.5 do `SPEC_SOLO_MCA.md`):

```json
{
  "decision_id": "dec-xyz-789",
  "decision_type": "override",
  "timestamp": "2026-10-13T14:15:00Z",

  "machine_agent": {
    "agent_type": "validator",
    "agent_id": "kelsen_validator",
    "agent_version": "1.0.0",
    "model": null,
    "model_version": null
  },
  "machine_confidence": 1.0,
  "machine_explanation_id": "exp-abc-123",

  "human_agent": {
    "agent_id": "desp-001",
    "agent_name": "João Silva",
    "agent_role": "despachante",
    "authentication_method": "oauth2",
    "session_id": "sess-def-456"
  },
  "human_authority": "senior_despachante",
  "human_justification": "Apesar da violação de I1, a norma é relevante para o setor farmacêutico e há precedente no CARF.",

  "outcome": "override_autorizado",
  "constraints_satisfied": ["H1", "H2", "H3", "O1", "P1", "K1", "K2"],
  "constraints_violated": ["I1"]
}
```

#### 4.3.5. Princípio de responsabilização

O framework impõe o seguinte princípio:

> **Toda decisão que afeta o estado do Solo deve ter uma cadeia de responsabilização completa, identificando o agente máquina (se aplicável), o agente humano (se aplicável) e a justificativa (obrigatória para overrides).**

### 4.4. Auditabilidade (Auditability)

#### 4.4.1. Definição

Auditabilidade é a capacidade de **reconstruir completamente** uma execução passada, incluindo:

- Todos os inputs recebidos
- Todos os prompts enviados ao LLM
- Todas as saídas brutas do LLM
- Todas as transformações aplicadas
- Todas as decisões tomadas (máquina e humano)
- Todas as violações de invariantes
- Todas as justificativas de override

#### 4.4.2. Mecanismo de implementação

O framework mantém um **log de auditoria imutável** que registra todos os eventos relevantes:

```python
@dataclass
class EventoAuditoria:
    """Evento no log de auditoria."""
    event_id: str
    timestamp: datetime
    event_type: str  # "input_received", "llm_called", "decision_made", "override_authorized", etc.
    execution_id: str
    component_id: str
    actor: str  # "system", "llm", "despachante:001", etc.
    payload: Dict[str, Any]  # Dados do evento (hash de conteúdo sensível)
    payload_hash: str  # Hash do payload (para integridade)
    previous_event_id: Optional[str]  # Cadeia de eventos
    signature: str  # Assinatura digital (para não-repúdio)
```

#### 4.4.3. Cadeia de auditoria

```mermaid
flowchart TB
    E1["Evento 1<br/>input_received<br/>hash: a1b2c3"]
    E2["Evento 2<br/>llm_called<br/>hash: d4e5f6"]
    E3["Evento 3<br/>decision_made<br/>hash: g7h8i9"]
    E4["Evento 4<br/>override_authorized<br/>hash: j0k1l2"]
    E5["Evento 5<br/>integrated<br/>hash: m3n4o5"]

    E1 -->|previous_event_id| E2
    E2 -->|previous_event_id| E3
    E3 -->|previous_event_id| E4
    E4 -->|previous_event_id| E5

    style E1 fill:#E3F2FD,stroke:#1565C0
    style E2 fill:#FFF3E0,stroke:#E65100
    style E3 fill:#F3E5F5,stroke:#7B1FA2
    style E4 fill:#FFEBEE,stroke:#C62828
    style E5 fill:#E8F5E9,stroke:#2E7D32
```

#### 4.4.4. Reconstrução de execução

O framework oferece uma API para reconstruir uma execução passada:

```python
reconstrucao = framework.reconstruir_execucao(execution_id="exec-abc-123")

print(f"Execução: {reconstrucao.execution_id}")
print(f"Início: {reconstrucao.started_at}")
print(f"Fim: {reconstrucao.finished_at}")
print(f"Eventos: {len(reconstrucao.events)}")

for evento in reconstrucao.events:
    print(f"  [{evento.timestamp}] {evento.event_type} por {evento.actor}")
    print(f"    Payload: {evento.payload_hash}")
```

#### 4.4.5. Princípio de auditabilidade

O framework impõe o seguinte princípio:

> **Toda execução deve ser reconstruível a partir do log de auditoria, independentemente de quanto tempo tenha passado. O log de auditoria é imutável, assinado digitalmente e persistido em storage durável.**

### 4.5. Detecção de degradação (Drift Detection)

#### 4.5.1. Definição

Degradação (drift) é a mudança gradual no comportamento de um modelo de IA ao longo do tempo, que pode ser causada por:

- Mudança na distribuição dos dados de entrada
- Atualização do modelo pelo provedor
- Mudança no prompt sem validação adequada
- Acúmulo de erros não detectados

#### 4.5.2. Mecanismo de implementação

O framework coleta métricas de qualidade do LLM e compara com baselines históricos:

```python
@dataclass
class MetricaQualidadeLLM:
    """Métrica de qualidade de LLM."""
    component_id: str
    timestamp: datetime
    precision_extracao: float  # Precisão na extração de metadados
    precision_fundamento: float  # Precisão na sugestão de fundamento
    taxa_alucinacao: float  # Taxa de saídas plausíveis mas incorretas
    taxa_rejeicao_humana: float  # Taxa de rejeição pelo Despachante
    taxa_override: float  # Taxa de overrides humanos
    custo_medio_por_execucao: float  # Custo médio em USD
    latencia_media: float  # Latência média em segundos
```

#### 4.5.3. Alertas de degradação

O framework dispara alertas quando as métricas de qualidade degradam:

| Métrica | Limiar | Ação |
|---|---|---|
| `precision_extracao` | < 85% | Alerta WARNING |
| `precision_fundamento` | < 70% | Alerta WARNING |
| `taxa_alucinacao` | > 5% | Alerta HIGH |
| `taxa_rejeicao_humana` | > 40% | Alerta HIGH |
| `taxa_override` | > 10% | Alerta HIGH |
| `custo_medio_por_execucao` | > 2x baseline | Alerta MEDIUM |
| `latencia_media` | > 2x baseline | Alerta MEDIUM |

#### 4.5.4. Exemplo aplicado ao MCA

No contexto do Solo MCA, os limiares de qualidade são definidos em `SPEC_SOLO_MCA.md` (seção 6.9):

- Precisão do LLM (Extração) > 85%
- Precisão do LLM (Fundamento Legal) > 70%
- Taxa de Aprovação Humana > 60%
- Taxa de Override Humano < 10%

O framework monitora essas métricas continuamente e dispara alertas quando os limiares são violados.

### 4.6. Versionamento de prompts

#### 4.6.1. Definição

Versionamento de prompts é a prática de tratar prompts como código versionado, com:

- Identificador único por versão
- Hash do conteúdo
- Registro de mudanças
- Capacidade de rollback

#### 4.6.2. Mecanismo de implementação

```python
@dataclass
class PromptVersion:
    """Versão de um prompt."""
    prompt_id: str
    version: str
    content: str
    content_hash: str
    created_at: datetime
    created_by: str
    changelog: str
    is_active: bool

class PromptRegistry:
    """Registro de versões de prompts."""

    def get_active_version(self, prompt_id: str) -> PromptVersion:
        """Retorna a versão ativa de um prompt."""
        ...

    def get_version(self, prompt_id: str, version: str) -> PromptVersion:
        """Retorna uma versão específica de um prompt."""
        ...

    def register_version(self, prompt: PromptVersion) -> None:
        """Registra uma nova versão de um prompt."""
        ...

    def activate_version(self, prompt_id: str, version: str) -> None:
        """Ativa uma versão específica de um prompt."""
        ...
```

#### 4.6.3. Exemplo aplicado ao MCA

No contexto do Solo MCA, o prompt de sugestão de fundamento legal (seção 6.4.3 do `SPEC_SOLO_MCA.md`) é versionado:

```yaml
prompt_id: suggest_legal_basis
version: "1.2.0"
content: |
  Você é um especialista em comércio exterior brasileiro.
  Analise a ementa do ato candidato e sugira 1-3 URNs de normas
  de nível hierárquico inferior que possam fundamentar o ato.
  Não invente informações. Retorne apenas a lista de URNs.
content_hash: "sha256:e5f6g7h8..."
created_at: "2026-09-15T10:00:00Z"
created_by: "mca_team"
changelog: "Adicionada instrução para não inventar informações"
is_active: true
```

---

## 5. Mecanismos de implementação

### 5.1. Invólucro de gestão estendido

O invólucro de gestão (seção 5.4 do `docs/contracts.md`) é estendido para coletar os seis sinais:

```python
class InvolucroGestao:
    """
    Decorator que envolve um componente e coleta os seis sinais.
    """

    def __init__(
        self,
        interno: ContratoComponente,
        coletor_metricas: ColetorMetricas,
        logger: LoggerEstruturado,
        tracer: TracerDistribuido,
        explicabilidade: ExplicabilidadeCollector,
        responsabilizacao: ResponsabilizacaoCollector,
        auditabilidade: AuditabilidadeCollector
    ):
        self.interno = interno
        self.coletor_metricas = coletor_metricas
        self.logger = logger
        self.tracer = tracer
        self.explicabilidade = explicabilidade
        self.responsabilizacao = responsabilizacao
        self.auditabilidade = auditabilidade

    def executar(self, contexto: dict) -> dict:
        """Executa o componente com coleta dos seis sinais."""
        # 1. Abrir span de tracing
        span = self.tracer.iniciar_span(f"component.{self.interno.identificador()}")

        # 2. Registrar evento de auditoria (input)
        self.auditabilidade.registrar_evento(
            event_type="input_received",
            execution_id=contexto.execution_id,
            actor="system",
            payload={"input_hash": hash(contexto.payload)}
        )

        # 3. Executar componente interno
        inicio = time.time()
        try:
            resultado = self.interno.executar(contexto)
            duracao = time.time() - inicio

            # 4. Coletar métricas
            self.coletor_metricas.registrar("component.execution.duration", duracao)
            self.coletor_metricas.incrementar("component.execution.success")

            # 5. Registrar explicação (se componente de IA)
            if self._eh_componente_ia():
                explicacao = self.explicabilidade.coletar_explicacao(contexto, resultado)
                self.auditabilidade.registrar_evento(
                    event_type="llm_called",
                    execution_id=contexto.execution_id,
                    actor=f"llm:{explicacao.model}",
                    payload={"explicacao_id": explicacao.id}
                )

            # 6. Registrar evento de auditoria (output)
            self.auditabilidade.registrar_evento(
                event_type="execution_completed",
                execution_id=contexto.execution_id,
                actor=self.interno.identificador(),
                payload={"output_hash": hash(resultado)}
            )

            return resultado

        except Exception as e:
            duracao = time.time() - inicio
            self.coletor_metricas.registrar("component.execution.duration", duracao)
            self.coletor_metricas.incrementar("component.execution.failure")

            # Registrar evento de auditoria (erro)
            self.auditabilidade.registrar_evento(
                event_type="execution_failed",
                execution_id=contexto.execution_id,
                actor=self.interno.identificador(),
                payload={"error": str(e)}
            )

            raise

        finally:
            self.tracer.encerrar_span(span)
```

### 5.2. Contexto de execução estendido

O contexto de execução é estendido para permitir emissão de sinais de IA:

```python
@dataclass
class ContextoExecucao:
    """Contexto de execução estendido."""
    execution_id: str
    component_id: str
    payload: Any
    metadata: Dict[str, Any]

    # Métodos de emissão de sinais
    def emitir_metrica(self, nome: str, valor: float):
        """Emite métrica de negócio."""
        ...

    def emitir_log(self, nivel: str, mensagem: str, **contexto):
        """Emite log estruturado."""
        ...

    def registrar_explicacao(self, explicacao: ExplicacaoIA):
        """Registra explicação de decisão de IA."""
        ...

    def registrar_responsabilizacao(self, cadeia: CadeiaResponsabilizacao):
        """Registra cadeia de responsabilização."""
        ...

    def registrar_evento_auditoria(self, evento: EventoAuditoria):
        """Registra evento no log de auditoria."""
        ...
```

### 5.3. Fluxo de coleta dos seis sinais

```mermaid
sequenceDiagram
    autonumber
    participant ORQ as Orquestração
    participant INV as Invólucro de Gestão
    participant COMP as Componente
    participant LLM as LLM (se aplicável)
    participant MET as Métricas
    participant LOG as Logs
    participant TRC as Traces
    participant EXP as Explicabilidade
    participant RES as Responsabilização
    participant AUD as Auditabilidade

    ORQ->>INV: invocar(contexto)
    INV->>TRC: abrir span
    INV->>AUD: registrar evento (input)

    INV->>COMP: executar(contexto)

    alt Componente de IA
        COMP->>LLM: chamar modelo
        LLM-->>COMP: saída bruta
        COMP->>EXP: registrar explicação
        EXP-->>INV: explicação coletada
        INV->>AUD: registrar evento (llm_called)
    end

    COMP-->>INV: resultado

    INV->>MET: registrar métricas
    INV->>LOG: registrar log
    INV->>AUD: registrar evento (output)
    INV->>TRC: fechar span

    INV-->>ORQ: resultado
```

---

## 6. Backends intercambiáveis

### 6.1. Princípio

O framework é agnóstico quanto ao backend de observabilidade. Ele oferece adaptadores para diferentes backends, permitindo que a organização escolha a stack que melhor atende suas necessidades.

### 6.2. Backends suportados

| Backend | Métricas | Logs | Traces | Explicabilidade | Responsabilização | Auditabilidade |
|---|---|---|---|---|---|---|
| **Prometheus + Grafana + Loki + Tempo** | Sim | Sim | Sim | Sim | Sim | Sim |
| **OpenTelemetry Collector** | Sim | Sim | Sim | Sim | Sim | Sim |
| **DataDog** | Sim | Sim | Sim | Sim | Sim | Sim |
| **Arize AI** | Sim | Sim | Sim | Sim | Sim | Sim |
| **LangSmith** | Não | Não | Não | Sim | Sim | Sim |
| **Weights & Biases** | Sim | Não | Não | Sim | Não | Não |
| **InMemory (testes)** | Sim | Sim | Sim | Sim | Sim | Sim |
| **Arquivo JSON** | Não | Sim | Não | Sim | Sim | Sim |

### 6.3. Exemplo de configuração

```yaml
# framework/infrastructure/config/observability.yaml
observability:
  metrics:
    backend: prometheus
    config:
      endpoint: "http://prometheus:9090"
      push_interval_seconds: 10

  logs:
    backend: loki
    config:
      endpoint: "http://loki:3100"
      labels:
        app: mca-framework
        environment: production

  traces:
    backend: tempo
    config:
      endpoint: "http://tempo:3200"
      sampling_rate: 1.0

  explicabilidade:
    backend: arize
    config:
      api_key: ${ARIZE_API_KEY}
      space: mca-production

  responsabilizacao:
    backend: postgres
    config:
      uri: postgresql://mca:mca_senha@postgres:5432/mca_audit

  auditabilidade:
    backend: postgres
    config:
      uri: postgresql://mca:mca_senha@postgres:5432/mca_audit
      immutable: true
      signature_key: ${AUDIT_SIGNATURE_KEY}
```

---

## 7. Dashboards e alertas

### 7.1. Dashboards unificados

O framework oferece dashboards unificados que agregam os seis sinais:

#### 7.1.1. Dashboard operacional

Responde à pergunta "o sistema está saudável?":

- Taxa de sucesso por componente
- Duração média por componente
- Taxa de erro por componente
- Estado de saúde de todos os componentes
- Alertas ativos

#### 7.1.2. Dashboard de IA

Responde à pergunta "a IA está performando bem?":

- Precisão do LLM (extração) ao longo do tempo
- Precisão do LLM (fundamento) ao longo do tempo
- Taxa de alucinação ao longo do tempo
- Custo total por dia/semana/mês
- Latência média por modelo
- Tokens consumidos por dia/semana/mês

#### 7.1.3. Dashboard de governança

Responde à pergunta "a curadoria está funcionando?":

- Taxa de aprovação humana ao longo do tempo
- Taxa de override humano ao longo do tempo
- Tempo médio de revisão
- Fila pendente de candidatos
- Distribuição de decisões por despachante

### 7.2. Alertas

#### 7.2.1. Alertas operacionais

| Alerta | Condição | Severidade | Canal |
|---|---|---|---|
| Componente indisponível | `health.status == 2` por > 5min | CRITICAL | Email, Slack, PagerDuty |
| Taxa de erro alta | `error_rate > 5%` por > 10min | HIGH | Email, Slack |
| Latência alta | `duration > 10min` por > 5 execuções | MEDIUM | Slack |
| Fila de execuções | `queue_depth > 100` | MEDIUM | Slack |

#### 7.2.2. Alertas de IA

| Alerta | Condição | Severidade | Canal |
|---|---|---|---|
| Precisão de extração baixa | `precision_extracao < 85%` | HIGH | Email, Slack |
| Precisão de fundamento baixa | `precision_fundamento < 70%` | HIGH | Email, Slack |
| Taxa de alucinação alta | `taxa_alucinacao > 5%` | HIGH | Email, Slack |
| Custo elevado | `custo > 2x baseline` | MEDIUM | Slack |
| Latência elevada | `latencia > 2x baseline` | MEDIUM | Slack |

#### 7.2.3. Alertas de governança

| Alerta | Condição | Severidade | Canal |
|---|---|---|---|
| Taxa de aprovação baixa | `taxa_aprovacao < 60%` | HIGH | Email, Slack |
| Taxa de override alta | `taxa_override > 10%` | HIGH | Email, Slack |
| Tempo de revisão alto | `tempo_revisao > 24h` | MEDIUM | Slack |
| Fila pendente alta | `fila_pendente > 50` | MEDIUM | Slack |

---

## 8. Critérios de conformidade

### 8.1. Critérios gerais

Um sistema só pode ser dito **conforme à observabilidade do MCA Framework** se satisfizer todos os critérios abaixo.

| ID | Critério | Verificação |
|---|---|---|
| CO-01 | Todo componente registrado coleta os seis sinais | Teste de observabilidade |
| CO-02 | Métricas são coletadas automaticamente pelo invólucro | Teste de invólucro |
| CO-03 | Logs são estruturados em formato JSON | Teste de formato |
| CO-04 | Traces são correlacionados entre componentes | Teste de correlação |
| CO-05 | Componentes de IA emitem explicabilidade | Teste de explicabilidade |
| CO-06 | Decisões têm cadeia de responsabilização completa | Teste de responsabilização |
| CO-07 | Execuções são reconstruíveis a partir do log de auditoria | Teste de auditabilidade |
| CO-08 | Prompts são versionados e rastreáveis | Teste de versionamento |
| CO-09 | Métricas de qualidade de IA são monitoradas | Teste de drift detection |
| CO-10 | Alertas são disparados quando limiares são violados | Teste de alertas |

### 8.2. Critérios específicos de IA

| ID | Critério | Verificação |
|---|---|---|
| CI-01 | Toda chamada LLM registra prompt, modelo e parâmetros | Teste de explicabilidade |
| CI-02 | Toda sugestão de LLM tem score de confiança | Teste de explicabilidade |
| CI-03 | Toda decisão humana tem justificativa registrada | Teste de responsabilização |
| CI-04 | Overrides humanos têm justificativa obrigatória | Teste de responsabilização |
| CI-05 | Toda execução tem log de auditoria imutável | Teste de auditabilidade |
| CI-06 | Logs de auditoria são assinados digitalmente | Teste de integridade |
| CI-07 | Métricas de precisão são calculadas continuamente | Teste de drift detection |
| CI-08 | Alertas são disparados quando precisão degrada | Teste de alertas |

### 8.3. Critérios de privacidade e segurança

| ID | Critério | Verificação |
|---|---|---|
| CP-01 | Dados sensíveis são hasheados em logs | Teste de privacidade |
| CP-02 | Prompts não contêm dados pessoais identificáveis | Revisão de código |
| CP-03 | Logs de auditoria são criptografados em repouso | Teste de segurança |
| CP-04 | Acesso ao log de auditoria é controlado por RBAC | Teste de acesso |
| CP-05 | Chaves de assinatura são rotacionadas periodicamente | Teste de rotação |

---

## 9. Trade-offs e limites

### 9.1. Vantagens da abordagem

| Vantagem | Descrição |
|---|---|
| **Completude** | Seis sinais cobrem aspectos operacionais e cognitivos |
| **Consistência** | Mesma interface para todos os componentes |
| **Transparência** | Decisões de IA são explicáveis e rastreáveis |
| **Responsabilidade** | Cadeia de responsabilização clara |
| **Auditabilidade** | Reconstrução completa de execuções passadas |
| **Detecção de degradação** | Monitoramento contínuo de qualidade de IA |
| **Versionamento** | Prompts tratados como código |
| **Flexibilidade** | Backends intercambiáveis |

### 9.2. Custos da abordagem

| Custo | Descrição | Mitigação |
|---|---|---|
| **Overhead de coleta** | Coleta dos seis sinais adiciona latência | Coleta assíncrona quando possível |
| **Volume de dados** | Logs de auditoria podem crescer rapidamente | Retenção configurável, compressão |
| **Complexidade** | Seis sinais exigem mais infraestrutura | Backends unificados (OpenTelemetry) |
| **Custo de storage** | Persistência de longo prazo é cara | Tiered storage (hot/warm/cold) |
| **Curva de aprendizagem** | DEV precisa entender os seis sinais | Documentação clara, exemplos |

### 9.3. Limitações conhecidas

1. **Explicabilidade limitada**: LLMs são caixas-pretas; a explicabilidade registrada é externa (prompt, parâmetros, saída), não interna (atenção, embeddings).

2. **Responsabilização distribuída**: Em cadeias complexas (LLM + validador + humano), a responsabilização pode ser difusa.

3. **Auditabilidade vs. privacidade**: Logs de auditoria completos podem conter dados sensíveis; é necessário balancear completude e privacidade.

4. **Drift detection reativo**: A detecção de degradação é reativa (baseada em métricas passadas), não preditiva.

5. **Custo de observabilidade**: A observabilidade completa tem custo financeiro (storage, computação, licenças de backends).

---

## 10. Referências bibliográficas

### 10.1. Observabilidade clássica

**[R01]** BEYER, Betsy; JONES, Chris; PETOFF, Jennifer; MURPHY, N. R. *Site Reliability Engineering: How Google Runs Production Systems*. Sebastopol: O'Reilly, 2016. ISBN: 978-1-491-92276-2.
> Uso: monitoramento white-box; sinais observáveis; operação de sistemas distribuídos.

**[R02]** SIGELMAN, Benjamin H.; BARROSO, Luiz André; BURROWS, Mike; STEPHENSON, Pat; PLAKAL, Manoj; BEAVER, Daniel; JASPAN, Saul; SHANBHAG, Chimani. *Dapper, a Large-Scale Distributed Systems Tracing Infrastructure*. Mountain View: Google, 2010. Relatório técnico.
> Uso: tracing distribuído; rastreios; amostragem; correlação entre serviços.

**[R03]** OPENTELEMETRY. *OpenTelemetry Specification*. Disponível em: <https://opentelemetry.io/docs/specs/otel/>. Consulta em: 2026.
> Uso: modelagem de métricas, traces e logs como sinais correlacionáveis.

**[R04]** NEWRELIC. *The Three Pillars of Observability*. Disponível em: <https://newrelic.com/blog/best-practices/three-pillars-observability>. Consulta em: 2026.
> Uso: definição clássica de métricas, logs e traces como os três pilares da observabilidade.

### 10.2. Observabilidade de IA

**[R05]** CHAMORRO, Pablo; FARHADI, Ali; et al. *A Survey on Evaluation of Large Language Models*. ACM Transactions on Intelligent Systems and Technology, 2024. DOI: [10.1145/3641288](https://doi.org/10.1145/3641288).
> Uso: métricas de avaliação de LLMs; precisão, alucinação, viés.

**[R06]** ARIZE AI. *LLM Observability: A Comprehensive Guide*. Disponível em: <https://arize.com/blog-course/llm-observability/>. Consulta em: 2026.
> Uso: conceitos de observabilidade específicos para LLMs; traces, spans, explicações.

**[R07]** LANGCHAIN. *LangSmith: Debugging, Testing, and Monitoring for LLM Applications*. Disponível em: <https://docs.smith.langchain.com/>. Consulta em: 2026.
> Uso: plataforma de observabilidade para aplicações LLM; versionamento de prompts, traces, explicações.

**[R08]** WEIGHTS & BIASES. *W&B Prompts: LLM Engineering & Ops*. Disponível em: <https://docs.wandb.ai/guides/prompts>. Consulta em: 2026.
> Uso: versionamento de prompts; monitoramento de qualidade; detecção de drift.

### 10.3. Explicabilidade e responsabilização

**[R09]** SAMEK, Wojciech; WIEDEMANN, Felix; MULLER, Klaus-Robert. *Explaining Explanations: An Overview of Interpretability of Machine Learning*. arXiv:1806.00031, 2018.
> Uso: fundamentação teórica de explicabilidade em sistemas de IA.

**[R10]** EUROPEAN UNION. *Ethics Guidelines for Trustworthy AI*. High-Level Expert Group on Artificial Intelligence, 2019.
> Uso: princípios de explicabilidade, responsabilização e auditabilidade em IA.

**[R11]** EUROPEAN UNION. *EU AI Act: Regulation on Artificial Intelligence*. 2024.
> Uso: requisitos regulatórios de explicabilidade e responsabilização.

**[R12]** FLORIDI, Luciano; COWLS, Josh. *A Unified Framework of Five Principles for AI in Society*. Harvard Data Science Review, 2019. DOI: [10.1162/99608f92.8cd550d1](https://doi.org/10.1162/99608f92.8cd550d1).
> Uso: princípios de transparência, responsabilização e justiça em IA.

### 10.4. Auditabilidade e não-repúdio

**[R13]** SCHNEIDER, Fred B. *Implementing Fault-Tolerant Services Using the State Machine Approach: A Tutorial*. ACM Computing Surveys, v. 22, n. 4, p. 299-319, 1990.
> Uso: logs imutáveis; cadeia de eventos; reconstrução de estado.

**[R14]** LAMPORT, Leslie; SHOSTAK, Robert; PEASE, Marshall. *The Byzantine Generals Problem*. ACM Transactions on Programming Languages and Systems, v. 4, n. 3, p. 382-401, 1982.
> Uso: fundamentação teórica de consenso e não-repúdio em sistemas distribuídos.

**[R15]** NAKAMOTO, Satoshi. *Bitcoin: A Peer-to-Peer Electronic Cash System*. 2008.
> Uso: cadeia de blocos imutável; assinatura digital; não-repúdio.

### 10.5. Detecção de degradação

**[R16]** LU, Jie; LIU, An; KUKSINS, Denis; BROADBRIDGE, Kyle; NOOR, Ali; CHEN, Fang; CHEN, Shuo; ZHANG, Xue; WANG, Wei; CAO, Yang. *Learning under Concept Drift: A Review*. IEEE Transactions on Knowledge and Data Engineering, v. 31, n. 12, p. 2346-2363, 2019. DOI: [10.1109/TKDE.2018.2876857](https://doi.org/10.1109/TKDE.2018.2876857).
> Uso: fundamentação teórica de detecção de drift em modelos de ML.

**[R17]** MORENO-TORRES, Jesus; BARRIONUEVO, Javier; GARCIA, Salvador; HERRERA, Francisco. *A Formal Study on Fuzzy Concept Drift in Classification*. Information Sciences, v. 562, p. 1-19, 2021.
> Uso: detecção de degradação em modelos de classificação.

### 10.6. Versionamento de prompts

**[R18]** JIANG, Yuxuan; et al. *Prompt Engineering for Large Language Models: A Survey*. arXiv:2308.10848, 2023.
> Uso: fundamentação teórica de engenharia de prompts; versionamento, avaliação.

**[R19]** LIU, Pengfei; et al. *Pre-train, Prompt, and Predict: A Systematic Survey of Prompting Methods in Natural Language Processing*. ACM Computing Surveys, v. 55, n. 1, p. 1-35, 2022. DOI: [10.1145/3560815](https://doi.org/10.1145/3560815).
> Uso: métodos de prompting; versionamento e reutilização de prompts.

### 10.7. Especificações técnicas e fontes de projeto

**[E1]** `SPEC_SOLO_MCA.md`. Especificação do Solo MCA: métricas de governança (seção 6.9), processo de abastecimento com curadoria humana (seção 6), extração de metadados via LLM (seção 6.4), integração com Ro-DOU (seção 6.12).
> **Papel neste documento**: fonte primária de evidência sobre métricas de governança e uso de LLM no projeto.

**[E2]** `solo_mca_rodou_01102026_1215.txt`. Snapshot de árvore e conteúdo do repositório via gitingest: estrutura `src/`, contratos de refatoração em `LEGACY_MAP.md`, regras de `legacy/`.
> **Papel neste documento**: fonte primária de evidência sobre a organização real do código.

---

## 11. Matriz de traçabilidade

### 11.1. Sinal → mecanismo → documento de origem

| Sinal | Mecanismo no molde | Documento de origem | Seção |
|---|---|---|---|
| Métricas | Coletor automático no invólucro | v1 (AX-02), v2 (Gestão) | 3.1 |
| Logs | Logger estruturado no invólucro | v1 (AX-02), v2 (Gestão) | 3.2 |
| Traces | Tracer distribuído no invólucro | v1 (AX-02), v2 (Gestão) | 3.3 |
| Explicabilidade | ExplicabilidadeCollector no invólucro | v1 (AX-07), SPEC_SOLO_MCA (6.4) | 4.2 |
| Responsabilização | ResponsabilizacaoCollector no invólucro | v1 (AX-07), SPEC_SOLO_MCA (6.5) | 4.3 |
| Auditabilidade | AuditabilidadeCollector no invólucro | v1 (AX-07), SPEC_SOLO_MCA (6.6) | 4.4 |

### 11.2. Critério de conformidade → sinal → verificação

| Critério | Sinal | Verificação |
|---|---|---|
| CO-01 | Todos os seis | Teste de observabilidade |
| CO-02 | Métricas | Teste de invólucro |
| CO-03 | Logs | Teste de formato |
| CO-04 | Traces | Teste de correlação |
| CO-05 | Explicabilidade | Teste de explicabilidade |
| CO-06 | Responsabilização | Teste de responsabilização |
| CO-07 | Auditabilidade | Teste de auditabilidade |
| CO-08 | Explicabilidade | Teste de versionamento |
| CO-09 | Métricas de IA | Teste de drift detection |
| CO-10 | Alertas | Teste de alertas |

### 11.3. Referência → seção de utilização

| Referência | Seções |
|---|---|
| [R01], [R02], [R03], [R04] | 3, 10.1 |
| [R05], [R06], [R07], [R08] | 4, 10.2 |
| [R09], [R10], [R11], [R12] | 4.2, 4.3, 10.3 |
| [R13], [R14], [R15] | 4.4, 10.4 |
| [R16], [R17] | 4.5, 10.5 |
| [R18], [R19] | 4.6, 10.6 |
| [E1], [E2] | 1, 4, 10.7 |

---

## Fechamento

A observabilidade do MCA Framework não se limita aos três sinais clássicos (métricas, logs, traces). Ela estende-se para três sinais cognitivos (explicabilidade, responsabilização, auditabilidade) específicos de sistemas que incorporam IA.

A propriedade que unifica os seis sinais é:

> **Todo sinal é coletado pelo invólucro de gestão, na fronteira do componente, independentemente da ferramenta interna. A observabilidade é nativa, transversal e invariante sob substituição de implementação.**

Essa propriedade garante que:

1. **Sistemas baseados em IA são transparentes**: toda decisão é explicável, responsabilizada e auditável.
2. **A curadoria humana é preservada**: o Despachante é o gatekeeper supremo, com cadeia de responsabilização completa.
3. **A degradação é detectada**: métricas de qualidade são monitoradas continuamente, com alertas automáticos.
4. **A evolução é controlada**: prompts são versionados como código, com capacidade de rollback.
5. **A reconstrução é possível**: toda execução pode ser reconstruída a partir do log de auditoria imutável.

Toda decisão, critério de conformidade e exemplo deste documento deriva dessa propriedade.

---

*Documento de referência técnica. Os mecanismos aqui definidos são a base para implementação, teste e evolução da observabilidade do framework. Alterações exigem nova versão deste documento e revisão de todos os componentes afetados.*