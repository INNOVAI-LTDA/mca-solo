"""Conectores de execucao do MCA-Solo (ID 2.2).

Mecanismo de Orquestracao: materializa Phi : E -> Conectores
(docs/arquitetura_molde_v2_orquestracao_gestao.md, Secao 2.3).

Regras de Ouro aplicaveis:
- "A excecao e o veiculo de transporte de contexto para Observabilidade."
- "Falha explicita: toda violacao interrompe, sem fallback."
- "Gestao e invariante sob substituicao de implementacao."
- "Todo componente registrado deve herdar nominalmente de uma ABC de porta."

Camada: ``framework/execution/`` (Orquestracao). Conectores NAO sao
componentes de dominio: herdam de ``Connector`` (ABC de execucao) e
devem ser rejeitados pelo ``ComponentRegistry`` (REG-02).

Dependencias de terceiros (``requests``, ``neo4j``) sao importadas
lazily (CONN-06): sua ausencia produz ``ConfigurationError`` com
``context["dependency"]``, nunca ``ImportError`` cru em runtime.
"""

from __future__ import annotations

import abc
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Final
from urllib.parse import urlparse

from framework.core.exceptions import (
    ConfigurationError,
    FetcherError,
    FrameworkError,
    IngestorError,
)

__all__ = [
    "BACKOFF_STRATEGIES",
    "BoltConnector",
    "Connector",
    "ConnectorConfig",
    "ConnectorResponse",
    "HTTPConnector",
    "REDACTED_KEYS",
    "RETRYABLE_STATUS",
    "RetryPolicy",
    "TransportResult",
    "WebhookConnector",
    "build_connector",
]

# ---------------------------------------------------------------------------
# Vocabularios imutaveis (Regra de Ouro: Estado de Contrato e definitivo)
# ---------------------------------------------------------------------------

#: Status HTTP classificados como retryaveis por padrao (CONN-03).
RETRYABLE_STATUS: Final[frozenset[int]] = frozenset(
    {408, 425, 429, 500, 502, 503, 504}
)

#: Estrategias de backoff suportadas (CFG-03).
BACKOFF_STRATEGIES: Final[frozenset[str]] = frozenset(
    {"fixed", "linear", "exponential"}
)

#: Chaves sensíveis redigidas em ``metadados()`` e ``context`` (SEC-01).
REDACTED_KEYS: Final[frozenset[str]] = frozenset(
    {"password", "authorization", "secret", "api_key", "token"}
)

#: Esquemas validos por protocolo (CFG-05).
HTTP_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})
BOLT_SCHEMES: Final[frozenset[str]] = frozenset(
    {"bolt", "bolt+s", "bolt+ssc", "neo4j", "neo4j+s"}
)

#: Verbos HTTP permitidos (CFG-06).
HTTP_METHODS: Final[frozenset[str]] = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}
)


# ---------------------------------------------------------------------------
# Utilitarios internos
# ---------------------------------------------------------------------------


def _redact(mapping: dict[str, Any]) -> dict[str, Any]:
    """Retorna copia superficial com valores de chaves sensíveis redigidos.

    Implementa SEC-01: ``password``, ``authorization``, ``secret``,
    ``api_key`` e ``token`` sao substituidos por ``"***"``. Chaves
    desconhecidas sao preservadas. A copia e superficial (nao recursiva)
    porque os conectores apenas expoem metadados de nivel-1.

    Args:
        mapping: Dicionario a redigir.

    Returns:
        Novo dicionario com segredos redigidos.
    """
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        if key.lower() in REDACTED_KEYS:
            out[key] = "***"
        else:
            out[key] = value
    return out


def _validate_scheme(uri: str, allowed: frozenset[str], rule: str) -> None:
    """Valida esquema de URI contra um conjunto permitido (CFG-05).

    Args:
        uri: URI a validar.
        allowed: Esquemas permitidos.
        rule: Regra de configuracao violada (para diagnostico).

    Raises:
        ConfigurationError: Se o esquema nao estiver em ``allowed``.
    """
    try:
        parsed = urlparse(uri)
    except ValueError as exc:
        raise ConfigurationError(
            f"URI invalida: {uri!r}",
            context={"uri": uri, "rule": rule},
            cause=exc,
        ) from exc
    if parsed.scheme not in allowed:
        raise ConfigurationError(
            f"Esquema '{parsed.scheme}' nao permitido; esperados: "
            f"{sorted(allowed)}",
            context={"uri": uri, "scheme": parsed.scheme, "rule": rule},
        )


# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetryPolicy:
    """Politica de repeticao deterministica e imutavel (v2, Secao 4.2.4).

    Pre-condicoes:
        - ``max_attempts >= 1`` (CFG-02).
        - ``backoff`` em ``BACKOFF_STRATEGIES`` (CFG-03).
        - ``0 <= initial_delay <= max_delay`` e ``multiplier >= 1.0`` (CFG-04).
    Pos-condicoes:
        - ``delay_for(attempt)`` retorna atraso em segundos, limitado por
          ``max_delay``.
        - ``should_retry(status, attempt)`` decide deterministicamente.
    Invariantes:
        - ``frozen=True`` (imutabilidade estrutural).
        - ``delay_for`` e pura (sem ``random``, sem I/O).

    Attributes:
        max_attempts: Numero maximo de tentativas (>= 1).
        backoff: Estrategia de backoff (``fixed``/``linear``/``exponential``).
        initial_delay: Atraso inicial em segundos (>= 0).
        max_delay: Teto do atraso em segundos (>= ``initial_delay``).
        multiplier: Multiplicador do backoff (>= 1.0).
        retryable_status: Conjunto de status HTTP retryaveis.

    Examples:
        >>> p = RetryPolicy(max_attempts=3, backoff="exponential")
        >>> p.delay_for(1)
        1.0
        >>> p.delay_for(2)
        2.0
        >>> p.delay_for(3)
        4.0
    """

    max_attempts: int = 3
    backoff: str = "exponential"
    initial_delay: float = 1.0
    max_delay: float = 30.0
    multiplier: float = 2.0
    retryable_status: frozenset[int] = RETRYABLE_STATUS

    def __post_init__(self) -> None:
        """Valida CFG-02..CFG-04; levanta ConfigurationError(rule=...)."""
        if not isinstance(self.max_attempts, int) or self.max_attempts < 1:
            raise ConfigurationError(
                "RetryPolicy.max_attempts deve ser int >= 1",
                context={
                    "rule": "CFG-02",
                    "max_attempts": self.max_attempts,
                },
            )
        if self.backoff not in BACKOFF_STRATEGIES:
            raise ConfigurationError(
                f"RetryPolicy.backoff invalido: {self.backoff!r}",
                context={
                    "rule": "CFG-03",
                    "backoff": self.backoff,
                    "allowed": sorted(BACKOFF_STRATEGIES),
                },
            )
        if (
            not isinstance(self.initial_delay, (int, float))
            or self.initial_delay < 0
        ):
            raise ConfigurationError(
                "RetryPolicy.initial_delay deve ser >= 0",
                context={"rule": "CFG-04", "initial_delay": self.initial_delay},
            )
        if (
            not isinstance(self.max_delay, (int, float))
            or self.max_delay < self.initial_delay
        ):
            raise ConfigurationError(
                "RetryPolicy.max_delay deve ser >= initial_delay",
                context={
                    "rule": "CFG-04",
                    "max_delay": self.max_delay,
                    "initial_delay": self.initial_delay,
                },
            )
        if (
            not isinstance(self.multiplier, (int, float))
            or self.multiplier < 1.0
        ):
            raise ConfigurationError(
                "RetryPolicy.multiplier deve ser >= 1.0",
                context={"rule": "CFG-04", "multiplier": self.multiplier},
            )

    def delay_for(self, attempt: int) -> float:
        """Retorna o atraso (s) da tentativa ``attempt`` (1-based), com teto.

        Args:
            attempt: Numero da tentativa ja executada (>= 1).

        Returns:
            Atraso em segundos, limitado por ``max_delay``.

        Raises:
            ConfigurationError: Se ``attempt`` < 1 (CFG-02).
        """
        if not isinstance(attempt, int) or attempt < 1:
            raise ConfigurationError(
                "delay_for(attempt) exige attempt >= 1",
                context={"rule": "CFG-02", "attempt": attempt},
            )
        if self.backoff == "fixed":
            delay = self.initial_delay
        elif self.backoff == "linear":
            delay = self.initial_delay * attempt
        else:  # exponential
            delay = self.initial_delay * (self.multiplier ** (attempt - 1))
        return min(delay, self.max_delay)

    def should_retry(self, status_code: int | None, attempt: int) -> bool:
        """Decide se ha nova tentativa (CONN-02 / CONN-03).

        Args:
            status_code: Status HTTP da tentativa (None se excecao de rede).
            attempt: Tentativa ja executada (1-based).

        Returns:
            True se ``attempt < max_attempts`` e (status e retryavel ou
            status e None, i.e., excecao de rede).
        """
        if attempt >= self.max_attempts:
            return False
        if status_code is None:
            return True
        return status_code in self.retryable_status


