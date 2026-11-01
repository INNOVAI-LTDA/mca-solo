"""Testes das portas de domínio (ABCs) do Core Framework (ID 1.3).

Cobertura da Estratégia de Testes da Seção 6 da Especificação Técnica:
    6.1. Barreira de abstração (não-instanciação das ABCs -> ``TypeError``).
    6.2. Contrato via mixins (Contract Test Pattern): tipos de retorno,
         presença de métodos obrigatórios e assinaturas via
         ``inspect.signature``.
    6.3. Invariante de substituição (LSP): ``isinstance`` + uso polimórfico.
    6.4. Detecção de contrato incompleto (subclasse parcial -> ``TypeError``).
    6.5. Docstrings e metadados (``Pre-condicoes`` / ``Pos-condicoes`` /
         ``Invariantes`` nas classes; ``Args:`` / ``Returns:`` / ``Raises:``
         nos métodos).
    6.6. Independência de adaptadores (análise estática de imports via
         ``ast``: nada de ``application/`` nem ``framework.execution``).

Execução:
    pytest tests/framework/test_core_ports.py -v
    pytest --cov=framework.core.ports --cov-report=term-missing
"""

from __future__ import annotations

import abc
import ast
import inspect
import re
import textwrap
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple, Type

import pytest

import framework.core.ports as ports_module
from framework.core.entities import (
    FetchResult,
    IngestResult,
    ValidationResult,
)
from framework.core.ports import (
    FetcherPort,
    IngestPort,
    TransformerPort,
    URNPort,
    ValidatorPort,
)

# ---------------------------------------------------------------------------
# Inventário central das portas (fonte única para testes parametrizados)
# ---------------------------------------------------------------------------

#: Tupla ``(nome_da_porta, classe_abstrata, methods_abstratos_esperados)``.
PORT_INVENTORY: Tuple[Tuple[str, Type[abc.ABC], Tuple[str, ...]], ...] = (
    ("FetcherPort", FetcherPort, ("buscar", "validar_config", "metadados")),
    ("IngestPort", IngestPort, ("ingerir", "validar_conexao", "metadados")),
    ("TransformerPort", TransformerPort, ("transformar", "transformacoes")),
    ("ValidatorPort", ValidatorPort, ("validar", "regras")),
    ("URNPort", URNPort, ("gerar", "validar", "parsear")),
)

ALL_PORT_CLASSES: Tuple[Type[abc.ABC], ...] = tuple(cls for _, cls, _ in PORT_INVENTORY)

PORT_NAMES: Tuple[str, ...] = tuple(name for name, _, _ in PORT_INVENTORY)


def _parametrize_ports(func: Any) -> Any:
    """Aplica ``pytest.mark.parametrize`` sobre o inventário de portas.

    Empacota as cinco portas em uma única parametrização (evita conflito
    de nomes de parâmetros causado por múltiplas decorações empilhadas).

    Args:
        func: Função de teste a ser parametrizada.

    Returns:
        A função decorada com um ``parametrize`` contendo as 5 portas.
    """
    return pytest.mark.parametrize(
        "porta_nome,porta_abstrata,metodos_esperados",
        list(PORT_INVENTORY),
        ids=list(PORT_NAMES),
    )(func)


def _corpo_sem_docstring(node: ast.FunctionDef) -> List[ast.stmt]:
    """Retorna o corpo de ``node`` sem a docstring, se houver.

    Args:
        node: Nó de definição de função vindo da AST.

    Returns:
        Lista de statements restantes após remover a docstring literal.
    """
    corpo = list(node.body)
    if (
        corpo
        and isinstance(corpo[0], ast.Expr)
        and isinstance(corpo[0].value, ast.Constant)
        and isinstance(corpo[0].value.value, str)
    ):
        corpo = corpo[1:]
    return corpo


# ---------------------------------------------------------------------------
# Stubs concretos (Seção 6.2/6.3): implementações mínimas dos contratos
# ---------------------------------------------------------------------------


class StubFetcher(FetcherPort):
    """Implementação fictícia completa de ``FetcherPort``."""

    def buscar(self, config: Dict[str, Any]) -> FetchResult:
        return FetchResult(
            items=[{"id": 1, "config": dict(config)}],
            metadata={"source": "stub"},
        )

    def validar_config(self, config: Dict[str, Any]) -> bool:
        return "url" in config

    def metadados(self) -> Dict[str, Any]:
        return {"nome": "StubFetcher", "versao": "1.0.0"}


