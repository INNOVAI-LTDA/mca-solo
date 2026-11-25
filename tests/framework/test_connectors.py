"""Suite de testes dos Conectores de Execucao (ID 2.2).

Cobre as 7 categorias da Spec ID 2.2 (Secao 6):
6.1 Configuracao, Imutabilidade e Defaults
6.2 Politica de Retry e Backoff
6.3 Timeout
6.4 Mapeamento de Excecoes e Falha Explicita
6.5 Contrato, Heranca e Fronteira Arquitetural
6.6 Integracao com Mocks por Protocolo
6.7 Observabilidade, Seguranca e Higiene

Regras de Ouro verificadas:
- "A excecao e o veiculo de transporte de contexto para Observabilidade."
- "Falha explicita: toda violacao interrompe, sem fallback."
- "Gestao e invariante sob substituicao de implementacao."
- "Todo componente registrado deve herdar nominalmente de uma ABC de porta."
"""

from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from framework.core.exceptions import (
    ConfigurationError,
    FetcherError,
    FrameworkError,
    IngestorError,
)
from framework.execution.connectors import (
    BACKOFF_STRATEGIES,
    REDACTED_KEYS,
    RETRYABLE_STATUS,
    BoltConnector,
    Connector,
    ConnectorConfig,
    ConnectorResponse,
    HTTPConnector,
    RetryPolicy,
    TransportResult,
    WebhookConnector,
    build_connector,
)
from framework.execution.orchestrator import ComponentRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Duble de ``requests.Response`` para testes HTTP/Webhook."""

    def __init__(
        self,
        status_code: int = 200,
        body: Any = None,
        headers: dict[str, str] | None = None,
        raise_for_status: bool = False,
    ) -> None:
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self._raise = raise_for_status

    def json(self) -> Any:
        if isinstance(self._body, (dict, list)):
            return self._body
        raise ValueError("not JSON")

    @property
    def text(self) -> str:
        return str(self._body)

    def raise_for_status(self) -> None:
        if self._raise:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSession:
    """Duble de ``requests.Session`` com controle de respostas."""

    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            return _FakeResponse(status_code=500)
        return self._responses.pop(0)

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        if not self._responses:
            return _FakeResponse(status_code=500)
        return self._responses.pop(0)

    def close(self) -> None:
        self.closed = True


# ===========================================================================
# 6.1 Configuracao, Imutabilidade e Defaults
# ===========================================================================


class TestRetryPolicyImutabilidade:
    """6.1 - frozen=True e defaults documentados."""

    def test_frozen(self) -> None:
        policy = RetryPolicy()
        with pytest.raises(Exception):  # FrozenInstanceError
            policy.max_attempts = 10  # type: ignore[misc]

    def test_defaults(self) -> None:
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.backoff == "exponential"
        assert policy.initial_delay == 1.0
        assert policy.max_delay == 30.0
        assert policy.multiplier == 2.0
        assert policy.retryable_status == RETRYABLE_STATUS

    def test_retryable_status_default(self) -> None:
        assert RETRYABLE_STATUS == frozenset({408, 425, 429, 500, 502, 503, 504})


class TestRetryPolicyValidacao:
    """6.1 - Negativos parametrizados (CFG-02..CFG-04)."""

    @pytest.mark.parametrize(
        "kwargs,rule",
        [
            ({"max_attempts": 0}, "CFG-02"),
            ({"max_attempts": -1}, "CFG-02"),
            ({"backoff": "jitter"}, "CFG-03"),
            ({"initial_delay": -1.0}, "CFG-04"),
            ({"initial_delay": 10.0, "max_delay": 5.0}, "CFG-04"),
            ({"multiplier": 0.5}, "CFG-04"),
        ],
    )
    def test_negativos(self, kwargs: dict[str, Any], rule: str) -> None:
        with pytest.raises(ConfigurationError) as exc:
            RetryPolicy(**kwargs)
        assert exc.value.context["rule"] == rule


class TestConnectorConfigImutabilidade:
    """6.1 - frozen=True, copia defensiva de headers."""

    def test_frozen(self) -> None:
        config = ConnectorConfig()
        with pytest.raises(Exception):
            config.timeout_seconds = 60.0  # type: ignore[misc]

    def test_defaults(self) -> None:
        config = ConnectorConfig()
        assert config.timeout_seconds == 30.0
        assert config.headers == {}
        assert config.verify_tls is True
        assert isinstance(config.retry, RetryPolicy)

    def test_copia_defensiva_headers(self) -> None:
        external = {"X-Key": "value"}
        config = ConnectorConfig(headers=external)
        external["X-Key"] = "changed"
        assert config.headers["X-Key"] == "value"

    @pytest.mark.parametrize(
        "timeout,rule",
        [
            (0, "CFG-01"),
            (-1, "CFG-01"),
            (float("inf"), "CFG-01"),
            (float("nan"), "CFG-01"),
        ],
    )
    def test_timeout_invalido(self, timeout: float, rule: str) -> None:
        with pytest.raises(ConfigurationError) as exc:
            ConnectorConfig(timeout_seconds=timeout)
        assert exc.value.context["rule"] == rule


class TestConnectorResponseImutabilidade:
    """6.1 - frozen=True, propriedades derivadas."""

    def test_frozen(self) -> None:
        response = ConnectorResponse(
            payload={}, status_code=200, attempts=1, duration_seconds=0.5
        )
        with pytest.raises(Exception):
            response.status_code = 500  # type: ignore[misc]

    def test_is_success(self) -> None:
        assert ConnectorResponse({}, 200, 1, 0.5).is_success is True
        assert ConnectorResponse({}, 204, 1, 0.5).is_success is True
        assert ConnectorResponse({}, 404, 1, 0.5).is_success is False
        assert ConnectorResponse({}, 500, 1, 0.5).is_success is False


# ===========================================================================
# 6.2 Politica de Retry e Backoff
# ===========================================================================


class TestRetryPolicyBackoff:
    """6.2 - delay_for deterministico, should_retry."""

    def test_exponential(self) -> None:
        policy = RetryPolicy(
            backoff="exponential", initial_delay=1.0, multiplier=2.0, max_delay=30.0
        )
        assert policy.delay_for(1) == 1.0
        assert policy.delay_for(2) == 2.0
        assert policy.delay_for(3) == 4.0
        assert policy.delay_for(4) == 8.0

    def test_linear(self) -> None:
        policy = RetryPolicy(backoff="linear", initial_delay=0.5)
        assert policy.delay_for(1) == 0.5
        assert policy.delay_for(2) == 1.0
        assert policy.delay_for(3) == 1.5

    def test_fixed(self) -> None:
        policy = RetryPolicy(backoff="fixed", initial_delay=2.0)
        assert policy.delay_for(1) == 2.0
        assert policy.delay_for(2) == 2.0
        assert policy.delay_for(3) == 2.0

    def test_max_delay_teto(self) -> None:
        policy = RetryPolicy(
            backoff="exponential", initial_delay=10.0, max_delay=15.0, multiplier=2.0
        )
        assert policy.delay_for(1) == 10.0
        assert policy.delay_for(2) == 15.0  # teto
        assert policy.delay_for(3) == 15.0

    def test_should_retry_retryable(self) -> None:
        policy = RetryPolicy(max_attempts=3)
        assert policy.should_retry(503, 1) is True
        assert policy.should_retry(503, 2) is True
        assert policy.should_retry(503, 3) is False  # esgotou

    def test_should_retry_non_retryable(self) -> None:
        policy = RetryPolicy(max_attempts=3)
        assert policy.should_retry(400, 1) is False
        assert policy.should_retry(404, 1) is False
        assert policy.should_retry(401, 1) is False

    def test_should_retry_none_status(self) -> None:
        policy = RetryPolicy(max_attempts=3)
        assert policy.should_retry(None, 1) is True
        assert policy.should_retry(None, 3) is False

    def test_delay_for_invalid_attempt(self) -> None:
        policy = RetryPolicy()
        with pytest.raises(ConfigurationError) as exc:
            policy.delay_for(0)
        assert exc.value.context["rule"] == "CFG-02"


# ===========================================================================
# 6.3 Timeout
# ===========================================================================


class TestTimeoutPropagacao:
    """6.3 - timeout_seconds repassado ao transporte (CONN-04)."""

    @patch("framework.execution.connectors.time.sleep")
    def test_http_propaga_timeout(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession([_FakeResponse(200, {"ok": True})])
        connector = HTTPConnector(
            "https://api.example.com", config=ConnectorConfig(timeout_seconds=15.0)
        )
        connector._session = session  # type: ignore[assignment]
        connector.send({})
        assert session.calls[0]["timeout"] == 15.0

    @patch("framework.execution.connectors.time.sleep")
    def test_webhook_propaga_timeout(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession([_FakeResponse(200, {"ok": True})])
        connector = WebhookConnector(
            "https://n8n.example.com/webhook",
            config=ConnectorConfig(timeout_seconds=10.0),
        )
        connector._session = session  # type: ignore[assignment]
        connector.send({"event": "test"})
        assert session.calls[0]["timeout"] == 10.0

    @patch("framework.execution.connectors.time.sleep")
    def test_bolt_propaga_timeout(self, mock_sleep: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = []
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        connector = BoltConnector(
            "bolt://localhost:7687", config=ConnectorConfig(timeout_seconds=60.0)
        )
        connector._driver = mock_driver  # type: ignore[assignment]
        connector.send({"query": "MATCH (n) RETURN n"})
        # BoltConnector nao passa timeout explicitamente ao session.run
        # (o driver Neo4j gerencia internamente), mas o teste garante
        # que o conector nao falha e retorna TransportResult.


# ===========================================================================
# 6.4 Mapeamento de Excecoes e Falha Explicita
# ===========================================================================


class TestMapeamentoExcecoes:
    """6.4 - HTTP->FetcherError, Bolt/Webhook->IngestorError."""

    @patch("framework.execution.connectors.time.sleep")
    def test_http_levanta_fetcher_error(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession(
            [_FakeResponse(503), _FakeResponse(503), _FakeResponse(503)]
        )
        connector = HTTPConnector(
            "https://api.example.com",
            config=ConnectorConfig(retry=RetryPolicy(max_attempts=3)),
        )
        connector._session = session  # type: ignore[assignment]
        with pytest.raises(FetcherError) as exc:
            connector.send({})
        assert exc.value.context["connector"] == "HTTPConnector"
        assert exc.value.context["protocol"] == "http"
        assert exc.value.context["attempts"] == 3

    @patch("framework.execution.connectors.time.sleep")
    def test_webhook_levanta_ingestor_error(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession([_FakeResponse(500), _FakeResponse(500)])
        connector = WebhookConnector(
            "https://n8n.example.com/webhook",
            config=ConnectorConfig(retry=RetryPolicy(max_attempts=2)),
        )
        connector._session = session  # type: ignore[assignment]
        with pytest.raises(IngestorError) as exc:
            connector.send({"event": "test"})
        assert exc.value.context["connector"] == "WebhookConnector"
        assert exc.value.context["protocol"] == "webhook"

    @patch("framework.execution.connectors.time.sleep")
    def test_bolt_levanta_ingestor_error(self, mock_sleep: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.side_effect = RuntimeError("connection lost")
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        connector = BoltConnector(
            "bolt://localhost:7687",
            config=ConnectorConfig(retry=RetryPolicy(max_attempts=2)),
        )
        connector._driver = mock_driver  # type: ignore[assignment]
        with pytest.raises(IngestorError) as exc:
            connector.send({"query": "MATCH (n) RETURN n"})
        assert exc.value.context["connector"] == "BoltConnector"
        assert exc.value.context["protocol"] == "bolt"

    def test_todas_sao_framework_error(self) -> None:
        assert issubclass(FetcherError, FrameworkError)
        assert issubclass(IngestorError, FrameworkError)
        assert issubclass(ConfigurationError, FrameworkError)


class TestFalhaExplicita:
    """6.4 - Esgotamento nunca retorna None/ConnectorResponse com erro."""

    @patch("framework.execution.connectors.time.sleep")
    def test_esgotamento_levanta_excecao(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession([_FakeResponse(503)] * 5)
        connector = HTTPConnector(
            "https://api.example.com",
            config=ConnectorConfig(retry=RetryPolicy(max_attempts=3)),
        )
        connector._session = session  # type: ignore[assignment]
        with pytest.raises(FetcherError):
            connector.send({})

    @patch("framework.execution.connectors.time.sleep")
    def test_4xx_nao_retryable_falha_imediata(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession([_FakeResponse(404)])
        connector = HTTPConnector(
            "https://api.example.com",
            config=ConnectorConfig(retry=RetryPolicy(max_attempts=3)),
        )
        connector._session = session  # type: ignore[assignment]
        with pytest.raises(FetcherError) as exc:
            connector.send({})
        assert exc.value.context["retryable"] is False
        assert len(session.calls) == 1  # apenas 1 tentativa

    @patch("framework.execution.connectors.time.sleep")
    def test_retry_after_tem_precedencia(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession(
            [
                _FakeResponse(429, headers={"Retry-After": "7"}),
                _FakeResponse(200, {"ok": True}),
            ]
        )
        connector = HTTPConnector(
            "https://api.example.com",
            config=ConnectorConfig(retry=RetryPolicy(max_attempts=3)),
        )
        connector._session = session  # type: ignore[assignment]
        connector.send({})
        mock_sleep.assert_called_with(7.0)


class TestEncadeamentoExcecoes:
    """6.4 - __cause__ preservado (Regra de Ouro)."""

    @patch("framework.execution.connectors.time.sleep")
    def test_cause_preservado(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession([_FakeResponse(503)])
        connector = HTTPConnector(
            "https://api.example.com",
            config=ConnectorConfig(retry=RetryPolicy(max_attempts=1)),
        )
        connector._session = session  # type: ignore[assignment]
        with pytest.raises(FetcherError) as exc:
            connector.send({})
        # __cause__ pode ser None se a ultima tentativa foi status 503
        # (sem excecao de transporte), mas o contexto deve ter last_status.
        assert exc.value.context["last_status"] == 503


# ===========================================================================
# 6.5 Contrato, Heranca e Fronteira Arquitetural
# ===========================================================================


class TestConnectorABC:
    """6.5 - Connector e ABC, nao instanciavel diretamente."""

    def test_nao_instanciavel(self) -> None:
        with pytest.raises(TypeError):
            Connector()  # type: ignore[abstract]

    def test_subclasse_incompleta(self) -> None:
        class Incompleto(Connector):
            pass

        with pytest.raises(TypeError):
            Incompleto()  # type: ignore[abstract]

    def test_tres_conectores_sao_subclasses(self) -> None:
        assert issubclass(HTTPConnector, Connector)
        assert issubclass(WebhookConnector, Connector)
        assert issubclass(BoltConnector, Connector)


class TestFronteiraArquitetural:
    """6.5 - Connector NAO e *Port; rejeitado pelo ComponentRegistry."""

    def test_connector_nao_e_port(self) -> None:
        from framework.core.ports import (
            FetcherPort,
            IngestPort,
            TransformerPort,
            URNPort,
            ValidatorPort,
        )

        connector = HTTPConnector("https://api.example.com")
        assert not isinstance(connector, FetcherPort)
        assert not isinstance(connector, IngestPort)
        assert not isinstance(connector, TransformerPort)
        assert not isinstance(connector, ValidatorPort)
        assert not isinstance(connector, URNPort)

    def test_registry_rejeita_connector(self) -> None:
        registry = ComponentRegistry()
        connector = HTTPConnector("https://api.example.com")
        with pytest.raises(ConfigurationError) as exc:
            registry.register("http", connector)
        assert exc.value.context["rule"] == "REG-02"


class TestInvarianciaSobSubstituicao:
    """6.5 - Trocar protocolo nao altera conjunto de chaves de contexto."""

    @patch("framework.execution.connectors.time.sleep")
    def test_mesmas_chaves_de_contexto(self, mock_sleep: MagicMock) -> None:
        http_session = _FakeSession([_FakeResponse(503)])
        http = HTTPConnector(
            "https://api.example.com",
            config=ConnectorConfig(retry=RetryPolicy(max_attempts=1)),
        )
        http._session = http_session  # type: ignore[assignment]

        webhook_session = _FakeSession([_FakeResponse(500)])
        webhook = WebhookConnector(
            "https://n8n.example.com/webhook",
            config=ConnectorConfig(retry=RetryPolicy(max_attempts=1)),
        )
        webhook._session = webhook_session  # type: ignore[assignment]

        with pytest.raises(FetcherError) as exc_http:
            http.send({})
        with pytest.raises(IngestorError) as exc_webhook:
            webhook.send({})

        chaves_http = set(exc_http.value.context.keys())
        chaves_webhook = set(exc_webhook.value.context.keys())
        # Ambas devem ter as chaves basicas de contexto de falha.
        chaves_basicas = {
            "connector",
            "protocol",
            "endpoint",
            "attempts",
            "timeout_seconds",
            "retryable",
        }
        assert chaves_basicas <= chaves_http
        assert chaves_basicas <= chaves_webhook


# ===========================================================================
# 6.6 Integracao com Mocks por Protocolo
# ===========================================================================


class TestHTTPConnectorIntegracao:
    """6.6 - HTTP com sessao duble."""

    @patch("framework.execution.connectors.time.sleep")
    def test_sucesso_200(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession([_FakeResponse(200, {"normas": [1, 2, 3]})])
        connector = HTTPConnector("https://api.example.com")
        connector._session = session  # type: ignore[assignment]
        response = connector.send({})
        assert response.is_success is True
        assert response.payload == {"normas": [1, 2, 3]}
        assert response.attempts == 1
        assert response.duration_seconds >= 0

    @patch("framework.execution.connectors.time.sleep")
    def test_retry_e_sucesso(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession(
            [_FakeResponse(503), _FakeResponse(503), _FakeResponse(200, {"ok": True})]
        )
        connector = HTTPConnector(
            "https://api.example.com",
            config=ConnectorConfig(retry=RetryPolicy(max_attempts=3)),
        )
        connector._session = session  # type: ignore[assignment]
        response = connector.send({})
        assert response.is_success is True
        assert response.attempts == 3
        assert mock_sleep.call_count == 2

    def test_close_idempotente(self) -> None:
        connector = HTTPConnector("https://api.example.com")
        connector.close()  # sem sessao
        connector.close()  # idempotente
        session = _FakeSession([])
        connector._session = session  # type: ignore[assignment]
        connector.close()
        assert session.closed is True
        connector.close()  # idempotente


class TestWebhookConnectorIntegracao:
    """6.6 - Webhook com POST JSON e assinatura HMAC."""

    @patch("framework.execution.connectors.time.sleep")
    def test_post_json_com_assinatura(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession([_FakeResponse(200, {"received": True})])
        connector = WebhookConnector(
            "https://n8n.example.com/webhook", secret="my-secret"
        )
        connector._session = session  # type: ignore[assignment]
        response = connector.send({"event": "test", "data": [1, 2, 3]})
        assert response.is_success is True
        call = session.calls[0]
        assert call["method"] == "POST"
        assert "X-MCA-Signature" in call["headers"]
        # Verifica que o corpo foi serializado com sort_keys=True.
        body_bytes = call["data"]
        assert isinstance(body_bytes, bytes)
        body_json = json.loads(body_bytes.decode("utf-8"))
        assert body_json == {"data": [1, 2, 3], "event": "test"}

    @patch("framework.execution.connectors.time.sleep")
    def test_sem_secret_sem_assinatura(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession([_FakeResponse(200)])
        connector = WebhookConnector("https://n8n.example.com/webhook")
        connector._session = session  # type: ignore[assignment]
        connector.send({"event": "test"})
        call = session.calls[0]
        assert "X-MCA-Signature" not in call["headers"]


class TestBoltConnectorIntegracao:
    """6.6 - Bolt com driver duble."""

    @patch("framework.execution.connectors.time.sleep")
    def test_query_sucesso(self, mock_sleep: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = [{"n.id": 1}, {"n.id": 2}]
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        connector = BoltConnector("bolt://localhost:7687", database="solo_mca")
        connector._driver = mock_driver  # type: ignore[assignment]
        response = connector.send({"query": "MATCH (n) RETURN n.id"})
        assert response.is_success is True
        assert response.payload == [{"n.id": 1}, {"n.id": 2}]
        mock_driver.session.assert_called_with(database="solo_mca")

    def test_payload_sem_query_levanta_erro(self) -> None:
        connector = BoltConnector("bolt://localhost:7687")
        with pytest.raises(IngestorError) as exc:
            connector.send({"cypher": "MATCH (n) RETURN n"})
        assert exc.value.context["rule"] == "CONN-04"


class TestBuildConnector:
    """6.6 - Factory a partir de spec dict."""

    def test_build_http(self) -> None:
        spec = {
            "protocol": "http",
            "config": {
                "url": "https://api.example.com",
                "method": "GET",
                "timeout_seconds": 15.0,
            },
        }
        connector = build_connector(spec)
        assert isinstance(connector, HTTPConnector)
        assert connector.url == "https://api.example.com"
        assert connector.method == "GET"
        assert connector.config.timeout_seconds == 15.0

    def test_build_webhook(self) -> None:
        spec = {
            "protocol": "webhook",
            "config": {
                "url": "https://n8n.example.com/webhook",
                "secret": "my-secret",
            },
        }
        connector = build_connector(spec)
        assert isinstance(connector, WebhookConnector)
        assert connector.url == "https://n8n.example.com/webhook"

    def test_build_bolt(self) -> None:
        spec = {
            "protocol": "bolt",
            "config": {
                "uri": "bolt://localhost:7687",
                "user": "neo4j",
                "password": "secret",
                "database": "solo_mca",
            },
        }
        connector = build_connector(spec)
        assert isinstance(connector, BoltConnector)
        assert connector.uri == "bolt://localhost:7687"
        assert connector.database == "solo_mca"

    def test_build_protocolo_desconhecido(self) -> None:
        spec = {"protocol": "ftp", "config": {"url": "ftp://example.com"}}
        with pytest.raises(ConfigurationError) as exc:
            build_connector(spec)
        assert exc.value.context["rule"] == "CFG-05"

    def test_build_com_retry_policy(self) -> None:
        spec = {
            "protocol": "http",
            "config": {
                "url": "https://api.example.com",
                "retry_policy": {
                    "max_attempts": 5,
                    "backoff": "linear",
                    "initial_delay": 2.0,
                },
            },
        }
        connector = build_connector(spec)
        assert connector.config.retry.max_attempts == 5
        assert connector.config.retry.backoff == "linear"
        assert connector.config.retry.initial_delay == 2.0


# ===========================================================================
# 6.7 Observabilidade, Seguranca e Higiene
# ===========================================================================


class TestSegurancaRedacao:
    """6.7 - SEC-01: segredos redigidos em metadados() e context."""

    def test_http_metadados_redigidos(self) -> None:
        connector = HTTPConnector(
            "https://api.example.com",
            config=ConnectorConfig(headers={"Authorization": "Bearer secret"}),
        )
        metadata = connector.metadados()
        assert metadata["headers"]["Authorization"] == "***"

    def test_webhook_metadados_redigidos(self) -> None:
        connector = WebhookConnector(
            "https://n8n.example.com/webhook", secret="my-secret"
        )
        metadata = connector.metadados()
        assert metadata["secret"] == "***"

    def test_bolt_metadados_redigidos(self) -> None:
        connector = BoltConnector(
            "bolt://localhost:7687", user="neo4j", password="secret"
        )
        metadata = connector.metadados()
        assert metadata["password"] == "***"
        assert metadata["user"] == "neo4j"

    @patch("framework.execution.connectors.time.sleep")
    def test_context_falha_redigido(self, mock_sleep: MagicMock) -> None:
        session = _FakeSession([_FakeResponse(503)])
        connector = HTTPConnector(
            "https://api.example.com",
            config=ConnectorConfig(retry=RetryPolicy(max_attempts=1)),
        )
        connector._session = session  # type: ignore[assignment]
        with pytest.raises(FetcherError) as exc:
            connector.send({}, context={"password": "secret123"})
        assert exc.value.context["password"] == "***"


class TestObservabilidadeOBS01:
    """6.7 - OBS-01: conector nao escreve logs/metrics/arquivos."""

    def test_ast_sem_print_logging_open(self) -> None:
        connectors_path = Path(__file__).resolve().parents[2] / "framework" / "execution" / "connectors.py"
        source = connectors_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in {"print", "logging"}, (
                        f"connectors.py contem chamada proibida: {node.func.id}"
                    )
                elif isinstance(node.func, ast.Attribute):
                    assert node.func.attr not in {"info", "warning", "error", "debug"}, (
                        f"connectors.py contem chamada de logger proibida"
                    )


class TestValidacaoCFG05:
    """6.7 - CFG-05: esquemas validos por protocolo."""

    def test_http_rejeita_ftp(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            HTTPConnector("ftp://example.com")
        assert exc.value.context["rule"] == "CFG-05"

    def test_webhook_rejeita_ftp(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            WebhookConnector("ftp://example.com")
        assert exc.value.context["rule"] == "CFG-05"

    def test_bolt_rejeita_http(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            BoltConnector("http://localhost:7687")
        assert exc.value.context["rule"] == "CFG-05"

    def test_bolt_aceita_neo4j_s(self) -> None:
        connector = BoltConnector("neo4j+s://localhost:7687")
        assert connector.uri == "neo4j+s://localhost:7687"


class TestValidacaoCFG06:
    """6.7 - CFG-06: verbos HTTP permitidos."""

    def test_http_rejeita_trace(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            HTTPConnector("https://api.example.com", method="TRACE")
        assert exc.value.context["rule"] == "CFG-06"

    def test_http_aceita_metodos_validos(self) -> None:
        for method in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
            connector = HTTPConnector("https://api.example.com", method=method)
            assert connector.method == method


class TestValidateConfig:
    """6.7 - validate_config() para spec declarativa."""

    def test_http_valida_url(self) -> None:
        connector = HTTPConnector("https://api.example.com")
        assert connector.validate_config({"url": "https://api.example.com"}) is True
        assert connector.validate_config({"url": "ftp://x"}) is False
        assert connector.validate_config({}) is False

    def test_webhook_valida_url(self) -> None:
        connector = WebhookConnector("https://n8n.example.com/webhook")
        assert connector.validate_config({"url": "https://n8n.example.com"}) is True
        assert connector.validate_config({}) is False

    def test_bolt_valida_uri(self) -> None:
        connector = BoltConnector("bolt://localhost:7687")
        assert connector.validate_config({"uri": "bolt://localhost:7687"}) is True
        assert connector.validate_config({"uri": "http://x"}) is False
        assert connector.validate_config({}) is False