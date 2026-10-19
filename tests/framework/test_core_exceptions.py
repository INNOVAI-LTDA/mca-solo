"""Testes unitarios para a hierarquia de excecoes do Core (ID 1.1).

Cobertura das categorias da secao 6 da especificacao tecnica:
    6.1 - Instanciacao e contratos do construtor.
    6.2 - Imutabilidade do contexto (copia defensiva / propriedade read-only).
    6.3 - Heranca e captura (polimorfismo).
    6.4 - Encadeamento de excecoes (preservacao de traceback).

Execucao:
    pytest tests/framework/test_core_exceptions.py -v
    pytest --cov=framework.core.exceptions --cov-report=term-missing
"""

from typing import Any, Dict, List, Type

import pytest

from framework.core.exceptions import (
    ConfigurationError,
    FetcherError,
    FrameworkError,
    IngestorError,
    TransformerError,
    ValidationError,
)

# Todas as classes concretas da hierarquia (base + 5 subclasses).
ALL_EXCEPTION_CLASSES: List[Type[FrameworkError]] = [
    FrameworkError,
    ConfigurationError,
    FetcherError,
    IngestorError,
    TransformerError,
    ValidationError,
]

# As 5 subclasses diretas da base.
SUBCLASSES: List[Type[FrameworkError]] = [
    ConfigurationError,
    FetcherError,
    IngestorError,
    TransformerError,
    ValidationError,
]


# ---------------------------------------------------------------------------
# 6.1 Testes de Instanciacao e Contratos
# ---------------------------------------------------------------------------