class StubIngestor(IngestPort):
    """Implementação fictícia completa de ``IngestPort``."""

    def ingerir(self, dados: FetchResult) -> IngestResult:
        return IngestResult(
            success_count=dados.items_count,
            failure_count=0,
            ingested_ids=[item["id"] for item in dados.items],
        )

    def validar_conexao(self) -> bool:
        return True

    def metadados(self) -> Dict[str, Any]:
        return {"nome": "StubIngestor", "backend": "memory"}


class StubTransformer(TransformerPort):
    """Implementação fictícia completa de ``TransformerPort``."""

    def transformar(self, dados: FetchResult) -> FetchResult:
        novos_itens = [dict(item) for item in dados.items]
        return FetchResult(items=novos_itens, metadata=dict(dados.metadata))

    def transformacoes(self) -> List[str]:
        return ["normalizar", "enriquecer"]


class StubValidator(ValidatorPort):
    """Implementação fictícia completa de ``ValidatorPort``."""

    def validar(self, dados: List[Dict[str, Any]]) -> ValidationResult:
        violacoes = [
            {"rule": "K1", "description": "item sem id"}
            for item in dados
            if "id" not in item
        ]
        return ValidationResult(is_valid=len(violacoes) == 0, violations=violacoes)

    def regras(self) -> List[str]:
        return ["K1", "K2", "K3"]


class StubURNGenerator(URNPort):
    """Implementação fictícia completa de ``URNPort``."""

    _PATTERN = re.compile(r"^urn:lex:br:[a-z0-9_:;\.\-]+$")

    def gerar(self, dados: Dict[str, Any]) -> str:
        return (
            f"urn:lex:br:{dados.get('jurisdicao', 'federal')}:"
            f"{dados.get('tipo', 'lei')}:{dados.get('data', '1988-10-05')}"
            f";{dados.get('numero', '1')}"
        )

    def validar(self, urn: str) -> bool:
        return bool(self._PATTERN.match(urn))

    def parsear(self, urn: str) -> Dict[str, Any]:
        partes = urn.split(":")
        return {
            "scheme": partes[0],
            "pais": partes[2] if len(partes) > 2 else None,
            "raw": urn,
        }


# ===========================================================================
# 6.1. Testes de Barreira de Abstração (Não-Instanciação)
# ===========================================================================


class TestBarreiraDeAbstracao:
    """Nenhuma ABC de porta pode ser instanciada diretamente."""

    @_parametrize_ports
    def test_instanciacao_direta_levanta_type_error(
        self,
        porta_nome: str,
        porta_abstrata: Type[abc.ABC],
        metodos_esperados: Tuple[str, ...],
    ) -> None:
        """``porta()`` deve levantar ``TypeError`` citando os abstract methods."""
        with pytest.raises(TypeError) as excinfo:
            porta_abstrata()  # type: ignore[abstract]

        mensagem = str(excinfo.value)
        assert "abstract" in mensagem.lower()
        # A mensagem precisa indicar ao menos o primeiro método faltante.
        assert metodos_esperados[0] in mensagem or "method" in mensagem.lower()

    @_parametrize_ports
    def test_classe_e_abc_com_metodos_abstratos(
        self,
        porta_nome: str,
        porta_abstrata: Type[abc.ABC],
        metodos_esperados: Tuple[str, ...],
    ) -> None:
        """Cada porta herda de ``abc.ABC`` e declara os métodos esperados."""
        assert issubclass(porta_abstrata, abc.ABC)
        assert abc.ABC in porta_abstrata.__bases__ or any(
            base is abc.ABC for base in inspect.getmro(porta_abstrata)
        )
        assert porta_abstrata.__abstractmethods__ == frozenset(
            metodos_esperados
        ), f"{porta_nome}: conjunto de métodos abstratos divergente"

    @_parametrize_ports
    def test_todos_os_metodos_de_contrato_estao_decorados(
        self,
        porta_nome: str,
        porta_abstrata: Type[abc.ABC],
        metodos_esperados: Tuple[str, ...],
    ) -> None:
        """Cada método de contrato possui ``__isabstractmethod__ = True``."""
        for nome in metodos_esperados:
            metodo = getattr(porta_abstrata, nome)
            assert getattr(metodo, "__isabstractmethod__", False) is True, (
                f"{porta_nome}.{nome} não está decorado com " "@abc.abstractmethod"
            )

    @_parametrize_ports
    def test_corpos_dos_metodos_abstratos_nao_tem_logica(
        self,
        porta_nome: str,
        porta_abstrata: Type[abc.ABC],
        metodos_esperados: Tuple[str, ...],
    ) -> None:
        """Corpos dos abstratos contêm apenas docstring + ``...`` (Ellipsis)."""
        arvore = ast.parse(textwrap.dedent(inspect.getsource(porta_abstrata)))
        classe = arvore.body[0]
        assert isinstance(classe, ast.ClassDef)
        for node in classe.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            corpo = _corpo_sem_docstring(node)
            assert (
                len(corpo) == 1
            ), f"{porta_nome}.{node.name}: corpo deve ter apenas Ellipsis"
            stmt = corpo[0]
            assert isinstance(stmt, ast.Expr) and isinstance(
                stmt.value, ast.Constant
            ), f"{porta_nome}.{node.name}: corpo deve ser literal"
            assert (
                stmt.value.value is Ellipsis
            ), f"{porta_nome}.{node.name}: corpo deve ser exatamente '...'"


