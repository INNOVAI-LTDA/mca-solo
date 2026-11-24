# Exemplos de Implementação do MCA Framework

| Campo | Valor |
|---|---|
| **Documento** | `docs/examples.md` |
| **Versão** | 1.1 |
| **Data** | 2026-11-24 |
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
| 7.1–7.2 | Composição (declarativa) | App DAG YAML |
| 7.3 | Composição (programática) | `Orchestrator` (ID 2.1) |
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