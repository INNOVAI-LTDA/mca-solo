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
RETRYABLE_STATUS: Final[frozenset[int]] = frozenset({408, 425, 429, 500, 502, 503, 504})

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
    """Retorna copia com valores de chaves sensíveis redigidos (recursiva).

    Implementa SEC-01: ``password``, ``authorization``, ``secret``,
    ``api_key`` e ``token`` sao substituidos por ``"***"``.
    A funcao e recursiva para dicionarios, garantindo que chaves
    sensiveis em niveis aninhados (ex.: ``headers``) tambem sejam redigidas.

    Args:
        mapping: Dicionario a redigir.

    Returns:
        Novo dicionario com segredos redigidos.
    """
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        if isinstance(key, str) and key.lower() in REDACTED_KEYS:
            out[key] = "***"
        elif isinstance(value, dict):
            out[key] = _redact(value)
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
    """Politica de repeticao deterministica e imutavel (v2, Secao 4.2.4)."""

    max_attempts: int = 3
    backoff: str = "exponential"
    initial_delay: float = 1.0
    max_delay: float = 30.0
    multiplier: float = 2.0
    retryable_status: frozenset[int] = RETRYABLE_STATUS

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int) or self.max_attempts < 1:
            raise ConfigurationError(
                "RetryPolicy.max_attempts deve ser int >= 1",
                context={"rule": "CFG-02", "max_attempts": self.max_attempts},
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
        if not isinstance(self.initial_delay, (int, float)) or self.initial_delay < 0:
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
        if not isinstance(self.multiplier, (int, float)) or self.multiplier < 1.0:
            raise ConfigurationError(
                "RetryPolicy.multiplier deve ser >= 1.0",
                context={"rule": "CFG-04", "multiplier": self.multiplier},
            )

    def delay_for(self, attempt: int) -> float:
        if not isinstance(attempt, int) or attempt < 1:
            raise ConfigurationError(
                "delay_for(attempt) exige attempt >= 1",
                context={"rule": "CFG-02", "attempt": attempt},
            )
        if self.backoff == "fixed":
            delay = self.initial_delay
        elif self.backoff == "linear":
            delay = self.initial_delay * attempt
        else:
            delay = self.initial_delay * (self.multiplier ** (attempt - 1))
        return min(delay, self.max_delay)

    def should_retry(self, status_code: int | None, attempt: int) -> bool:
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
    """Configuracao imutavel de transporte (timeout + retry + headers)."""

    timeout_seconds: float = 30.0
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    headers: dict[str, str] = field(default_factory=dict)
    verify_tls: bool = True

    def __post_init__(self) -> None:
        if (
            not isinstance(self.timeout_seconds, (int, float))
            or self.timeout_seconds <= 0
        ):
            raise ConfigurationError(
                "ConnectorConfig.timeout_seconds deve ser > 0",
                context={"rule": "CFG-01", "timeout_seconds": self.timeout_seconds},
            )
        if isinstance(self.timeout_seconds, float) and (
            self.timeout_seconds != self.timeout_seconds
            or self.timeout_seconds == float("inf")
        ):
            raise ConfigurationError(
                "ConnectorConfig.timeout_seconds deve ser finito",
                context={"rule": "CFG-01", "timeout_seconds": self.timeout_seconds},
            )
        object.__setattr__(self, "headers", dict(self.headers))


# ---------------------------------------------------------------------------
# TransportResult / ConnectorResponse
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransportResult:
    """Resposta bruta normalizada, protocolo-agnostica."""

    status_code: int
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorResponse:
    """Snapshot imutavel do resultado, com proveniencia de transporte."""

    payload: Any
    status_code: int
    attempts: int
    duration_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


# ---------------------------------------------------------------------------
# Connector (ABC)
# ---------------------------------------------------------------------------


class Connector(abc.ABC):
    """ABC de execucao (NAO e porta de dominio — CONN-05)."""

    protocol: str = ""
    error_class: type[FetcherError] | type[IngestorError] = FetcherError

    def __init__(self, config: ConnectorConfig | None = None) -> None:
        self._config = config or ConnectorConfig()

    @property
    def config(self) -> ConnectorConfig:
        return self._config

    def send(
        self, payload: Any, context: dict[str, Any] | None = None
    ) -> ConnectorResponse:
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
                if not retry.should_retry(result.status_code, attempt):
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
                delay = self._compute_delay(result.headers, attempt, retry)
                time.sleep(delay)
                last_exc = None
            except self.error_class:
                raise
            except Exception as exc:
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
        self, headers: dict[str, str], attempt: int, retry: RetryPolicy
    ) -> float:
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
    def _endpoint(self) -> str: ...

    @abc.abstractmethod
    def _dispatch(self, payload: Any, timeout: float) -> TransportResult: ...

    @abc.abstractmethod
    def validate_config(self, config: dict[str, Any]) -> bool: ...

    @abc.abstractmethod
    def metadados(self) -> dict[str, Any]: ...

    def close(self) -> None:
        return None