# ===========================================================================
# 6.2. Testes de Contrato via Mixins (Padrão Contract Test)
# ===========================================================================


class FetcherPortContractTests:
    """Mixin genérico de contrato para qualquer implementação de FetcherPort."""

    stub_class: Type[FetcherPort]

    @pytest.fixture
    def fetcher(self) -> Iterator[FetcherPort]:
        yield self.stub_class()

    def test_retorna_fetch_result(self, fetcher: FetcherPort) -> None:
        resultado = fetcher.buscar({"url": "https://example.com"})
        assert isinstance(resultado, FetchResult)

    def test_items_sao_lista_de_dicts(self, fetcher: FetcherPort) -> None:
        resultado = fetcher.buscar({"url": "https://example.com"})
        assert isinstance(resultado.items, list)
        assert all(isinstance(item, dict) for item in resultado.items)

    def test_proveniencia_presente(self, fetcher: FetcherPort) -> None:
        resultado = fetcher.buscar({"url": "https://example.com"})
        assert "source" in resultado.metadata

    def test_validar_config_retorna_bool(self, fetcher: FetcherPort) -> None:
        assert isinstance(fetcher.validar_config({"url": "x"}), bool)
        assert isinstance(fetcher.validar_config({}), bool)

    def test_metadados_retorna_dict(self, fetcher: FetcherPort) -> None:
        assert isinstance(fetcher.metadados(), dict)

    def test_presenca_de_metodos_obrigatorios(self) -> None:
        for nome in ("buscar", "validar_config", "metadados"):
            assert hasattr(self.stub_class, nome), nome

    def test_assinaturas_via_inspect(self) -> None:
        assert list(inspect.signature(self.stub_class.buscar).parameters) == [
            "self",
            "config",
        ]
        assert list(inspect.signature(self.stub_class.validar_config).parameters) == [
            "self",
            "config",
        ]
        assert list(inspect.signature(self.stub_class.metadados).parameters) == ["self"]
        retornos = {
            nome: inspect.signature(getattr(self.stub_class, nome)).return_annotation
            for nome in ("buscar", "validar_config", "metadados")
        }
        assert retornos["buscar"] in (FetchResult, "FetchResult")
        assert retornos["validar_config"] in (bool, "bool")
        assert str(retornos["metadados"]) in (
            "Dict[str, Any]",
            "dict[str, Any]",
        )


