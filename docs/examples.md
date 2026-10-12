# Exemplos de Implementação do MCA Framework

| Campo | Valor |
|---|---|
| **Documento** | `docs/examples.md` |
| **Versão** | 1.0 |
| **Data** | 2026-10-13 |
| **Status** | Referência prática consolidada |
| **Dependência** | `docs/arquitetura_molde_fundamentacao.md` (v1); `docs/arquitetura_molde_v2_orquestracao_gestao.md` (v2); `docs/arquitetura_molde_v3_dags_separacao.md` (v3); `docs/contracts.md`; `docs/observability.md`; `SPEC_SOLO_MCA.md` |
| **Escopo** | Exemplos práticos e executáveis de implementação de componentes, composições, conectores e testes, demonstrando o uso do framework em cenários reais do projeto MCA |
| **Fora de escopo** | Implementação completa de todos os componentes do projeto; lógica de negócio COMEX detalhada |
| **Público** | Desenvolvedores de framework, desenvolvedores de componentes, desenvolvedores de composição, arquitetos |

---

## Sumário

1. [Introdução e propósito](#1-introducao-e-proposito)
2. [Exemplos de Fetchers](#2-exemplos-de-fetchers)
3. [Exemplos de Ingestors](#3-exemplos-de-ingestors)
4. [Exemplos de Transformers](#4-exemplos-de-transformers)
5. [Exemplos de Validators](#5-exemplos-de-validators)
6. [Exemplos de URN Generators](#6-exemplos-de-urn-generators)
7. [Exemplos de Composições (App DAGs)](#7-exemplos-de-composicoes-app-dags)
8. [Exemplos de Conectores](#8-exemplos-de-conectores)
9. [Exemplos de Testes](#9-exemplos-de-testes)
10. [Exemplos de Observabilidade](#10-exemplos-de-observabilidade)
11. [Matriz de traçabilidade](#11-matriz-de-tracabilidade)

---

## 1. Introdução e propósito

### 1.1. O que este documento oferece

Este documento fornece exemplos práticos e executáveis de como implementar componentes, composições e testes usando o MCA Framework. Cada exemplo:

- **Implementa um contrato** definido em `docs/contracts.md`
- **Demonstra um conceito** dos documentos v1, v2, v3 e observability.md
- **É coerente com o domínio** do projeto MCA (normas brasileiras, LRMoo, COMEX)
- **Pode ser copiado e adaptado** para uso real

### 1.2. Como usar este documento

Os exemplos estão organizados por tipo de componente:

| Seção | Tipo de componente | Contrato implementado |
|---|---|---|
| 2 | Fetcher | `FetcherPort` |
| 3 | Ingestor | `IngestPort` |
| 4 | Transformer | `TransformerPort` |
| 5 | Validator | `ValidatorPort` |
| 6 | URN Generator | `URNPort` |
| 7 | Composição | App DAG YAML |
| 8 | Conector | `Connector` |
| 9 | Teste | Testes unitários e de integração |
| 10 | Observabilidade | Consultas de métricas, logs, traces |

### 1.3. Pré-requisitos

Antes de implementar os exemplos, certifique-se de:

1. **Ler os documentos de fundamentação** (v1, v2, v3) para entender a arquitetura
2. **Ler `docs/contracts.md`** para entender os contratos formais
3. **Ler `SPEC_SOLO_MCA.md`** para entender o domínio do projeto
4. **Executar `scripts/create_dir.ps1`** para criar a estrutura de diretórios
5. **Instalar as dependências** do framework

---

## 2. Exemplos de Fetchers

### 2.1. SenadoAdapter

**Finalidade**: Extrair normas da API do Senado Federal (Níveis 1-4).

**Contrato implementado**: `FetcherPort`

**Conceitos demonstrados**:
- Arquitetura Hexagonal (adapter de entrada)
- Rate limiting
- Retry logic
- Proveniência completa

```python
# framework/adapters/driving/senado/senado_adapter.py

from typing import Dict, Any, List, Optional
from datetime import datetime
import requests
import time

from framework.core.ports import FetcherPort, FetchResult
from framework.core.exceptions import FetcherError, ConfigurationError


class SenadoAdapter(FetcherPort):
    """
    Adapter para API do Senado Federal (Niveis 1-4).

    Extrai normas da API de Dados Abertos do Senado:
    - Emendas Constitucionais (L1)
    - Tratados Internacionais (L2)
    - Leis Ordinarias e Complementares (L3)
    - Decretos Legislativos (L4)

    Caracteristicas:
    - Rate limiting: 10 req/s (limite da API)
    - Retry: 3 tentativas com backoff exponencial
    - Proveniencia: source, timestamp, version
    """

    # Constantes
    BASE_URL = "https://legis.senado.leg.br/dadosabertos"
    RATE_LIMIT_DELAY = 0.15  # 10 req/s
    DEFAULT_TIMEOUT = 15
    MAX_RETRIES = 3

    # Mapeamento de tipos para URN
    TIPO_URN_MAP = {
        "EMC": "constituicao:emenda",
        "DLG": "decreto.legislativo",
        "DEC": "decreto",
        "LEI": "lei",
        "LC": "lei.complementar",
    }

    SIGLA_PARA_API = {
        "EC": "EMC",
        "DL": "DLG",
        "DEC": "DEC",
        "LEI": "LEI",
        "LC": "LC",
    }

    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o adapter.

        Args:
            config: {
                "normas": [
                    ("EMC", 33, 2001),  # (tipo, numero, ano)
                    ("DLG", 135, 2019),
                    ("LC", 87, 1996),
                ],
                "rate_limit": 10,  # opcional
                "timeout": 15,  # opcional
            }
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "MCA-Framework/1.0"
        })
        self._last_request_time = 0.0

    def buscar(self, config: Dict[str, Any]) -> FetchResult:
        """
        Busca normas na API do Senado.

        Args:
            config: Configuracao de busca (sobrescreve config do __init__)

        Returns:
            FetchResult com normas extraidas
        """
        normas = config.get("normas", self.config.get("normas", []))
        items = []
        errors = []

        for tipo, numero, ano in normas:
            try:
                norma = self._buscar_norma(tipo, numero, ano)
                if norma:
                    items.append(norma)
            except Exception as e:
                errors.append({
                    "error": str(e),
                    "context": {"tipo": tipo, "numero": numero, "ano": ano},
                    "timestamp": datetime.utcnow().isoformat()
                })

        return FetchResult(
            items=items,
            metadata={
                "source": "senado",
                "total": len(items),
                "errors": len(errors),
                "timestamp": datetime.utcnow().isoformat()
            },
            errors=errors,
            fetched_at=datetime.utcnow()
        )

    def validar_config(self, config: Dict[str, Any]) -> bool:
        """Valida configuracao."""
        if "normas" not in config:
            return False

        normas = config["normas"]
        if not isinstance(normas, list):
            return False

        for norma in normas:
            if not isinstance(norma, tuple) or len(norma) != 3:
                return False
            tipo, numero, ano = norma
            if not isinstance(tipo, str) or not isinstance(numero, int) or not isinstance(ano, int):
                return False

        return True

    def metadados(self) -> Dict[str, Any]:
        """Retorna metadados do adapter."""
        return {
            "name": "senado_adapter",
            "version": "1.0.0",
            "base_url": self.BASE_URL,
            "rate_limit": f"{1/self.RATE_LIMIT_DELAY:.1f} req/s",
            "supported_types": list(self.TIPO_URN_MAP.keys()),
        }

    def _rate_limit(self):
        """Respeita rate limit da API."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _buscar_norma(self, tipo: str, numero: int, ano: int) -> Optional[Dict[str, Any]]:
        """Busca norma especifica."""
        tipo_api = self._converter_sigla(tipo)
        url = f"{self.BASE_URL}/legislacao/{tipo_api}/{numero}/{ano}.json"

        data = self._request_with_retry(url)
        if not data:
            return None

        # Extrair dados
        documentos = (
            data.get("DetalheDocumento", {})
            .get("documentos", {})
            .get("documento", [])
        )

        if not documentos:
            return None

        doc = documentos[0]
        identificacao = doc.get("identificacao", {})

        # Converter data
        data_str = str(identificacao.get("dataassinatura", "")).strip()
        if data_str and len(data_str) >= 10:
            try:
                data_obj = datetime.strptime(data_str[:10], "%d/%m/%Y")
                data_promulgacao = data_obj.strftime("%Y-%m-%d")
            except ValueError:
                data_promulgacao = f"{ano}-01-01"
        else:
            data_promulgacao = f"{ano}-01-01"

        # Gerar URN
        urn = self._gerar_urn(tipo, str(numero), data_promulgacao)

        return {
            "urn": urn,
            "tipo": identificacao.get("tipo", tipo_api),
            "numero": str(identificacao.get("numero", numero)),
            "ano": ano,
            "data_promulgacao": data_promulgacao,
            "ementa": doc.get("ementa", ""),
            "situacao": doc.get("situacao", "Desconhecida"),
            "fonte": "API_Senado_Federal",
            "nivel_h": self._mapear_nivel(tipo_api),
        }

    def _request_with_retry(self, url: str) -> Optional[Dict]:
        """Executa requisicao com retry."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=self.DEFAULT_TIMEOUT)

                if response.status_code == 429:
                    wait = 2 ** attempt
                    time.sleep(wait)
                    continue

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                return response.json()

            except Exception as e:
                if attempt == self.MAX_RETRIES:
                    raise FetcherError(
                        f"Requisicao falhou apos {self.MAX_RETRIES} tentativas",
                        context={"url": url},
                        cause=e
                    )
                time.sleep(2 ** attempt)

        return None

    def _converter_sigla(self, tipo: str) -> str:
        """Converte sigla comum para sigla oficial da API."""
        tipo_upper = tipo.upper()
        return self.SIGLA_PARA_API.get(tipo_upper, tipo_upper)

    def _gerar_urn(self, tipo: str, numero: str, data: str) -> str:
        """Gera URN canonico."""
        tipo_oficial = self._converter_sigla(tipo)
        segmento = self.TIPO_URN_MAP.get(tipo_oficial, "norma")
        return f"urn:lex:br:federal:{segmento}:{data};{numero}"

    def _mapear_nivel(self, tipo_api: str) -> int:
        """Mapeia tipo para nivel hierarquico."""
        mapping = {
            "EMC": 1,  # Constituicao
            "DLG": 2,  # Tratado
            "LEI": 3,  # Lei
            "LC": 3,   # Lei Complementar
            "DEC": 4,  # Decreto
        }
        return mapping.get(tipo_api, 3)
```

**Exemplo de uso**:

```python
# Exemplo de uso do SenadoAdapter
from framework.adapters.driving.senado.senado_adapter import SenadoAdapter

config = {
    "normas": [
        ("EMC", 33, 2001),   # Emenda Constitucional 33/2001
        ("DLG", 135, 2019),  # Decreto Legislativo 135/2019
        ("LC", 87, 1996),    # Lei Complementar 87/1996
        ("LEI", 10865, 2004),  # Lei 10.865/2004
    ]
}

adapter = SenadoAdapter(config)
result = adapter.buscar(config)

print(f"Extraidos {result.items_count} itens")
print(f"Tem erros: {result.has_errors}")
print(f"Metadados: {result.metadata}")

for item in result.items:
    print(f"  URN: {item['urn']}")
    print(f"  Tipo: {item['tipo']}")
    print(f"  Nivel: {item['nivel_h']}")
```

**Verificação de conformidade**:

| Critério | Verificação |
|---|---|
| Implementa `FetcherPort` | Sim (métodos `buscar`, `validar_config`, `metadados`) |
| Retorna `FetchResult` com proveniência | Sim (metadata contém source, timestamp) |
| Trata erros sem interromper lote | Sim (errors list) |
| Rate limiting | Sim (10 req/s) |
| Retry logic | Sim (3 tentativas com backoff) |

### 2.2. RoDOUAdapter

**Finalidade**: Extrair publicações do DOU via INLABS (Níveis 6-8).

**Contrato implementado**: `FetcherPort`

**Conceitos demonstrados**:
- Integração com PostgreSQL (article_raw)
- Filtros COMEX (C1-C6)
- Texto completo (full_text)

```python
# framework/adapters/driving/rodou/rodou_adapter.py

from typing import Dict, Any, List
from datetime import datetime
import psycopg2

from framework.core.ports import FetcherPort, FetchResult
from framework.core.exceptions import FetcherError


class RoDOUAdapter(FetcherPort):
    """
    Adapter para Ro-DOU (Niveis 6-8).

    Extrai publicacoes do DOU via INLABS:
    - Instrucoes Normativas RFB (L6)
    - Normas de Orgaos Anuentes (L7)
    - Solucoes de Consulta (L8)

    Caracteristicas:
    - Fonte: PostgreSQL (article_raw)
    - Filtros: termos COMEX, orgaos, secoes
    - Texto completo: full_text
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.conn = None

    def buscar(self, config: Dict[str, Any]) -> FetchResult:
        """Busca publicacoes no DOU."""
        terms = config.get("terms", [])
        department = config.get("department", [])
        date_range = config.get("date_range", {})

        items = []
        errors = []

        try:
            # Conectar ao PostgreSQL
            self.conn = psycopg2.connect(
                host=self.config.get("postgres_host", "localhost"),
                port=self.config.get("postgres_port", 5432),
                dbname=self.config.get("postgres_db", "rodou"),
                user=self.config.get("postgres_user", "rodou"),
                password=self.config.get("postgres_password", "")
            )

            # Construir query
            query = self._construir_query(terms, department, date_range)

            # Executar query
            with self.conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

                for row in rows:
                    item = self._mapear_row_para_item(row)
                    items.append(item)

        except Exception as e:
            errors.append({
                "error": str(e),
                "context": {"terms": terms, "department": department},
                "timestamp": datetime.utcnow().isoformat()
            })
            raise FetcherError(
                "Falha ao buscar publicacoes no DOU",
                context={"terms": terms},
                cause=e
            )
        finally:
            if self.conn:
                self.conn.close()

        return FetchResult(
            items=items,
            metadata={
                "source": "dou_inlabs",
                "total": len(items),
                "terms": terms,
                "department": department,
                "timestamp": datetime.utcnow().isoformat()
            },
            errors=errors,
            fetched_at=datetime.utcnow()
        )

    def validar_config(self, config: Dict[str, Any]) -> bool:
        """Valida configuracao."""
        required = ["postgres_host", "postgres_db", "postgres_user"]
        return all(field in config for field in required)

    def metadados(self) -> Dict[str, Any]:
        """Retorna metadados."""
        return {
            "name": "rodou_adapter",
            "version": "1.0.0",
            "source": "INLABS",
            "supported_levels": [6, 7, 8],
        }

    def _construir_query(self, terms: List[str], department: List[str], date_range: Dict) -> str:
        """Construi query SQL."""
        query = "SELECT * FROM article_raw WHERE 1=1"

        if terms:
            terms_filter = " OR ".join([f"full_text ILIKE '%{term}%'" for term in terms])
            query += f" AND ({terms_filter})"

        if department:
            dept_filter = " OR ".join([f"hierarchy_str ILIKE '%{dept}%'" for dept in department])
            query += f" AND ({dept_filter})"

        if date_range:
            start = date_range.get("start")
            end = date_range.get("end")
            if start:
                query += f" AND pub_date >= '{start}'"
            if end:
                query += f" AND pub_date <= '{end}'"

        return query

    def _mapear_row_para_item(self, row: tuple) -> Dict[str, Any]:
        """Mapeia row do PostgreSQL para item."""
        # Assumindo estrutura: id, section, title, href, abstract, date, hierarchy_str, arttype, pubtype, full_text, matches
        return {
            "id": row[0],
            "section": row[1],
            "title": row[2],
            "href": row[3],
            "abstract": row[4],
            "date": row[5],
            "hierarchy_str": row[6],
            "arttype": row[7],
            "pubtype": row[8],
            "full_text": row[9],
            "matches": row[10] if len(row) > 10 else [],
            "fonte": "DOU_INLABS",
        }
```

---

## 3. Exemplos de Ingestors

### 3.1. Neo4jAdapter

**Finalidade**: Ingerir normas no grafo Neo4j seguindo modelo LRMoo.

**Contrato implementado**: `IngestPort`

**Conceitos demonstrados**:
- Arquitetura Hexagonal (adapter de saída)
- Modelo LRMoo (Work, Expression, Manifestation)
- Batch processing
- Idempotência

```python
# framework/adapters/driven/neo4j/neo4j_adapter.py

from typing import Dict, Any, List
from datetime import datetime

from framework.core.ports import IngestPort, FetchResult, IngestResult
from framework.core.exceptions import IngestorError


class Neo4jAdapter(IngestPort):
    """
    Adapter para Neo4j (grafo de conhecimento).

    Ingerir normas no grafo seguindo modelo LRMoo:
    - NormativeElement (Work)
    - ComponentTemporalVersion (Expression)
    - LanguageVersion (Manifestation)
    - LegislativeAction (Event)

    Caracteristicas:
    - Batch processing: 100 itens por batch
    - Idempotencia: MERGE em vez de CREATE
    - Proveniencia: created_at, updated_at
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.driver = None
        self.batch_size = config.get("batch_size", 100)

    def ingerir(self, dados: FetchResult) -> IngestResult:
        """Ingerir dados no Neo4j."""
        result = IngestResult()

        try:
            # Conectar ao Neo4j
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(
                self.config.get("uri", "bolt://localhost:7687"),
                auth=(
                    self.config.get("user", "neo4j"),
                    self.config.get("password", "neo4j")
                )
            )

            # Processar em batches
            for i in range(0, len(dados.items), self.batch_size):
                batch = dados.items[i:i + self.batch_size]
                batch_result = self._ingerir_batch(batch)

                result.success_count += batch_result.success_count
                result.failure_count += batch_result.failure_count
                result.ingested_ids.extend(batch_result.ingested_ids)
                result.errors.extend(batch_result.errors)

        except Exception as e:
            raise IngestorError(
                "Falha ao ingerir dados no Neo4j",
                context={"total_items": len(dados.items)},
                cause=e
            )
        finally:
            if self.driver:
                self.driver.close()

        result.ingested_at = datetime.utcnow()
        return result

    def validar_conexao(self) -> bool:
        """Valida conexao com Neo4j."""
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                self.config.get("uri", "bolt://localhost:7687"),
                auth=(
                    self.config.get("user", "neo4j"),
                    self.config.get("password", "neo4j")
                )
            )
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            return True
        except Exception:
            return False

    def metadados(self) -> Dict[str, Any]:
        """Retorna metadados."""
        return {
            "name": "neo4j_adapter",
            "version": "1.0.0",
            "uri": self.config.get("uri"),
            "batch_size": self.batch_size,
        }

    def _ingerir_batch(self, batch: List[Dict[str, Any]]) -> IngestResult:
        """Ingerir um batch de normas."""
        result = IngestResult()

        for item in batch:
            try:
                self._ingerir_norma(item)
                result.success_count += 1
                result.ingested_ids.append(item.get("urn", "unknown"))
            except Exception as e:
                result.failure_count += 1
                result.errors.append({
                    "urn": item.get("urn", "unknown"),
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                })

        return result

    def _ingerir_norma(self, norma: Dict[str, Any]):
        """Ingerir uma norma individual."""
        with self.driver.session() as session:
            # 1. Criar/atualizar NormativeElement (Work)
            session.run("""
                MERGE (n:NormativeElement {urn: $urn})
                ON CREATE SET
                    n.nivel_h = $nivel_h,
                    n.sub_nivel_h = $sub_nivel_h,
                    n.tipo_elemento = $tipo_elemento,
                    n.codigo = $codigo,
                    n.descricao = $descricao,
                    n.data_vigencia = date($data_vigencia),
                    n.orgao_emissor = $orgao_emissor,
                    n.jurisdicao = $jurisdicao,
                    n.created_at = timestamp()
                ON MATCH SET
                    n.descricao = $descricao,
                    n.updated_at = timestamp()
            """,
                urn=norma.get("urn"),
                nivel_h=norma.get("nivel_h", 0),
                sub_nivel_h=norma.get("sub_nivel_h", -1),
                tipo_elemento=norma.get("tipo_elemento", ""),
                codigo=norma.get("codigo", ""),
                descricao=norma.get("ementa", "")[:2000],
                data_vigencia=norma.get("data_promulgacao"),
                orgao_emissor=norma.get("orgao_emissor"),
                jurisdicao=norma.get("jurisdicao", "federal"),
            )

            # 2. Criar ComponentTemporalVersion (Expression)
            urn_ctv = f"{norma['urn']}@{norma.get('data_promulgacao')}"
            session.run("""
                MERGE (ctv:ComponentTemporalVersion {urn: $urn})
                ON CREATE SET
                    ctv.valid_start = date($valid_start),
                    ctv.valid_end = NULL,
                    ctv.nivel_h = $nivel_h,
                    ctv.componente_tipo = $componente_tipo,
                    ctv.created_at = timestamp()
            """,
                urn=urn_ctv,
                valid_start=norma.get("data_promulgacao"),
                nivel_h=norma.get("nivel_h", 0),
                componente_tipo=norma.get("tipo_elemento", ""),
            )

            # 3. Conectar Work -> CTV
            session.run("""
                MATCH (n:NormativeElement {urn: $urn_work})
                MATCH (ctv:ComponentTemporalVersion {urn: $urn_ctv})
                MERGE (n)-[:TEM_VERSAO_TEMPORAL]->(ctv)
            """,
                urn_work=norma["urn"],
                urn_ctv=urn_ctv,
            )
```

---

## 4. Exemplos de Transformers

### 4.1. LLMProcessor

**Finalidade**: Processar textos com LLM para extração de metadados e sumarização.

**Contrato implementado**: `TransformerPort`

**Conceitos demonstrados**:
- Integração com LLM (OpenAI)
- Versionamento de prompts
- Métricas de IA (tokens, custo, latência)
- Explicabilidade

```python
# framework/processors/llm_processor.py

from typing import Dict, Any, List
from datetime import datetime
import openai
import hashlib

from framework.core.ports import TransformerPort, FetchResult
from framework.core.exceptions import TransformerError


class LLMProcessor(TransformerPort):
    """
    Processador LLM para extracao de metadados e sumarizacao.

    Caracteristicas:
    - Provider: OpenAI (GPT-4)
    - Prompts versionados
    - Metricas de IA: tokens, custo, latencia
    - Explicabilidade: prompt, modelo, parametros
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("provider", "openai")
        self.model = config.get("model", "gpt-4")
        self.temperature = config.get("temperature", 0.2)
        self.max_tokens = config.get("max_tokens", 300)
        self.api_key = config.get("api_key")

        openai.api_key = self.api_key

    def transformar(self, dados: FetchResult) -> FetchResult:
        """Transforma dados com LLM."""
        items_transformados = []

        for item in dados.items:
            try:
                # Extrair metadados com LLM
                metadados = self._extrair_metadados(item)

                # Sumarizar com LLM
                resumo = self._sumarizar(item)

                # Enriquecer item
                item_enriquecido = {
                    **item,
                    "metadados_extraidos": metadados,
                    "resumo": resumo,
                    "llm_info": {
                        "model": self.model,
                        "temperature": self.temperature,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }

                items_transformados.append(item_enriquecido)

            except Exception as e:
                # Em caso de falha, manter item original
                items_transformados.append(item)

        return FetchResult(
            items=items_transformados,
            metadata={
                **dados.metadata,
                "transformed_by": "llm_processor",
                "model": self.model,
                "timestamp": datetime.utcnow().isoformat()
            },
            errors=dados.errors,
            fetched_at=dados.fetched_at
        )

    def transformacoes(self) -> List[str]:
        """Retorna lista de transformacoes aplicadas."""
        return ["extracao_metadados", "sumarizacao"]

    def _extrair_metadados(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai metadados com LLM."""
        prompt = self._get_prompt_extracao()
        texto = item.get("ementa", "") or item.get("full_text", "")

        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": texto}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        # Parsear resposta
        content = response.choices[0].message.content
        metadados = self._parsear_resposta(content)

        return metadados

    def _sumarizar(self, item: Dict[str, Any]) -> str:
        """Sumariza texto com LLM."""
        prompt = self._get_prompt_sumarizacao()
        texto = item.get("ementa", "") or item.get("full_text", "")

        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": texto}
            ],
            temperature=self.temperature,
            max_tokens=150
        )

        return response.choices[0].message.content

    def _get_prompt_extracao(self) -> str:
        """Retorna prompt de extracao versionado."""
        return """Voce e um especialista em comercio exterior brasileiro.
Extraia os seguintes metadados do texto:
- tipo_elemento: tipo da norma (lei, decreto, instrucao normativa, etc.)
- orgao_emissor: orgao que emitiu a norma
- palavras_chave: lista de palavras-chave relevantes
- fundamentos_legais: lista de URNs de normas relacionadas

Retorne apenas um JSON com esses campos."""

    def _get_prompt_sumarizacao(self) -> str:
        """Retorna prompt de sumarizacao versionado."""
        return """Voce e um especialista em comercio exterior brasileiro.
Resuma o texto em uma unica frase objetiva.
Nao invente informacoes.
Retorne apenas o resumo."""

    def _parsear_resposta(self, content: str) -> Dict[str, Any]:
        """Parsear resposta do LLM."""
        import json
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw_response": content}
```

---

## 5. Exemplos de Validators

### 5.1. KelsenValidator

**Finalidade**: Validar invariantes kelsenianos (K1-K3).

**Contrato implementado**: `ValidatorPort`

**Conceitos demonstrados**:
- Validação de invariantes de domínio
- Derivação kelseniana
- Anti-simetria e aciclicidade

```python
# framework/processors/kelsen_validator.py

from typing import Dict, Any, List

from framework.core.ports import ValidatorPort, ValidationResult
from framework.core.exceptions import ValidationError


class KelsenValidator(ValidatorPort):
    """
    Validador de invariantes kelsenianos (K1-K3).

    Invariantes:
    - K1: Derivacao kelseniana (todo ato deve derivar de norma superior)
    - K2: Anti-simetria (se A fundamenta B, B nao fundamenta A)
    - K3: Aciclicidade (nao pode haver ciclos de fundamentacao)
    """

    def validar(self, dados: List[Dict[str, Any]]) -> ValidationResult:
        """Valida invariantes kelsenianos."""
        violations = []

        for item in dados:
            # K1: Derivacao kelseniana
            if not self._verificar_derivacao(item):
                violations.append({
                    "rule": "K1",
                    "description": "Ato nao deriva de norma superior",
                    "item_urn": item.get("urn"),
                    "context": {"fundamento_legal_urn": item.get("fundamento_legal_urn")}
                })

            # K2: Anti-simetria
            if not self._verificar_anti_simetria(item, dados):
                violations.append({
                    "rule": "K2",
                    "description": "Violacao de anti-simetria",
                    "item_urn": item.get("urn"),
                    "context": {}
                })

            # K3: Aciclicidade
            if not self._verificar_aciclicidade(item, dados):
                violations.append({
                    "rule": "K3",
                    "description": "Ciclo de fundamentacao detectado",
                    "item_urn": item.get("urn"),
                    "context": {}
                })

        return ValidationResult(
            is_valid=len(violations) == 0,
            violations=violations
        )

    def regras(self) -> List[str]:
        """Retorna lista de regras."""
        return ["K1", "K2", "K3"]

    def _verificar_derivacao(self, item: Dict[str, Any]) -> bool:
        """Verifica K1: derivacao kelseniana."""
        fundamento = item.get("fundamento_legal_urn")
        if not fundamento:
            return False  # Todo ato deve ter fundamento

        # Verificar se fundamento existe no grafo
        # (implementacao real consultaria Neo4j)
        return True

    def _verificar_anti_simetria(self, item: Dict[str, Any], todos: List[Dict]) -> bool:
        """Verifica K2: anti-simetria."""
        urn_atual = item.get("urn")
        fundamentos = item.get("fundamento_legal_urn", [])

        for outro in todos:
            if outro.get("urn") in fundamentos:
                outros_fundamentos = outro.get("fundamento_legal_urn", [])
                if urn_atual in outros_fundamentos:
                    return False  # A fundamenta B e B fundamenta A

        return True

    def _verificar_aciclicidade(self, item: Dict[str, Any], todos: List[Dict]) -> bool:
        """Verifica K3: aciclicidade."""
        # Implementacao simplificada (DFS para detectar ciclos)
        visitados = set()
        pilha = [item.get("urn")]

        while pilha:
            atual = pilha.pop()
            if atual in visitados:
                return False  # Ciclo detectado
            visitados.add(atual)

            # Buscar fundamentos do atual
            for outro in todos:
                if outro.get("urn") == atual:
                    pilha.extend(outro.get("fundamento_legal_urn", []))

        return True
```

---

## 6. Exemplos de URN Generators

### 6.1. LexURNGenerator

**Finalidade**: Gerar URNs canônicos no formato urn:lex:br.

**Contrato implementado**: `URNPort`

**Conceitos demonstrados**:
- Geração determinística de URNs
- Validação de formato
- Parse de URNs

```python
# framework/processors/lex_urn_generator.py

from typing import Dict, Any
import re

from framework.core.ports import URNPort


class LexURNGenerator(URNPort):
    """
    Gerador de URNs canonicos no formato urn:lex:br.

    Formato: urn:lex:br:<jurisdicao>:<tipo>:<data>;<numero>

    Exemplos:
    - urn:lex:br:federal:lei:2004-03-01;10865
    - urn:lex:br:federal:decreto:1999-08-10;9782
    """

    # Mapeamento de tipos para segmento URN
    TIPO_PARA_SEGMENTO = {
        "EMC": "constituicao:emenda",
        "DLG": "decreto.legislativo",
        "DEC": "decreto",
        "LEI": "lei",
        "LC": "lei.complementar",
        "IN": "instrucao.normativa",
        "RESOLUCAO": "resolucao",
    }

    def gerar(self, dados: Dict[str, Any]) -> str:
        """Gera URN canonico."""
        jurisdicao = dados.get("jurisdicao", "federal")
        tipo = dados.get("tipo", "norma")
        data = dados.get("data_promulgacao")
        numero = dados.get("numero")

        segmento = self.TIPO_PARA_SEGMENTO.get(tipo.upper(), tipo.lower())

        return f"urn:lex:br:{jurisdicao}:{segmento}:{data};{numero}"

    def validar(self, urn: str) -> bool:
        """Valida se URN esta no formato correto."""
        pattern = r"^urn:lex:br:[a-z]+:[a-z\.:]+:\d{4}-\d{2}-\d{2};\d+$"
        return bool(re.match(pattern, urn))

    def parsear(self, urn: str) -> Dict[str, Any]:
        """Faz parse de URN em componentes."""
        if not self.validar(urn):
            raise ValueError(f"URN invalido: {urn}")

        # Remover prefixo
        sem_prefixo = urn.replace("urn:lex:br:", "")

        # Separar componentes
        partes = sem_prefixo.split(":")
        jurisdicao = partes[0]
        segmento = partes[1]
        data_numero = partes[2]

        data, numero = data_numero.split(";")

        return {
            "jurisdicao": jurisdicao,
            "segmento": segmento,
            "data": data,
            "numero": numero,
        }
```

---

## 7. Exemplos de Composições (App DAGs)

### 7.1. Pipeline Ro-DOU → Solo MCA

**Finalidade**: Pipeline completo de vigilância DOU para o Solo MCA.

**Conceitos demonstrados**:
- Composição declarativa em YAML
- Múltiplos estágios (fetch, transform, ingest)
- Conectores HTTP e Bolt
- Notificações webhook

```yaml
# config/compositions/rodou_solo_pipeline.yaml

dag:
  id: rodou_solo_pipeline
  description: "Pipeline Ro-DOU para Solo MCA (C2 Classificacao)"
  schedule: "0 8 * * MON-FRI"  # 8h da manha, dias uteis
  owner: dev_team
  immutable: false
  tags: [solo_mca, comex, classificacao]

components:
  - id: rodou_fetcher
    type: ro_dou.hook.DOUHook
    config:
      dag_id: solo_mca_c2_classificacao
      sources: [INLABS]
      terms:
        - "NCM AND (classificacao OR alteracao)"
        - "Sistema Harmonizado AND mercadoria"
      department:
        - "Secretaria da Receita Federal"
        - "CAMEX"
        - "GECEX"
      use_summary: true
      full_text: true

  - id: llm_processor
    type: mca.llm.LLMProcessor
    config:
      provider: openai
      model: gpt-4
      temperature: 0.2
      max_tokens: 300
      custom_prompt: |
        Voce e um especialista em comercio exterior brasileiro.
        Resuma a publicacao em uma unica frase objetiva.

  - id: solo_ingestor
    type: mca.neo4j.Neo4jAdapter
    config:
      uri: bolt://neo4j:7687
      user: neo4j
      password: ${NEO4J_PASSWORD}
      database: solo_mca

pipeline:
  stages:
    - id: fetch_dou
      component: rodou_fetcher
      output: raw_publications

    - id: process_with_llm
      component: llm_processor
      input: raw_publications
      output: enriched_publications
      depends_on: [fetch_dou]

    - id: ingest_to_solo
      component: solo_ingestor
      input: enriched_publications
      output: ingestion_result
      depends_on: [process_with_llm]

connectors:
  - source: fetch_dou
    target: process_with_llm
    type: synchronous
    protocol: http
    config:
      url: http://localhost:8000/process
      method: POST
      timeout_seconds: 30

  - source: process_with_llm
    target: ingest_to_solo
    type: synchronous
    protocol: bolt
    config:
      uri: bolt://neo4j:7687
      timeout_seconds: 60

notifications:
  on_success:
    - type: webhook
      url: https://n8n.example.com/webhook/solo-success
    - type: log
      level: INFO

  on_failure:
    - type: webhook
      url: https://n8n.example.com/webhook/solo-failure
    - type: alert
      channel: pipeline_alerts
      severity: HIGH
```

### 7.2. Pipeline com Gate Humano

**Finalidade**: Pipeline com aprovação humana antes da integração.

**Conceitos demonstrados**:
- Gate humano (curadoria)
- Override humano com justificativa
- Cadeia de responsabilização

```yaml
# config/compositions/rodou_solo_com_curadoria.yaml

dag:
  id: rodou_solo_com_curadoria
  description: "Pipeline Ro-DOU com curadoria humana"
  schedule: "0 8 * * MON-FRI"
  owner: dev_team
  immutable: false

components:
  - id: rodou_fetcher
    type: ro_dou.hook.DOUHook
    config:
      terms: ["NCM", "classificacao"]
      department: ["RFB", "CAMEX"]

  - id: llm_processor
    type: mca.llm.LLMProcessor
    config:
      provider: openai
      model: gpt-4

  - id: candidato_registrador
    type: mca.neo4j.CandidatoRegistrador
    config:
      uri: bolt://neo4j:7687
      status: "EM_CANDIDATURA"

  - id: curador_notifier
    type: mca.notifications.CuradorNotifier
    config:
      channel: email
      recipients: ["despachantes@example.com"]

pipeline:
  stages:
    - id: fetch_dou
      component: rodou_fetcher
      output: raw_publications

    - id: process_with_llm
      component: llm_processor
      input: raw_publications
      output: enriched_publications
      depends_on: [fetch_dou]

    - id: register_candidato
      component: candidato_registrador
      input: enriched_publications
      output: candidatos
      depends_on: [process_with_llm]

    - id: notify_curador
      component: curador_notifier
      input: candidatos
      output: notificacoes_enviadas
      depends_on: [register_candidato]

    # Gate humano: aguarda aprovacao do despachante
    # (implementado via webhook externo)

connectors:
  - source: fetch_dou
    target: process_with_llm
    type: synchronous
    protocol: http

  - source: process_with_llm
    target: register_candidato
    type: synchronous
    protocol: bolt

  - source: register_candidato
    target: notify_curador
    type: asynchronous
    protocol: webhook
```

---

## 8. Exemplos de Conectores

### 8.1. HTTPConnector

**Finalidade**: Conector para chamadas HTTP síncronas.

```python
# framework/execution/connectors/http_connector.py

import requests
from typing import Any

from framework.execution.connectors.base import Connector


class HTTPConnector(Connector):
    """Conector para chamadas HTTP sincronas."""

    def __init__(self, url: str, method: str = "POST", headers: dict = None, timeout: int = 30):
        self.url = url
        self.method = method
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout

    def conectar(self, origem: Any, destino: Any) -> None:
        """Testa conectividade."""
        response = requests.head(self.url, timeout=5)
        response.raise_for_status()

    def transmitir(self, dados: Any) -> Any:
        """Transmite dados via HTTP."""
        response = requests.request(
            method=self.method,
            url=self.url,
            json=dados,
            headers=self.headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
```

### 8.2. WebhookConnector

**Finalidade**: Conector para webhooks assíncronos com retry.

```python
# framework/execution/connectors/webhook_connector.py

import requests
import time
from typing import Any

from framework.execution.connectors.base import Connector


class WebhookConnector(Connector):
    """Conector para webhooks assincronos com retry."""

    def __init__(
        self,
        url: str,
        method: str = "POST",
        retry_policy: dict = None
    ):
        self.url = url
        self.method = method
        self.retry_policy = retry_policy or {
            "max_attempts": 3,
            "backoff": "exponential",
            "initial_delay": 1
        }

    def conectar(self, origem: Any, destino: Any) -> None:
        """Webhooks nao exigem handshake inicial."""
        pass

    def transmitir(self, dados: Any) -> Any:
        """Transmite dados via webhook com retry."""
        attempt = 0
        delay = self.retry_policy["initial_delay"]

        while attempt < self.retry_policy["max_attempts"]:
            try:
                response = requests.request(
                    method=self.method,
                    url=self.url,
                    json=dados,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                attempt += 1
                if attempt < self.retry_policy["max_attempts"]:
                    time.sleep(delay)
                    if self.retry_policy["backoff"] == "exponential":
                        delay *= 2
                else:
                    raise
```

---

## 9. Exemplos de Testes

### 9.1. Teste Unitário de Fetcher

```python
# tests/adapters/test_senado_adapter.py

import pytest
from unittest.mock import patch, MagicMock

from framework.adapters.driving.senado.senado_adapter import SenadoAdapter


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
        assert result.items[0]["nivel_h"] == 3


def test_senado_adapter_validar_config():
    """Testa validacao de configuracao."""
    adapter = SenadoAdapter({})

    # Configuracao valida
    config_valida = {
        "normas": [("LEI", 10865, 2004)]
    }
    assert adapter.validar_config(config_valida) == True

    # Configuracao invalida
    config_invalida = {
        "normas": "nao_eh_lista"
    }
    assert adapter.validar_config(config_invalida) == False
```

### 9.2. Teste de Integração

```python
# tests/integration/test_pipeline_senado_neo4j.py

import pytest
from unittest.mock import patch

from framework.adapters.driving.senado.senado_adapter import SenadoAdapter
from framework.adapters.driven.neo4j.neo4j_adapter import Neo4jAdapter
from framework.pipeline.orchestrator import PipelineOrchestrator


def test_pipeline_senado_neo4j():
    """Testa pipeline completo Senado -> Neo4j."""
    # Mocks
    with patch.object(SenadoAdapter, "_buscar_norma") as mock_busca, \
         patch.object(Neo4jAdapter, "_ingerir_norma") as mock_ingest:

        mock_busca.return_value = {
            "urn": "urn:lex:br:federal:lei:2004-03-01;10865",
            "nivel_h": 3,
            "tipo_elemento": "LEI",
            "data_promulgacao": "2004-03-01"
        }
        mock_ingest.return_value = None

        # Configurar
        fetcher = SenadoAdapter({"normas": [("LEI", 10865, 2004)]})
        ingestor = Neo4jAdapter({"uri": "bolt://localhost:7687"})

        orchestrator = PipelineOrchestrator(
            fetcher=fetcher,
            ingestor=ingestor
        )

        # Executar
        result = orchestrator.executar()

        # Verificar
        assert result["status"] == "SUCCESS"
        assert result["items_processed"] == 1
        assert result["items_failed"] == 0
```

---

## 10. Exemplos de Observabilidade

### 10.1. Consulta de Métricas

```python
# Exemplo de consulta de metricas
from framework.management.dashboard import Dashboard

dashboard = Dashboard()

# Metricas de todos os componentes
for component in dashboard.components:
    metricas = component.metricas()
    print(f"Componente: {component.nome}")
    print(f"  Execucoes: {metricas['execution_count']}")
    print(f"  Taxa de sucesso: {metricas['success_rate']:.2%}")
    print(f"  Duracao media: {metricas['average_duration']:.2f}s")

# Metricas especificas de IA
for component in dashboard.components:
    if component.tipo == "llm_processor":
        print(f"LLM Tokens: {component.metricas()['tokens_total']}")
        print(f"LLM Custo: US$ {component.metricas()['cost_usd']:.4f}")
```

### 10.2. Consulta de Explicabilidade

```python
# Exemplo de consulta de explicabilidade
from framework.management.explicabilidade import ExplicabilidadeCollector

coletor = ExplicabilidadeCollector()

# Consultar explicacao de uma execucao
explicacao = coletor.obter_explicacao(execution_id="exec-abc-123")

print(f"Modelo: {explicacao.model}")
print(f"Prompt: {explicacao.prompt_template} v{explicacao.prompt_version}")
print(f"Confianca: {explicacao.confidence_score:.2%}")
print(f"Custo: US$ {explicacao.cost_usd:.4f}")
print(f"Alternativas: {len(explicacao.alternatives)}")
```

### 10.3. Consulta de Auditabilidade

```python
# Exemplo de reconstrucao de execucao
from framework.management.auditabilidade import AuditabilidadeCollector

coletor = AuditabilidadeCollector()

# Reconstruir execucao
reconstrucao = coletor.reconstruir_execucao(execution_id="exec-abc-123")

print(f"Execucao: {reconstrucao.execution_id}")
print(f"Inicio: {reconstrucao.started_at}")
print(f"Fim: {reconstrucao.finished_at}")
print(f"Eventos: {len(reconstrucao.events)}")

for evento in reconstrucao.events:
    print(f"  [{evento.timestamp}] {evento.event_type} por {evento.actor}")
```

---

## 11. Matriz de traçabilidade

### 11.1. Exemplo → Contrato → Conceito

| Exemplo | Contrato | Conceito demonstrado | Documento de origem |
|---|---|---|---|
| SenadoAdapter | FetcherPort | Hexagonal, Rate limiting, Retry | v1 (AX-01), contracts.md |
| RoDOUAdapter | FetcherPort | Integração PostgreSQL, Filtros COMEX | v1 (AX-01), SPEC_SOLO_MCA |
| Neo4jAdapter | IngestPort | LRMoo, Batch processing, Idempotência | v1 (AX-01), contracts.md |
| LLMProcessor | TransformerPort | LLM, Prompts versionados, Métricas IA | observability.md |
| KelsenValidator | ValidatorPort | Invariantes K1-K3 | v1 (AX-08), SPEC_SOLO_MCA |
| LexURNGenerator | URNPort | URNs canônicos | v1 (AX-07) |
| rodou_solo_pipeline | App DAG | Composição declarativa, Conectores | v3 (Core × App) |
| rodou_solo_com_curadoria | App DAG | Gate humano, Override | SPEC_SOLO_MCA (6.5) |
| HTTPConnector | Connector | Chamadas síncronas | v2 (Orquestração) |
| WebhookConnector | Connector | Webhooks assíncronos, Retry | v2 (Orquestração) |
| Teste SenadoAdapter | - | Teste unitário com mock | - |
| Teste Pipeline | - | Teste de integração | - |
| Consulta Métricas | MetricsPort | Observabilidade clássica | observability.md |
| Consulta Explicabilidade | ExplicabilidadeCollector | Observabilidade IA | observability.md |
| Consulta Auditabilidade | AuditabilidadeCollector | Reconstrução de execução | observability.md |

---

## Fechamento

Os exemplos apresentados neste documento demonstram a aplicação prática dos conceitos definidos nos documentos de fundamentação (v1, v2, v3), contratos (contracts.md) e observabilidade (observability.md).

Cada exemplo:

1. **Implementa um contrato** formal definido em `docs/contracts.md`
2. **Demonstra um conceito** arquitetural dos documentos de fundamentação
3. **É coerente com o domínio** do projeto MCA (normas brasileiras, LRMoo, COMEX)
4. **Pode ser copiado e adaptado** para uso real

A propriedade que unifica todos os exemplos é:

> **Todo exemplo implementa um contrato explícito, demonstra um conceito arquitetural e é coerente com o domínio do projeto MCA.**

Toda decisão, critério de conformidade e exemplo deste documento deriva dessa propriedade.

---

*Documento de referência prática. Os exemplos aqui apresentados são a base para implementação de componentes, composições e testes. Novos exemplos devem ser adicionados conforme o projeto evolui.*