# ---------------------------------------------------------------------------
# ConnectorConfig
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConnectorConfig:
    """Configuracao imutavel de transporte (timeout + retry + headers).

    Pre-condicoes:
        - ``timeout_seconds > 0`` e finito (CFG-01).
    Pos-condicoes:
        - ``headers`` e copia defensiva do dict fornecido.
    Invariantes:
        - ``frozen=True``.

    Attributes:
        timeout_seconds: Timeout por tentativa (s).
        retry: Politica de retry (default: RetryPolicy()).
        headers: Headers HTTP adicionais (copia defensiva).
        verify_tls: Verificar certificado TLS (default: True).
    """

    timeout_seconds: float = 30.0
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    headers: dict[str, str] = field(default_factory=dict)
    verify_tls: bool = True

    def __post_init__(self) -> None:
        """Valida CFG-01; copia defensiva de ``headers``."""
        if (
            not isinstance(self.timeout_seconds, (int, float))
            or self.timeout_seconds <= 0
        ):
            raise ConfigurationError(
                "ConnectorConfig.timeout_seconds deve ser > 0",
                context={
                    "rule": "CFG-01",
                    "timeout_seconds": self.timeout_seconds,
                },
            )
        if isinstance(self.timeout_seconds, float) and (
            self.timeout_seconds != self.timeout_seconds  # NaN check
            or self.timeout_seconds == float("inf")
        ):
            raise ConfigurationError(
                "ConnectorConfig.timeout_seconds deve ser finito",
                context={
                    "rule": "CFG-01",
                    "timeout_seconds": self.timeout_seconds,
                },
            )
        # Copia defensiva: mutar o dict externo nao afeta a config.
        object.__setattr__(self, "headers", dict(self.headers))


# ---------------------------------------------------------------------------
# TransportResult / ConnectorResponse
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransportResult:
    """Resposta bruta normalizada, protocolo-agnostica.

    Attributes:
        status_code: Status HTTP-like (Bolt mapeia 200/503).
        body: Corpo da resposta (dict/list/str/None).
        headers: Headers de resposta (default: dict vazio).
    """

    status_code: int
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorResponse:
    """Snapshot imutavel do resultado, com proveniencia de transporte.

    Attributes:
        payload: Corpo processado da resposta.
        status_code: Status HTTP-like.
        attempts: Numero de tentativas executadas (>= 1).
        duration_seconds: Duracao total (s) (>= 0).
        metadata: Metadados de proveniencia (protocol, endpoint, ...).
    """

    payload: Any
    status_code: int
    attempts: int
    duration_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """True se ``200 <= status_code < 300``."""
        return 200 <= self.status_code < 300


# ---------------------------------------------------------------------------
# Connector (ABC)
# ---------------------------------------------------------------------------