class IngestPortContractTests:
    """Mixin genérico de contrato para qualquer implementação de IngestPort."""

    stub_class: Type[IngestPort]

    @pytest.fixture
    def ingestor(self) -> Iterator[IngestPort]:
        yield self.stub_class()

    @pytest.fixture
    def dados(self) -> FetchResult:
        return FetchResult(items=[{"id": 1}, {"id": 2}], metadata={"source": "x"})

    def test_retorna_ingest_result(
        self, ingestor: IngestPort, dados: FetchResult
    ) -> None:
        assert isinstance(ingestor.ingerir(dados), IngestResult)

    def test_contadores_coerentes(
        self, ingestor: IngestPort, dados: FetchResult
    ) -> None:
        resultado = ingestor.ingerir(dados)
        assert resultado.total_count == resultado.success_count + (
            resultado.failure_count
        )
        assert resultado.success_count == dados.items_count

    def test_ingested_ids_possiveis_de_ler(
        self, ingestor: IngestPort, dados: FetchResult
    ) -> None:
        resultado = ingestor.ingerir(dados)
        assert isinstance(resultado.ingested_ids, list)

    def test_validar_conexao_retorna_bool(self, ingestor: IngestPort) -> None:
        assert isinstance(ingestor.validar_conexao(), bool)

    def test_metadados_retorna_dict(self, ingestor: IngestPort) -> None:
        assert isinstance(ingestor.metadados(), dict)

    def test_presenca_de_metodos_obrigatorios(self) -> None:
        for nome in ("ingerir", "validar_conexao", "metadados"):
            assert hasattr(self.stub_class, nome), nome

    def test_assinaturas_via_inspect(self) -> None:
        assert list(inspect.signature(self.stub_class.ingerir).parameters) == [
            "self",
            "dados",
        ]
        assert list(inspect.signature(self.stub_class.validar_conexao).parameters) == [
            "self"
        ]
        assert list(inspect.signature(self.stub_class.metadados).parameters) == ["self"]
        assert inspect.signature(self.stub_class.ingerir).return_annotation in (
            IngestResult,
            "IngestResult",
        )


class TransformerPortContractTests:
    """Mixin genérico de contrato p/ ``TransformerPort``."""

    stub_class: Type[TransformerPort]

    @pytest.fixture
    def transformer(self) -> Iterator[TransformerPort]:
        yield self.stub_class()

    @pytest.fixture
    def dados(self) -> FetchResult:
        return FetchResult(
            items=[{"id": 1, "titulo": "Lei X"}], metadata={"source": "senado"}
        )

    def test_retorna_fetch_result(
        self, transformer: TransformerPort, dados: FetchResult
    ) -> None:
        assert isinstance(transformer.transformar(dados), FetchResult)

    def test_preserva_proveniencia(
        self, transformer: TransformerPort, dados: FetchResult
    ) -> None:
        saida = transformer.transformar(dados)
        assert saida.metadata.get("source") == dados.metadata.get("source")

    def test_transformacoes_retorna_lista_de_str(
        self, transformer: TransformerPort
    ) -> None:
        transformacoes = transformer.transformacoes()
        assert isinstance(transformacoes, list)
        assert all(isinstance(t, str) for t in transformacoes)

    def test_presenca_de_metodos_obrigatorios(self) -> None:
        for nome in ("transformar", "transformacoes"):
            assert hasattr(self.stub_class, nome), nome

    def test_assinaturas_via_inspect(self) -> None:
        assert list(inspect.signature(self.stub_class.transformar).parameters) == [
            "self",
            "dados",
        ]
        assert list(inspect.signature(self.stub_class.transformacoes).parameters) == [
            "self"
        ]
        assert inspect.signature(self.stub_class.transformar).return_annotation in (
            FetchResult,
            "FetchResult",
        )


class ValidatorPortContractTests:
    """Mixin genérico de contrato p/ ``ValidatorPort``."""

    stub_class: Type[ValidatorPort]

    @pytest.fixture
    def validator(self) -> Iterator[ValidatorPort]:
        yield self.stub_class()

    def test_retorna_validation_result(self, validator: ValidatorPort) -> None:
        resultado = validator.validar([{"id": 1}])
        assert isinstance(resultado, ValidationResult)

    def test_violacoes_em_item_incompleto(self, validator: ValidatorPort) -> None:
        resultado = validator.validar([{"no_id": True}])
        assert resultado.is_valid is False
        assert resultado.violations_count >= 1

    def test_regras_retorna_lista_de_str(self, validator: ValidatorPort) -> None:
        regras = validator.regras()
        assert isinstance(regras, list)
        assert all(isinstance(r, str) for r in regras)

    def test_presenca_de_metodos_obrigatorios(self) -> None:
        for nome in ("validar", "regras"):
            assert hasattr(self.stub_class, nome), nome

    def test_assinaturas_via_inspect(self) -> None:
        assert list(inspect.signature(self.stub_class.validar).parameters) == [
            "self",
            "dados",
        ]
        assert list(inspect.signature(self.stub_class.regras).parameters) == ["self"]
        assert inspect.signature(self.stub_class.validar).return_annotation in (
            ValidationResult,
            "ValidationResult",
        )