class TestInstanciacaoEContratos:
    """Garante o contrato do construtor: message, context e cause."""

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_instancia_apenas_com_message(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """Todas as classes podem ser instanciadas apenas com `message`."""
        erro = exc_class("falha ocorreu")
        assert isinstance(erro, exc_class)

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_atributo_message_acessivel(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """O atributo `message` e acessivel e corresponde ao valor passado."""
        erro = exc_class("mensagem legivel do erro")
        assert erro.message == "mensagem legivel do erro"

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_message_passada_ao_super_init(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """A mensagem deve estar presente em `args` (super().__init__)."""
        erro = exc_class("presente em args")
        assert "presente em args" in erro.args

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_context_padrao_e_dicionario_vazio(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """Sem `context`, o padrao deve ser um dicionario vazio `{}`."""
        erro = exc_class("sem contexto")
        assert erro.context == {}
        assert isinstance(erro.context, dict)

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_context_explicito_preservado(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """Metadados fornecidos devem estar disponiveis na instancia."""
        ctx: Dict[str, Any] = {"dag": "d1", "component": "senado_adapter"}
        erro = exc_class("com contexto", context=ctx)
        assert erro.context == ctx

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_cause_padrao_e_none(self, exc_class: Type[FrameworkError]) -> None:
        """Sem `cause`, o atributo deve ser `None`."""
        erro = exc_class("sem causa")
        assert erro.cause is None

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_str_contem_mensagem(self, exc_class: Type[FrameworkError]) -> None:
        """A representacao textual deve conter a mensagem do erro."""
        erro = exc_class("detalhe do erro")
        assert "detalhe do erro" in str(erro)

    def test_str_inclui_contexto_quando_preenchido(self) -> None:
        """Com contexto preenchido, `str()` deve expor os metadados."""
        erro = FetcherError("timeout", context={"url": "https://x"})
        assert "url" in str(erro)


# ---------------------------------------------------------------------------
# 6.2 Testes de Imutabilidade do Contexto (Critico para Observabilidade)
# ---------------------------------------------------------------------------


class TestImutabilidadeDoContexto:
    """Prova a copia defensiva e a exposicao read-only de `context`."""

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_copia_defensiva_externa(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """Modificar o dict original apos a instancia nao altera o interno."""
        ctx: Dict[str, Any] = {"key": "value"}
        erro = exc_class("imutabilidade", context=ctx)
        ctx["key"] = "changed"
        ctx["novo"] = "adicionado"
        assert erro.context == {"key": "value"}
        assert erro.context["key"] != "changed"

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_copia_defensiva_profunda(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """Mutacao de objetos aninhados no original nao vaza para dentro."""
        ctx: Dict[str, Any] = {"outer": {"inner": "valor"}}
        erro = exc_class("deep copy", context=ctx)
        ctx["outer"]["inner"] = "mutado"
        assert erro.context["outer"]["inner"] == "valor"

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_context_e_propriedade_read_only(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """Tentar reatribuir `context` deve lancar AttributeError."""
        erro = exc_class("read only", context={"a": 1})
        with pytest.raises(AttributeError):
            erro.context = {"a": 2}  # type: ignore[misc]

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_message_e_propriedade_read_only(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """Tentar reatribuir `message` deve lancar AttributeError."""
        erro = exc_class("read only")
        with pytest.raises(AttributeError):
            erro.message = "alterada"  # type: ignore[misc]

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_cause_e_propriedade_read_only(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """Tentar reatribuir `cause` deve lancar AttributeError."""
        erro = exc_class("read only")
        with pytest.raises(AttributeError):
            erro.cause = ValueError("x")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 6.3 Testes de Heranca e Captura (Polimorfismo)
# ---------------------------------------------------------------------------


class TestHerancaECaptura:
    """Valida a arvore de heranca e o polimorfismo do bloco except base."""

    @pytest.mark.parametrize("exc_class", SUBCLASSES)
    def test_subclass_e_instancia_de_framework_error(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """Todas as subclasses devem ser capturaveis como FrameworkError."""
        erro = exc_class("subclasse")
        assert isinstance(erro, FrameworkError)

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_todas_sao_instancias_de_exception(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """Toda a hierarquia herda de Exception."""
        erro = exc_class("qualquer")
        assert isinstance(erro, Exception)

    @pytest.mark.parametrize("exc_class", SUBCLASSES)
    def test_heranca_direta_de_framework_error(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """Cada subclasse herda diretamente de FrameworkError."""
        assert issubclass(exc_class, FrameworkError)
        assert FrameworkError in exc_class.__bases__

    def test_framework_error_nao_e_subclass_de_as_subclasses(
        self,
    ) -> None:
        """A base nao deve ser instancia de nenhuma subclasse (antisimetria)."""
        base = FrameworkError("base")
        for exc_class in SUBCLASSES:
            assert not isinstance(base, exc_class)

    def test_except_framework_error_capture_validation_error(self) -> None:
        """Um unico `except FrameworkError` captura ValidationError lancada."""
        captured: List[FrameworkError] = []
        try:
            raise ValidationError(
                "violacao da invariante K2", context={"invariante": "K2"}
            )
        except FrameworkError as erro:
            captured.append(erro)
        assert len(captured) == 1
        assert isinstance(captured[0], ValidationError)
        assert captured[0].context == {"invariante": "K2"}

    @pytest.mark.parametrize("exc_class", SUBCLASSES)
    def test_polimorfismo_captura_todas_subclasses(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """O Involucre de Gestao captura qualquer falha via bloco unico."""
        with pytest.raises(FrameworkError) as excinfo:
            raise exc_class("falha polimorfica")
        assert isinstance(excinfo.value, exc_class)


# ---------------------------------------------------------------------------
# 6.4 Testes de Encadeamento (Traceback Preservation)
# ---------------------------------------------------------------------------


class TestEncadeamento:
    """Garante preservacao da excecao original via `cause`/`__cause__`."""

    def test_cause_popula_dunder_cause_exatamente(self) -> None:
        """`__cause__` deve ser exatamente a instancia do erro original."""
        erro_original = ValueError("Erro original")
        ingestor = IngestorError("falha de escrita", cause=erro_original)
        assert ingestor.cause is erro_original
        assert ingestor.__cause__ is erro_original
        assert isinstance(ingestor.cause, ValueError)

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_raise_from_preserva_traceback(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """`raise ... from original` deve setar __cause__ nativamente."""
        original = RuntimeError("rede caiu")
        with pytest.raises(FrameworkError) as excinfo:
            try:
                raise original
            except RuntimeError as exc:
                raise exc_class("falha envolvente", cause=exc) from exc
        assert excinfo.value.__cause__ is original
        assert excinfo.value.cause is original

    def test_encadeamento_especifico_descrito_na_especificacao(self) -> None:
        """Cenario 6.4 literal: ValueError -> IngestorError(cause=...)."""
        try:
            raise ValueError("Erro original")
        except ValueError as erro_original:
            with pytest.raises(IngestorError) as excinfo:
                raise IngestorError(
                    "Falha ao escrever no Neo4j",
                    context={"destination": "neo4j"},
                    cause=erro_original,
                ) from erro_original
        assert excinfo.value.__cause__ is erro_original
        assert str(excinfo.value.__cause__) == "Erro original"

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_args_contem_cause_para_classe_base(
        self, exc_class: Type[FrameworkError]
    ) -> None:
        """A causa deve ser propagada ao construtor nativo (via kwargs)."""
        original = KeyError("env_var")
        erro = exc_class("config invalida", cause=original)
        assert any(arg is original for arg in erro.args) or erro.cause is original