class Connector(abc.ABC):
    """ABC de execucao (NAO e porta de dominio — CONN-05).

    Pre-condicoes:
        - ``config`` e valida (CFG-01..CFG-06).
    Pos-condicoes:
        - ``send()`` retorna ``ConnectorResponse`` ou levanta excecao tipada.
    Invariantes:
        - Retry/timeout vivem no Template Method, nunca nas subclasses.
        - Nenhuma chamada de logger/metrics/arquivo (OBS-01).
        - Nao herda de ``*Port`` (CONN-05).

    Attributes:
        protocol: Identificador do protocolo (``http``/``webhook``/``bolt``).
        error_class: Classe de excecao a levantar em falha de transporte.
    """

    protocol: str = ""
    error_class: type[FetcherError] | type[IngestorError] = FetcherError

    def __init__(self, config: ConnectorConfig | None = None) -> None:
        self._config = config or ConnectorConfig()

    @property
    def config(self) -> ConnectorConfig:
        """Configuracao imutavel vigente (somente leitura)."""
        return self._config

    def send(
        self, payload: Any, context: dict[str, Any] | None = None
    ) -> ConnectorResponse:
        """Envia payload com retry e timeout (Template Method).

        Args:
            payload: Corpo a transportar (dict/list/str/None).
            context: Metadados de execucao (execution_id, stage_id) apenas
                para enriquecer o contexto da excecao.

        Returns:
            ConnectorResponse imutavel com attempts e duration_seconds.

        Raises:
            FetcherError: Falha de rede/timeout em HTTPConnector.
            IngestorError: Falha de rede/timeout em Bolt/Webhook.
            ConfigurationError: Configuracao invalida (CFG-01..CFG-06).
        """
        ctx: dict[str, Any] = dict(context) if context else {}
        retry = self._config.retry
        timeout = self._config.timeout_seconds
        start = time.monotonic()
        last_exc: BaseException | None = None
        last_status: int | None = None

        for attempt in range(1, retry.max_attempts + 1):
            try:
                result = self._dispatch(payload, timeout)
                last_status = result.status_code
                if 200 <= result.status_code < 300:
                    duration = time.monotonic() - start
                    return ConnectorResponse(
                        payload=result.body,
                        status_code=result.status_code,
                        attempts=attempt,
                        duration_seconds=duration,
                        metadata={
                            "protocol": self.protocol,
                            "endpoint": self._endpoint(),
                            "attempts": attempt,
                            "duration_seconds": duration,
                        },
                    )
                # Status nao-2xx: decidir retry ou falha imediata.
                if not retry.should_retry(result.status_code, attempt):
                    # 4xx nao-retryable (exceto 408/429) -> falha imediata.
                    duration = time.monotonic() - start
                    raise self.error_class(
                        f"{self.__class__.__name__} falhou com status "
                        f"{result.status_code}",
                        context=self._failure_context(
                            attempt=attempt,
                            duration=duration,
                            status=result.status_code,
                            retryable=False,
                            extra=ctx,
                        ),
                    )
                # Retryable: aguardar e tentar novamente.
                delay = self._compute_delay(result.headers, attempt, retry)
                time.sleep(delay)
                last_exc = None
            except self.error_class:
                raise
            except Exception as exc:  # noqa: BLE001 - transporte generico
                last_exc = exc
                if not retry.should_retry(None, attempt):
                    duration = time.monotonic() - start
                    raise self.error_class(
                        f"{self.__class__.__name__} falhou apos "
                        f"{attempt} tentativa(s)",
                        context=self._failure_context(
                            attempt=attempt,
                            duration=duration,
                            status=last_status,
                            retryable=False,
                            extra=ctx,
                        ),
                        cause=exc,
                    ) from exc
                delay = retry.delay_for(attempt)
                time.sleep(delay)

        # Esgotou tentativas (CONN-01: falha explicita, sem fallback).
        duration = time.monotonic() - start
        raise self.error_class(
            f"{self.__class__.__name__} falhou apos "
            f"{retry.max_attempts} tentativa(s)",
            context=self._failure_context(
                attempt=retry.max_attempts,
                duration=duration,
                status=last_status,
                retryable=True,
                extra=ctx,
            ),
            cause=last_exc,
        )

    def _compute_delay(
        self,
        headers: dict[str, str],
        attempt: int,
        retry: RetryPolicy,
    ) -> float:
        """Calcula atraso respeitando Retry-After (CONN-03).

        Args:
            headers: Headers da resposta (Retry-After numerico tem precedencia).
            attempt: Tentativa ja executada.
            retry: Politica de retry.

        Returns:
            Atraso em segundos.
        """
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if retry_after is not None:
            try:
                return min(float(retry_after), retry.max_delay)
            except (TypeError, ValueError):
                pass
        return retry.delay_for(attempt)

    def _failure_context(
        self,
        *,
        attempt: int,
        duration: float,
        status: int | None,
        retryable: bool,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        """Constroi o contexto de falha (Regra de Ouro: excecao = veiculo).

        Args:
            attempt: Tentativa executada.
            duration: Duracao total (s).
            status: Ultimo status HTTP (None se excecao de rede).
            retryable: Se a falha era retryavel.
            extra: Metadados adicionais do caller.

        Returns:
            Dicionario de contexto com segredos redigidos (SEC-01).
        """
        base: dict[str, Any] = {
            "connector": self.__class__.__name__,
            "protocol": self.protocol,
            "endpoint": self._endpoint(),
            "attempts": attempt,
            "timeout_seconds": self._config.timeout_seconds,
            "duration_seconds": duration,
            "retryable": retryable,
        }
        if status is not None:
            base["last_status"] = status
        base.update(_redact(extra))
        return base

    @abc.abstractmethod
    def _endpoint(self) -> str:
        """Retorna o endpoint do conector (para diagnostico)."""
        ...

    @abc.abstractmethod
    def _dispatch(self, payload: Any, timeout: float) -> TransportResult:
        """Executa UMA chamada de transporte, sem retry (CONN-04).

        Args:
            payload: Corpo a transportar.
            timeout: Timeout em segundos (deve ser repassado ao transporte).

        Returns:
            TransportResult com status_code, body e headers.
        """
        ...

    @abc.abstractmethod
    def validate_config(self, config: dict[str, Any]) -> bool:
        """Valida configuracao declarativa do bloco ``connectors``.

        Args:
            config: Dict com chaves especificas do protocolo.

        Returns:
            True se a configuracao e valida.

        Raises:
            ConfigurationError: Se a estrutura for irremediavelmente invalida.
        """
        ...

    @abc.abstractmethod
    def metadados(self) -> dict[str, Any]:
        """Metadados do conector, com segredos redigidos (SEC-01).

        Returns:
            Dicionario com metadados (nome, versao, endpoint, ...).
        """
        ...

    def close(self) -> None:
        """Libera recursos (Session/driver). Idempotente."""
        return None


# ---------------------------------------------------------------------------
# HTTPConnector
# ---------------------------------------------------------------------------


class HTTPConnector(Connector):
    """Conector HTTP/HTTPS para APIs governamentais (v2, Secao 4.2.3).

    Pre-condicoes:
        - ``url`` e URI valida com esquema ``http`` ou ``https`` (CFG-05).
        - ``method`` em ``HTTP_METHODS`` (CFG-06).
    Pos-condicoes:
        - ``_dispatch`` realiza chamada HTTP via ``requests.Session``.
    Invariantes:
        - Falha de rede levanta ``FetcherError`` (CONN-04).
        - ``requests`` e importado lazily (CONN-06).

    Attributes:
        url: URL do endpoint.
        method: Verbo HTTP (default: ``GET``).
    """

    protocol = "http"
    error_class = FetcherError

    def __init__(
        self,
        url: str,
        method: str = "GET",
        config: ConnectorConfig | None = None,
    ) -> None:
        super().__init__(config)
        _validate_scheme(url, HTTP_SCHEMES, "CFG-05")
        method_upper = method.upper()
        if method_upper not in HTTP_METHODS:
            raise ConfigurationError(
                f"HTTPConnector.method invalido: {method!r}",
                context={
                    "rule": "CFG-06",
                    "method": method,
                    "allowed": sorted(HTTP_METHODS),
                },
            )
        self._url = url
        self._method = method_upper
        self._session: Any | None = None

    @property
    def url(self) -> str:
        """URL do endpoint (somente leitura)."""
        return self._url

    @property
    def method(self) -> str:
        """Verbo HTTP (somente leitura)."""
        return self._method

    def _endpoint(self) -> str:
        return self._url

    def _get_session(self) -> Any:
        """Retorna (ou cria) a ``requests.Session`` lazily (CONN-06)."""
        if self._session is None:
            try:
                import requests  # noqa: WPS433 - import lazy
            except ImportError as exc:
                raise ConfigurationError(
                    "Dependencia 'requests' nao instalada",
                    context={"rule": "CONN-06", "dependency": "requests"},
                    cause=exc,
                ) from exc
            self._session = requests.Session()
            if self._config.headers:
                self._session.headers.update(self._config.headers)
        return self._session

    def _dispatch(self, payload: Any, timeout: float) -> TransportResult:
        """Executa UMA chamada HTTP (CONN-04).

        Args:
            payload: Corpo da requisicao (dict -> JSON; str -> body cru).
            timeout: Timeout em segundos (repassado ao ``requests``).

        Returns:
            TransportResult com status, body e headers.

        Raises:
            FetcherError: Em caso de excecao de transporte.
        """
        session = self._get_session()
        kwargs: dict[str, Any] = {"timeout": timeout, "verify": self._config.verify_tls}
        if payload is not None and self._method in {"POST", "PUT", "PATCH"}:
            if isinstance(payload, (dict, list)):
                kwargs["json"] = payload
            else:
                kwargs["data"] = payload
        try:
            response = session.request(self._method, self._url, **kwargs)
        except Exception as exc:  # noqa: BLE001 - requests levanta varias
            raise FetcherError(
                f"HTTPConnector falhou em {self._url}",
                context={
                    "url": self._url,
                    "method": self._method,
                    "timeout": timeout,
                },
                cause=exc,
            ) from exc
        headers = {k.lower(): v for k, v in response.headers.items()}
        try:
            body = response.json()
        except ValueError:
            body = response.text
        return TransportResult(
            status_code=response.status_code,
            body=body,
            headers=headers,
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Valida config declarativa do bloco ``connectors``.

        Args:
            config: Dict com ``url`` e opcionalmente ``method``.

        Returns:
            True se valido.
        """
        if "url" not in config:
            return False
        try:
            _validate_scheme(config["url"], HTTP_SCHEMES, "CFG-05")
        except ConfigurationError:
            return False
        method = config.get("method", "GET")
        return isinstance(method, str) and method.upper() in HTTP_METHODS

    def metadados(self) -> dict[str, Any]:
        """Metadados do conector, com segredos redigidos (SEC-01)."""
        return _redact(
            {
                "name": "HTTPConnector",
                "protocol": self.protocol,
                "url": self._url,
                "method": self._method,
                "timeout_seconds": self._config.timeout_seconds,
                "verify_tls": self._config.verify_tls,
                "headers": dict(self._config.headers),
            }
        )

    def close(self) -> None:
        """Libera a sessao HTTP. Idempotente."""
        if self._session is not None:
            try:
                self._session.close()
            finally:
                self._session = None


# ---------------------------------------------------------------------------
# WebhookConnector
# ---------------------------------------------------------------------------


class WebhookConnector(Connector):
    """Conector de notificacao (n8n/alertas); POST JSON, assinatura HMAC.

    Pre-condicoes:
        - ``url`` e URI valida com esquema ``http`` ou ``https`` (CFG-05).
    Pos-condicoes:
        - ``_dispatch`` realiza POST JSON com header ``X-MCA-Signature``
          (HMAC-SHA256 do corpo) quando ``secret`` e fornecido.
    Invariantes:
        - Sempre POST (CFG-06).
        - Falha levanta ``IngestorError``.

    Attributes:
        url: URL do webhook.
        secret: Segredo para assinatura HMAC (opcional).
    """

    protocol = "webhook"
    error_class = IngestorError

    def __init__(
        self,
        url: str,
        secret: str | None = None,
        config: ConnectorConfig | None = None,
    ) -> None:
        super().__init__(config)
        _validate_scheme(url, HTTP_SCHEMES, "CFG-05")
        self._url = url
        self._secret = secret
        self._session: Any | None = None

    @property
    def url(self) -> str:
        """URL do webhook (somente leitura)."""
        return self._url

    def _endpoint(self) -> str:
        return self._url

    def _sign(self, body: bytes) -> str:
        """Calcula HMAC-SHA256 do corpo (quando ``secret`` e fornecido).

        Args:
            body: Corpo da requisicao em bytes.

        Returns:
            Assinatura hexadecimal.
        """
        if not self._secret:
            return ""
        return hmac.new(
            self._secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()

    def _get_session(self) -> Any:
        """Retorna (ou cria) a ``requests.Session`` lazily (CONN-06)."""
        if self._session is None:
            try:
                import requests  # noqa: WPS433 - import lazy
            except ImportError as exc:
                raise ConfigurationError(
                    "Dependencia 'requests' nao instalada",
                    context={"rule": "CONN-06", "dependency": "requests"},
                    cause=exc,
                ) from exc
            self._session = requests.Session()
            headers = {"Content-Type": "application/json"}
            headers.update(self._config.headers)
            self._session.headers.update(headers)
        return self._session

    def _dispatch(self, payload: Any, timeout: float) -> TransportResult:
        """Executa UMA chamada POST JSON (CONN-04).

        Args:
            payload: Corpo a serializar como JSON.
            timeout: Timeout em segundos.

        Returns:
            TransportResult com status, body e headers.
        """
        session = self._get_session()
        body_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        headers: dict[str, str] = {}
        signature = self._sign(body_bytes)
        if signature:
            headers["X-MCA-Signature"] = signature
        try:
            response = session.post(
                self._url,
                data=body_bytes,
                headers=headers,
                timeout=timeout,
                verify=self._config.verify_tls,
            )
        except Exception as exc:  # noqa: BLE001
            raise IngestorError(
                f"WebhookConnector falhou em {self._url}",
                context={"url": self._url, "timeout": timeout},
                cause=exc,
            ) from exc
        resp_headers = {k.lower(): v for k, v in response.headers.items()}
        try:
            body = response.json()
        except ValueError:
            body = response.text
        return TransportResult(
            status_code=response.status_code,
            body=body,
            headers=resp_headers,
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Valida config declarativa do bloco ``connectors``."""
        if "url" not in config:
            return False
        try:
            _validate_scheme(config["url"], HTTP_SCHEMES, "CFG-05")
        except ConfigurationError:
            return False
        return True

    def metadados(self) -> dict[str, Any]:
        """Metadados do conector, com segredos redigidos (SEC-01)."""
        return _redact(
            {
                "name": "WebhookConnector",
                "protocol": self.protocol,
                "url": self._url,
                "secret": self._secret,
                "timeout_seconds": self._config.timeout_seconds,
                "verify_tls": self._config.verify_tls,
            }
        )

    def close(self) -> None:
        """Libera a sessao HTTP. Idempotente."""
        if self._session is not None:
            try:
                self._session.close()
            finally:
                self._session = None


# ---------------------------------------------------------------------------
# BoltConnector
# ---------------------------------------------------------------------------


class BoltConnector(Connector):
    """Conector Bolt/Neo4j; driver importado lazily (CONN-06).

    Pre-condicoes:
        - ``uri`` e URI valida com esquema em ``BOLT_SCHEMES`` (CFG-05).
    Pos-condicoes:
        - ``_dispatch`` executa query Cypher via driver Neo4j.
    Invariantes:
        - Driver e driver.session() sao criados lazily.
        - Falha levanta ``IngestorError``.

    Attributes:
        uri: URI de conexao (``bolt://...``, ``neo4j://...``).
        user: Usuario (opcional).
        password: Senha (opcional; redigida em ``metadados()``).
        database: Nome do banco (default: ``neo4j``).
    """

    protocol = "bolt"
    error_class = IngestorError

    def __init__(
        self,
        uri: str,
        user: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
        config: ConnectorConfig | None = None,
    ) -> None:
        super().__init__(config)
        _validate_scheme(uri, BOLT_SCHEMES, "CFG-05")
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver: Any | None = None

    @property
    def uri(self) -> str:
        """URI de conexao (somente leitura)."""
        return self._uri

    @property
    def database(self) -> str:
        """Nome do banco (somente leitura)."""
        return self._database

    def _endpoint(self) -> str:
        return f"{self._uri}/{self._database}"

    def _get_driver(self) -> Any:
        """Retorna (ou cria) o driver Neo4j lazily (CONN-06)."""
        if self._driver is None:
            try:
                from neo4j import GraphDatabase  # noqa: WPS433 - import lazy
            except ImportError as exc:
                raise ConfigurationError(
                    "Dependencia 'neo4j' nao instalada",
                    context={"rule": "CONN-06", "dependency": "neo4j"},
                    cause=exc,
                ) from exc
            auth = (
                (self._user, self._password)
                if self._user and self._password
                else None
            )
            self._driver = GraphDatabase.driver(self._uri, auth=auth)
        return self._driver

    def _dispatch(self, payload: Any, timeout: float) -> TransportResult:
        """Executa UMA query Cypher (CONN-04).

        Args:
            payload: Dict com ``query`` (str) e opcionalmente ``parameters``.
            timeout: Timeout em segundos (repassado ao session).

        Returns:
            TransportResult com status 200 (sucesso) ou 503 (falha).
        """
        if not isinstance(payload, dict) or "query" not in payload:
            raise IngestorError(
                "BoltConnector requer payload com 'query'",
                context={"rule": "CONN-04", "payload_type": type(payload).__name__},
            )
        driver = self._get_driver()
        query = payload["query"]
        parameters = payload.get("parameters") or {}
        try:
            with driver.session(database=self._database) as session:
                result = session.run(query, parameters)
                records = [dict(record) for record in result]
            return TransportResult(status_code=200, body=records, headers={})
        except Exception as exc:  # noqa: BLE001
            raise IngestorError(
                f"BoltConnector falhou em {self._uri}",
                context={
                    "uri": self._uri,
                    "database": self._database,
                    "timeout": timeout,
                },
                cause=exc,
            ) from exc

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Valida config declarativa do bloco ``connectors``."""
        if "uri" not in config:
            return False
        try:
            _validate_scheme(config["uri"], BOLT_SCHEMES, "CFG-05")
        except ConfigurationError:
            return False
        return True

    def metadados(self) -> dict[str, Any]:
        """Metadados do conector, com segredos redigidos (SEC-01)."""
        return _redact(
            {
                "name": "BoltConnector",
                "protocol": self.protocol,
                "uri": self._uri,
                "user": self._user,
                "password": self._password,
                "database": self._database,
                "timeout_seconds": self._config.timeout_seconds,
            }
        )

    def close(self) -> None:
        """Libera o driver Neo4j. Idempotente."""
        if self._driver is not None:
            try:
                self._driver.close()
            finally:
                self._driver = None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_connector(spec: dict[str, Any]) -> Connector:
    """Fabrica a partir do bloco ``connectors`` da App DAG (ID 1.4).

    Args:
        spec: Dict com ``protocol``, ``config`` (timeout_seconds,
            retry_policy, url/uri, method, secret, user, password, database).

    Returns:
        Instancia de Connector correspondente ao protocolo.

    Raises:
        ConfigurationError: Protocolo desconhecido (CFG-05) ou chave
            obrigatoria ausente.
    """
    if not isinstance(spec, dict):
        raise ConfigurationError(
            "build_connector espera dict",
            context={"rule": "CFG-05", "spec_type": type(spec).__name__},
        )
    protocol = spec.get("protocol")
    if not isinstance(protocol, str):
        raise ConfigurationError(
            "build_connector: 'protocol' obrigatorio",
            context={"rule": "CFG-05"},
        )
    config_dict = spec.get("config") or {}
    retry_dict = config_dict.get("retry_policy") or {}
    retry = RetryPolicy(
        max_attempts=retry_dict.get("max_attempts", 3),
        backoff=retry_dict.get("backoff", "exponential"),
        initial_delay=retry_dict.get("initial_delay", 1.0),
        max_delay=retry_dict.get("max_delay", 30.0),
        multiplier=retry_dict.get("multiplier", 2.0),
    )
    connector_config = ConnectorConfig(
        timeout_seconds=config_dict.get("timeout_seconds", 30.0),
        retry=retry,
        headers=config_dict.get("headers") or {},
        verify_tls=config_dict.get("verify_tls", True),
    )
    protocol_lower = protocol.lower()
    if protocol_lower == "http":
        if "url" not in config_dict:
            raise ConfigurationError(
                "HTTPConnector requer 'url' em config",
                context={"rule": "CFG-05", "protocol": protocol},
            )
        return HTTPConnector(
            url=config_dict["url"],
            method=config_dict.get("method", "GET"),
            config=connector_config,
        )
    if protocol_lower == "webhook":
        if "url" not in config_dict:
            raise ConfigurationError(
                "WebhookConnector requer 'url' em config",
                context={"rule": "CFG-05", "protocol": protocol},
            )
        return WebhookConnector(
            url=config_dict["url"],
            secret=config_dict.get("secret"),
            config=connector_config,
        )
    if protocol_lower == "bolt":
        if "uri" not in config_dict:
            raise ConfigurationError(
                "BoltConnector requer 'uri' em config",
                context={"rule": "CFG-05", "protocol": protocol},
            )
        return BoltConnector(
            uri=config_dict["uri"],
            user=config_dict.get("user"),
            password=config_dict.get("password"),
            database=config_dict.get("database", "neo4j"),
            config=connector_config,
        )
    raise ConfigurationError(
        f"Protocolo desconhecido: {protocol!r}",
        context={"rule": "CFG-05", "protocol": protocol},
    )