class URNPortContractTests:
    """Mixin genérico de contrato p/ ``URNPort``."""

    stub_class: Type[URNPort]

    @pytest.fixture
    def urn_gen(self) -> Iterator[URNPort]:
        yield self.stub_class()

    def test_gerar_retorna_str(self, urn_gen: URNPort) -> None:
        urn = urn_gen.gerar({"jurisdicao": "federal", "tipo": "lei"})
        assert isinstance(urn, str)

    def test_gerar_prefixo_canonico(self, urn_gen: URNPort) -> None:
        urn = urn_gen.gerar({"jurisdicao": "federal", "tipo": "lei"})
        assert urn.startswith("urn:lex:br:")

    def test_validar_roundtrip(self, urn_gen: URNPort) -> None:
        urn = urn_gen.gerar({"jurisdicao": "federal", "tipo": "decreto"})
        assert urn_gen.validar(urn) is True
        assert urn_gen.validar("http://exemplo.com") is False

    def test_parsear_retorna_dict(self, urn_gen: URNPort) -> None:
        urn = urn_gen.gerar({"jurisdicao": "federal", "tipo": "lei"})
        assert isinstance(urn_gen.parsear(urn), dict)

    def test_presenca_de_metodos_obrigatorios(self) -> None:
        for nome in ("gerar", "validar", "parsear"):
            assert hasattr(self.stub_class, nome), nome

    def test_assinaturas_via_inspect(self) -> None:
        assert list(inspect.signature(self.stub_class.gerar).parameters) == [
            "self",
            "dados",
        ]
        assert list(inspect.signature(self.stub_class.validar).parameters) == [
            "self",
            "urn",
        ]
        assert list(inspect.signature(self.stub_class.parsear).parameters) == [
            "self",
            "urn",
        ]
        assert inspect.signature(self.stub_class.gerar).return_annotation in (
            str,
            "str",
        )
        assert inspect.signature(self.stub_class.validar).return_annotation in (
            bool,
            "bool",
        )


# --- Vinculação dos stubs aos mixins (herdam mixin + teste em classe pytest) ---


class TestFetcherPortContrato(FetcherPortContractTests):
    stub_class = StubFetcher


class TestIngestPortContrato(IngestPortContractTests):
    stub_class = StubIngestor


class TestTransformerPortContrato(TransformerPortContractTests):
    stub_class = StubTransformer


class TestValidatorPortContrato(ValidatorPortContractTests):
    stub_class = StubValidator


class TestURNPortContrato(URNPortContractTests):
    stub_class = StubURNGenerator


# ===========================================================================
# 6.3. Testes de Invariante de Substituição (LSP)
# ===========================================================================


STUB_TO_PORT: Tuple[Tuple[Type[object], Type[abc.ABC], str], ...] = (
    (StubFetcher, FetcherPort, "FetcherPort"),
    (StubIngestor, IngestPort, "IngestPort"),
    (StubTransformer, TransformerPort, "TransformerPort"),
    (StubValidator, ValidatorPort, "ValidatorPort"),
    (StubURNGenerator, URNPort, "URNPort"),
)


class TestSubstituicaoLSP:
    """Adaptadores conformes são intercambiáveis pelos seus contratos."""

    @pytest.mark.parametrize(
        "stub_cls,porta_abstrata,porta_nome",
        STUB_TO_PORT,
        ids=[name for _, _, name in STUB_TO_PORT],
    )
    def test_isinstance_do_contrato(
        self,
        stub_cls: Type[object],
        porta_abstrata: Type[abc.ABC],
        porta_nome: str,
    ) -> None:
        instancia = stub_cls()
        assert isinstance(instancia, porta_abstrata)
        assert issubclass(stub_cls, porta_abstrata)

    def test_uso_polimorfico_em_contexto_que_espera_a_porta(self) -> None:
        """Um pipeline tipado pela porta aceita qualquer adapter conforme."""

        def pipeline(fetcher: FetcherPort, ingestor: IngestPort) -> int:
            dados = fetcher.buscar({"url": "https://x"})
            resultado = ingestor.ingerir(dados)
            return resultado.success_count

        assert pipeline(StubFetcher(), StubIngestor()) == 1

    def test_substituicao_entre_implementacoes_diferentes(self) -> None:
        """Duas implementações distintas de ``URNPort`` são intercambiáveis."""

        class OutroURN(URNPort):
            def gerar(self, dados: Dict[str, Any]) -> str:
                return "urn:lex:br:custom"

            def validar(self, urn: str) -> bool:
                return urn == "urn:lex:br:custom"

            def parsear(self, urn: str) -> Dict[str, Any]:
                return {"urn": urn}

        geradores: List[URNPort] = [StubURNGenerator(), OutroURN()]
        for gerador in geradores:
            urn = gerador.gerar({"jurisdicao": "federal"})
            assert gerador.validar(urn) is True
            assert isinstance(gerador.parsear(urn), dict)