# ---------------------------------------------------------------------------
# HTTPConnector
# ---------------------------------------------------------------------------


class HTTPConnector(Connector):
    """Conector HTTP/HTTPS para APIs governamentais (v2, Secao 4.2.3)."""

    protocol = "http"
    error_class = FetcherError

    def __init__(
        self, url: str, method: str = "GET", config: ConnectorConfig | None = None
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
        return self._url

    @property
    def method(self) -> str:
        return self._method

    def _endpoint(self) -> str:
        return self._url

    def _get_session(self) -> Any:
        if self._session is None:
            try:
                import requests  # noqa: WPS433
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
        session = self._get_session()
        kwargs: dict[str, Any] = {
            "timeout": timeout,
            "verify": self._config.verify_tls,
        }
        if payload is not None and self._method in {"POST", "PUT", "PATCH"}:
            if isinstance(payload, (dict, list)):
                kwargs["json"] = payload
            else:
                kwargs["data"] = payload
        try:
            response = session.request(self._method, self._url, **kwargs)
        except Exception as exc:
            raise RuntimeError(f"HTTP falhou em {self._url}") from exc

        headers = {k.lower(): v for k, v in response.headers.items()}
        try:
            body = response.json()
        except ValueError:
            body = response.text
        return TransportResult(
            status_code=response.status_code, body=body, headers=headers
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        if "url" not in config:
            return False
        try:
            _validate_scheme(config["url"], HTTP_SCHEMES, "CFG-05")
        except ConfigurationError:
            return False
        method = config.get("method", "GET")
        return isinstance(method, str) and method.upper() in HTTP_METHODS

    def metadados(self) -> dict[str, Any]:
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
        if self._session is not None:
            try:
                self._session.close()
            finally:
                self._session = None


# ---------------------------------------------------------------------------
# WebhookConnector
# ---------------------------------------------------------------------------


class WebhookConnector(Connector):
    """Conector de notificacao (n8n/alertas); POST JSON, assinatura HMAC."""

    protocol = "webhook"
    error_class = IngestorError

    def __init__(
        self, url: str, secret: str | None = None, config: ConnectorConfig | None = None
    ) -> None:
        super().__init__(config)
        _validate_scheme(url, HTTP_SCHEMES, "CFG-05")
        self._url = url
        self._secret = secret
        self._session: Any | None = None

    @property
    def url(self) -> str:
        return self._url

    def _endpoint(self) -> str:
        return self._url

    def _sign(self, body: bytes) -> str:
        if not self._secret:
            return ""
        return hmac.new(self._secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    def _get_session(self) -> Any:
        if self._session is None:
            try:
                import requests  # noqa: WPS433
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
        except Exception as exc:
            raise RuntimeError(f"Webhook falhou em {self._url}") from exc

        resp_headers = {k.lower(): v for k, v in response.headers.items()}
        try:
            body = response.json()
        except ValueError:
            body = response.text
        return TransportResult(
            status_code=response.status_code, body=body, headers=resp_headers
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        if "url" not in config:
            return False
        try:
            _validate_scheme(config["url"], HTTP_SCHEMES, "CFG-05")
        except ConfigurationError:
            return False
        return True

    def metadados(self) -> dict[str, Any]:
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
        if self._session is not None:
            try:
                self._session.close()
            finally:
                self._session = None


# ---------------------------------------------------------------------------
# BoltConnector
# ---------------------------------------------------------------------------


class BoltConnector(Connector):
    """Conector Bolt/Neo4j; driver importado lazily (CONN-06)."""

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
        return self._uri

    @property
    def database(self) -> str:
        return self._database

    def _endpoint(self) -> str:
        return f"{self._uri}/{self._database}"

    def _get_driver(self) -> Any:
        if self._driver is None:
            try:
                from neo4j import GraphDatabase  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ConfigurationError(
                    "Dependencia 'neo4j' nao instalada",
                    context={"rule": "CONN-06", "dependency": "neo4j"},
                    cause=exc,
                ) from exc
            auth = (
                (self._user, self._password) if self._user and self._password else None
            )
            self._driver = GraphDatabase.driver(self._uri, auth=auth)
        return self._driver

    def _dispatch(self, payload: Any, timeout: float) -> TransportResult:
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
        except Exception as exc:
            raise RuntimeError(f"Bolt falhou em {self._uri}") from exc

    def validate_config(self, config: dict[str, Any]) -> bool:
        if "uri" not in config:
            return False
        try:
            _validate_scheme(config["uri"], BOLT_SCHEMES, "CFG-05")
        except ConfigurationError:
            return False
        return True

    def metadados(self) -> dict[str, Any]:
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
        if self._driver is not None:
            try:
                self._driver.close()
            finally:
                self._driver = None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_connector(spec: dict[str, Any]) -> Connector:
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
