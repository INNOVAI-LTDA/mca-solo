"""Contratos de dados e gestao imutaveis do Core do MCA-Solo (ID 1.2).

Este modulo materializa os contratos de payload que trafegam entre os
componentes do pipeline (Orquestracao) e o snapshot de telemetria de cada
componente registrado (Gestao), conforme as Secoes 4 e 5 de
``docs/contracts.md``, a Secao 3.2.1 de
``docs/arquitetura_molde_v2_orquestracao_gestao.md`` e ``docs/examples.md``.

Regra de Ouro: uma vez materializado, o estado de um Contrato de Dados
(Dominio) ou de Gestao (Telemetria) e definitivo e imutavel. Novas
informacoes (ex.: adicao de um erro de validacao) devem ser materializadas
atraves da criacao de uma NOVA instancia (padrao de copia defensiva via
``dataclasses.replace()``), preservando o rastro de auditoria do estado
anterior (Sinais de Observabilidade: Auditabilidade e Responsabilizacao).

Taxonomia das entidades:
    Grupo A - Dominio (payloads de pipeline):
        - FetchResult: saida unificada de qualquer ``FetcherPort``.
        - IngestResult: saida unificada de qualquer ``IngestPort``.
        - ValidationResult: saida unificada de qualquer ``ValidatorPort``.

    Grupo B - Gestao (telemetria):
        - ComponentStatus: enumeracao rigida dos estados de saude.
        - ComponentMetrics: snapshot imutavel de metricas de um componente.

Proveniencia:
    - Contratos de Dominio carregam proveniencia de execucao (``source``
      via ``metadata`` e ``timestamp`` via ``fetched_at`` / ``ingested_at``
      / ``validated_at``). O ``execution_id`` e injetado pelo contexto de
      orquestracao, nao sendo campo direto da entidade de payload
      (padrao LRMoo / Hexagonal).
    - Contratos de Gestao carregam proveniencia de telemetria
      (``component_id`` e ``collected_at``), sem ``execution_id``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utcnow() -> datetime:
    """Retorna o timestamp UTC corrente usado pelos ``default_factory``.

    Centralizar a geracao de timestamps em uma unica funcao privada
    permite monkeypatching deterministico nos testes e preserva a
    auditabilidade da linha temporal dos contratos. Utiliza objetos
    timezone-aware (o contrato historico de ``docs/contracts.md`` era
    ``datetime.utcnow()``, hoje deprecado na stdlib).

    Returns:
        O ``datetime`` atual em UTC (timezone-aware).
    """
    return datetime.now(timezone.utc)


class ComponentStatus(str, Enum):
    """Estados de saude possiveis de um componente gerenciado (v2, 3.2.1).

    A enumeracao e rigidamente tipada para eliminar strings magicas no
    ciclo de vida monitorado transversalmente pela camada de Gestao.

    Attributes:
        PRONTO: Componente registrado, saudavel e aguardando execucao.
        EXECUTANDO: Componente com execucao em andamento.
        DEGRADADO: Componente operacional, porem com anomalias (ex.: taxa
            de erro acima do limiar).
        PARADO: Componente indisponivel / desativado.
    """

    PRONTO = "PRONTO"
    EXECUTANDO = "EXECUTANDO"
    DEGRADADO = "DEGRADADO"
    PARADO = "PARADO"


@dataclass(frozen=True)
class FetchResult:
    """Contrato unificado de saida para todos os fetchers (Grupo A - Dominio).

    Retornado por qualquer ``FetcherPort`` ao extrair dados de uma fonte
    externa. Carrega a proveniencia da fonte (``source`` via ``metadata``)
    e o instante de coleta (``fetched_at``).

    A classe e imutavel (``frozen=True``): qualquer evolucao de estado deve
    ocorrer por copia defensiva (ver ``with_error``), preservando o rastro
    de auditoria do estado anterior.

    Invariantes:
        - ``items`` e sempre uma lista (pode ser vazia).
        - ``metadata`` contem a proveniencia (source, timestamp, etc.).
        - ``errors`` contem falhas nao fatais acumuladas.
        - ``fetched_at`` e sempre definido.

    Attributes:
        items: Lista de itens brutos extraidos da fonte externa.
        metadata: Dicionario de proveniencia/contexto da coleta (ex.:
            ``{"source": "senado"}``). Default: dict vazio (independente
            por instancia, via ``default_factory``).
        errors: Lista de erros nao fatais registrados durante a coleta.
            Cada erro e um dict com as chaves ``error``, ``context`` e
            ``timestamp``. Default: lista vazia (independente por
            instancia, via ``default_factory``).
        fetched_at: Timestamp UTC da extracao. Default: agora (UTC).

    Examples:
        >>> result = FetchResult(items=[1, 2, 3], metadata={"source": "camara"})
        >>> result.items_count
        3
        >>> result.has_errors
        False
        >>> novo = result.with_error("Timeout", {"url": "http://x"})
        >>> result.errors   # instancia original permanece intacta
        []
        >>> len(novo.errors)
        1
    """

    items: List[Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=_utcnow)

    @property
    def items_count(self) -> int:
        """Numero de itens extraidos.

        Returns:
            Quantidade de elementos em ``items`` (O(1) via ``len``).
        """
        return len(self.items)

    @property
    def has_errors(self) -> bool:
        """Indica se ha erros nao fatais registrados na coleta.

        Returns:
            ``True`` se e somente se ``len(self.errors) > 0``.
        """
        return len(self.errors) > 0

    def with_error(
        self, erro: str, contexto: Optional[Dict[str, Any]] = None
    ) -> "FetchResult":
        """Retorna uma NOVA instancia com o erro adicionado (copia defensiva).

        IMPORTANTE: este metodo NAO modifica a instancia atual. Como a
        classe e ``frozen``, a evolucao de estado e materializada atraves
        de ``dataclasses.replace()``, que constroi uma nova instancia com
        a lista ``errors`` estendida por um unico registro de erro. O
        estado anterior permanece imutavel, preservando o rastro de
        auditoria (Auditabilidade). Substitui o antigo padrao mutavel
        ``adicionar_erro``.

        Args:
            erro: Mensagem legivel do erro nao fatal (ex.: ``"Timeout"``).
            contexto: Metadados estruturados do erro (ex.: ``{"url": ...}``).
                ``None`` e normalizado para ``{}``. Uma copia defensiva e
                gravada no novo registro para evitar aliasing externo.

        Returns:
            Um NOVO ``FetchResult`` igual ao atual, porem com o registro
            de erro appendedado a ``errors`` (lista tambem nova; os demais
            campos sao herdados por ``dataclasses.replace``).

        Examples:
            >>> r = FetchResult(items=[])
            >>> r2 = r.with_error("Timeout", {"url": "https://x"})
            >>> r.errors
            []
            >>> r2.errors[0]["error"]
            'Timeout'
        """
        registro: Dict[str, Any] = {
            "error": erro,
            "context": dict(contexto) if contexto else {},
            "timestamp": _utcnow().isoformat(),
        }
        novas_errors: List[Dict[str, Any]] = list(self.errors) + [registro]
        return dataclasses.replace(self, errors=novas_errors)


@dataclass(frozen=True)
class IngestResult:
    """Contrato unificado de saida para todos os ingestors (Grupo A - Dominio).

    Retornado por qualquer ``IngestPort`` ao persistir dados. Carrega
    contadores de sucesso/falha, os IDs efetivamente ingeridos e o instante
    da ingestao (``ingested_at``). Instancia imutavel (``frozen=True``).

    Invariantes:
        - ``success_count + failure_count == total_count``.
        - ``ingested_ids`` contem apenas IDs de sucesso.
        - ``errors`` contem falhas individuais da persistencia.

    Attributes:
        success_count: Quantidade de itens persistidos com sucesso.
        failure_count: Quantidade de itens que falharam ao persistir.
        ingested_ids: Lista de identificadores dos itens ingeridos com
            sucesso. Default: lista vazia (via ``default_factory``).
        errors: Lista de falhas individuais de ingestao. Default: lista
            vazia (via ``default_factory``).
        ingested_at: Timestamp UTC da ingestao. Default: agora (UTC).

    Examples:
        >>> r = IngestResult(success_count=8, failure_count=2)
        >>> r.total_count
        10
        >>> r.success_rate
        80.0
        >>> IngestResult().success_rate  # evita ZeroDivisionError
        0.0
    """

    success_count: int = 0
    failure_count: int = 0
    ingested_ids: List[Any] = field(default_factory=list)
    errors: List[Any] = field(default_factory=list)
    ingested_at: datetime = field(default_factory=_utcnow)

    @property
    def total_count(self) -> int:
        """Total de itens processados pela ingestao.

        Returns:
            Soma estrita de ``success_count + failure_count`` (O(1)).
        """
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        """Taxa de sucesso em percentual (0.0 a 100.0).

        Caso de borda: retorna ``0.0`` quando ``total_count == 0``,
        evitando ``ZeroDivisionError``.

        Returns:
            Percentual de itens ingeridos com sucesso.
        """
        total = self.total_count
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100


@dataclass(frozen=True)
class ValidationResult:
    """Contrato para validacao de invariantes de dominio (Grupo A - Dominio).

    Retornado por qualquer ``ValidatorPort`` ao checar invariantes (ex.:
    Kelsen, LRMoo). Instancia imutavel (``frozen=True``).

    Invariantes:
        - ``is_valid`` e ``True`` se e somente se ``violations`` esta vazio
          (garantida no construtor via ``__post_init__``).
        - ``violations`` contem detalhes de cada regra violada.

    Attributes:
        is_valid: Flag de validade do conjunto validado.
        violations: Lista de registros de violacao (ex.: ``{"rule": "H1",
            "description": ...}``). Default: lista vazia (via
            ``default_factory``).
        validated_at: Timestamp UTC da validacao. Default: agora (UTC).

    Examples:
        >>> v = ValidationResult(is_valid=False, violations=[{"rule": "K1"}])
        >>> v.violations_count
        1
        >>> ValidationResult(is_valid=True).violations_count
        0
    """

    is_valid: bool
    violations: List[Dict[str, Any]] = field(default_factory=list)
    validated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        """Valida o invariante de dominio no momento da materializacao.

        Garante que ``is_valid`` e coerente com ``violations``: um
        resultado so e valido se nao houver violacoes. Tentar construir
        um estado incoerente levanta ``ValueError`` imediatamente, antes
        que o snapshot imutavel seja registrado (barreira de entrada).

        Raises:
            ValueError: Se ``is_valid`` for ``True`` com ``violations``
                nao vazias, ou ``False`` com ``violations`` vazias.
        """
        if self.is_valid and len(self.violations) > 0:
            raise ValueError(
                "Invariante violado: ValidationResult com violations "
                "nao vazias deve ter is_valid=False."
            )
        if not self.is_valid and len(self.violations) == 0:
            raise ValueError(
                "Invariante violado: ValidationResult com is_valid=False "
                "deve registrar ao menos uma violacao."
            )

    @property
    def violations_count(self) -> int:
        """Numero de violacoes de invariante registradas.

        Returns:
            Quantidade de elementos em ``violations`` (O(1) via ``len``).
        """
        return len(self.violations)


@dataclass(frozen=True)
class ComponentMetrics:
    """Snapshot imutavel de telemetria de um componente (Grupo B - Gestao).

    Retornado pelo ``InvolucroGestao`` (ou ``MetricsPort``) ao consultar o
    estado de saude e telemetria agregada de um componente registrado.
    Representa um fato historico no momento da coleta (``collected_at``),
    nunca um estado mutavel em memoria. Instancia imutavel
    (``frozen=True``).

    Proveniencia de gestao: ``component_id`` e ``collected_at``.
    Diferentemente dos contratos de Dominio, NAO possui ``execution_id``.

    Attributes:
        component_id: Identificador unico do componente monitorado.
        collected_at: Timestamp UTC do snapshot de telemetria. Default:
            agora (UTC).
        execution_count: Numero total de execucoes observadas.
        success_rate: Proporcao (percentual) de execucoes bem-sucedidas.
        average_duration: Duracao media das execucoes, em segundos.
        error_rate: Proporcao (percentual) de execucoes com erro.
        last_execution: Timestamp UTC da ultima execucao; ``None`` antes
            da primeira execucao do componente.
        status: Estado atual do componente. Tipado rigidamente por
            ``ComponentStatus`` (sem strings magicas). Default:
            ``ComponentStatus.PRONTO``.

    Examples:
        >>> m = ComponentMetrics(component_id="fetcher_senado")
        >>> m.status
        <ComponentStatus.PRONTO: 'PRONTO'>
        >>> m.last_execution is None
        True
    """

    # Proveniencia de Telemetria
    component_id: str
    collected_at: datetime = field(default_factory=_utcnow)

    # Indicadores Operacionais (Snapshot)
    execution_count: int = 0
    success_rate: float = 0.0
    average_duration: float = 0.0
    error_rate: float = 0.0
    last_execution: Optional[datetime] = None
    status: ComponentStatus = ComponentStatus.PRONTO