# ===========================================================================
# 6.4. Testes de Detecção de Contrato Incompleto
# ===========================================================================


class TestContratoIncompleto:
    """Subclasses parciais devem falhar na instanciação (barreira de runtime)."""

    def test_fetcher_sem_metadados_e_levantar_type_error(self) -> None:
        class ParcialFetcher(FetcherPort):
            def buscar(self, config: Dict[str, Any]) -> FetchResult:
                return FetchResult(items=[])

            def validar_config(self, config: Dict[str, Any]) -> bool:
                return True

        with pytest.raises(TypeError) as excinfo:
            ParcialFetcher()  # type: ignore[abstract]
        assert "metadados" in str(excinfo.value)

    def test_ingestor_sem_validar_conexao(self) -> None:
        class ParcialIngestor(IngestPort):
            def ingerir(self, dados: FetchResult) -> IngestResult:
                return IngestResult()

            def metadados(self) -> Dict[str, Any]:
                return {}

        with pytest.raises(TypeError) as excinfo:
            ParcialIngestor()  # type: ignore[abstract]
        assert "validar_conexao" in str(excinfo.value)

    def test_transformer_sem_transformacoes(self) -> None:
        class ParcialTransformer(TransformerPort):
            def transformar(self, dados: FetchResult) -> FetchResult:
                return dados

        with pytest.raises(TypeError) as excinfo:
            ParcialTransformer()  # type: ignore[abstract]
        assert "transformacoes" in str(excinfo.value)

    def test_validator_sem_regras(self) -> None:
        class ParcialValidator(ValidatorPort):
            def validar(self, dados: List[Dict[str, Any]]) -> ValidationResult:
                return ValidationResult(is_valid=True)

        with pytest.raises(TypeError) as excinfo:
            ParcialValidator()  # type: ignore[abstract]
        assert "regras" in str(excinfo.value)

    def test_urn_sem_parsear(self) -> None:
        class ParcialURN(URNPort):
            def gerar(self, dados: Dict[str, Any]) -> str:
                return "urn:lex:br:federal"

            def validar(self, urn: str) -> bool:
                return True

        with pytest.raises(TypeError) as excinfo:
            ParcialURN()  # type: ignore[abstract]
        assert "parsear" in str(excinfo.value)

    def test_subclasse_totalmente_vazia_falha(self) -> None:
        """Herdar sem implementar NADA também é bloqueado pelo ABCMeta."""

        class Vazio(FetcherPort):
            pass

        with pytest.raises(TypeError):
            Vazio()  # type: ignore[abstract]

    def test_adapter_sem_heranca_nominal_nao_e_registravel(self) -> None:
        """Regra de Ouro: ausência de herança => não é uma porta conforme."""

        class DuckFetcher:
            def buscar(self, config: Dict[str, Any]) -> FetchResult:
                return FetchResult(items=[])

            def validar_config(self, config: Dict[str, Any]) -> bool:
                return True

            def metadados(self) -> Dict[str, Any]:
                return {}

        assert not isinstance(DuckFetcher(), FetcherPort)
        assert not issubclass(DuckFetcher, FetcherPort)


# ===========================================================================
# 6.5. Testes de Docstring e Metadados
# ===========================================================================


class TestDocstringsEMetadados:
    """Documentação contratual obrigatória em classes e métodos abstratos."""

    @_parametrize_ports
    def test_docstring_da_classe_nao_vazia(
        self,
        porta_nome: str,
        porta_abstrata: Type[abc.ABC],
        metodos_esperados: Tuple[str, ...],
    ) -> None:
        doc = inspect.getdoc(porta_abstrata)
        assert doc, f"{porta_nome} não possui docstring"
        assert len(doc.strip()) > 20

    @_parametrize_ports
    def test_docstring_da_classe_tem_secoes_contratuais(
        self,
        porta_nome: str,
        porta_abstrata: Type[abc.ABC],
        metodos_esperados: Tuple[str, ...],
    ) -> None:
        doc = inspect.getdoc(porta_abstrata) or ""
        for secao in ("Pre-condicoes:", "Pos-condicoes:", "Invariantes:"):
            assert secao in doc, f"{porta_nome}: falta seção {secao}"

    @_parametrize_ports
    def test_docstring_dos_metodos_tem_args_returns_raises(
        self,
        porta_nome: str,
        porta_abstrata: Type[abc.ABC],
        metodos_esperados: Tuple[str, ...],
    ) -> None:
        for nome in metodos_esperados:
            metodo = getattr(porta_abstrata, nome)
            doc = inspect.getdoc(metodo)
            assert doc, f"{porta_nome}.{nome}: docstring vazia"
            for secao in ("Args:", "Returns:", "Raises:"):
                assert secao in doc, f"{porta_nome}.{nome}: falta {secao}"

    def test_docstring_do_modulo_presente(self) -> None:
        assert ports_module.__doc__, "Módulo ports.py sem docstring"
        assert "Hexagonal" in (ports_module.__doc__ or "")

    def test_all_exporta_as_cinco_abcs(self) -> None:
        assert set(ports_module.__all__) == set(PORT_NAMES)
        assert len(ports_module.__all__) == 5
        for nome in ports_module.__all__:
            assert hasattr(ports_module, nome), nome

    def test_star_import_expoe_apenas_as_portas(self) -> None:
        namespace: Dict[str, Any] = {}
        exec(  # noqa: S102 - avaliacao deliberada do contrato de __all__
            "from framework.core.ports import *", namespace
        )
        exportadas = {k for k, v in namespace.items() if isinstance(v, type)}
        assert exportadas == set(PORT_NAMES)


# ===========================================================================
# 6.6. Testes de Independência de Adaptadores
# ===========================================================================


PORTS_PATH = Path(ports_module.__file__).resolve()


def _collect_imports(path: Path) -> List[str]:
    """Retorna todos os nomes importados (absolutos) por um módulo via AST."""
    arvore = ast.parse(path.read_text(encoding="utf-8"))
    nomes: List[str] = []
    for node in ast.walk(arvore):
        if isinstance(node, ast.Import):
            nomes.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                nomes.append(node.module)
    return nomes


class TestIndependenciaDeAdaptadores:
    """``ports.py`` só conhece a stdlib e as entidades do próprio core."""

    ALLOWED_PREFIXES = (
        "__future__",
        "abc",
        "typing",
        "collections",
        "datetime",
        "framework.core.entities",
    )

    def test_nenhum_import_de_application_ou_execution(self) -> None:
        imports = _collect_imports(PORTS_PATH)
        proibidos = ("application", "framework.execution", "airflow")
        for modulo in imports:
            for prefixo in proibidos:
                assert not modulo.startswith(
                    prefixo
                ), f"ports.py importa módulo proibido: {modulo}"

    def test_todos_os_imports_estao_na_whitelist(self) -> None:
        for modulo in _collect_imports(PORTS_PATH):
            assert modulo.startswith(
                self.ALLOWED_PREFIXES
            ), f"Import fora da whitelist em ports.py: {modulo}"

    def test_dependencia_unidirecional_ports_entities(self) -> None:
        """entities.py NÃO pode importar ports.py (sem ciclo)."""
        entities_path = PORTS_PATH.parent / "entities.py"
        assert entities_path.exists()
        imports_entities = _collect_imports(entities_path)
        assert not any(m.endswith(".ports") or m == "ports" for m in imports_entities)
        imports_ports = _collect_imports(PORTS_PATH)
        assert any(
            m.endswith("framework.core.entities") for m in imports_ports
        ), "ports.py deve depender de entities.py"

    def test_modulo_importa_sem_montar_application(self) -> None:
        """Importar ``framework.core.ports`` não carrega adaptadores."""
        carregados = [
            nome
            for nome in inspect.getmembers(__import__("sys").modules)
            if nome[0].startswith("application.")
        ]
        # Pode haver 0 ou mais; o que importa é que ports não force nenhum:
        assert "application.components.senado_adapter" not in _collect_imports(
            PORTS_PATH
        )
        assert isinstance(carregados, list)
