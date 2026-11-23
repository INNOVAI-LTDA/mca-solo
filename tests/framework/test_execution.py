"""Suite de testes do Motor de Orquestracao (ID 2.1).

Cobre as 7 categorias da Spec ID 2.1 (Secao 6):
    6.1 Instanciacao e Contratos
    6.2 Ordem Topologica e Execucao Sequencial
    6.3 Deteccao de Ciclos e Dependencias Invalidas
    6.4 Propagacao de Dados entre Estagios
    6.5 Resolucao de Componentes (Registro)
    6.6 Falha Explicita (Edge Cases)
    6.7 Integracao com DAGDefinition

Regras de Ouro verificadas:
    - "Todo componente registrado deve herdar nominalmente de uma ABC de porta"
    - "A excecao e o veiculo de transporte de contexto para Observabilidade"
    - "Falha explicita: toda violacao interrompe a execucao, sem fallback"
    - "Gestao e invariante sob substituicao de implementacao"
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from framework.core.entities import FetchResult, IngestResult, ValidationResult
from framework.core.exceptions import ConfigurationError, FrameworkError
from framework.core.ports import (
    FetcherPort,
    IngestPort,
    TransformerPort,
    URNPort,
    ValidatorPort,
)
from framework.execution.orchestrator import (
    ComponentRegistry,
    ExecutionResult,
    ExecutionStatus,
    Orchestrator,
    StageExecutor,
    TopologicalSorter,
)

# ---------------------------------------------------------------------------
# Dubles de teste e helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DAGStub:
    """Duble estrutural de DAGDefinition para testes unitarios.

    O Orchestrator consome apenas id, pipeline e tasks. Usar um duble
    isola o motor (ID 2.1) do parser (ID 1.4).
    """

    id: str = "app_test"
    pipeline: dict[str, Any] = field(default_factory=dict)
    tasks: list[dict[str, Any]] = field(default_factory=list)


def make_dag(
    dag_id: str = "app_test",
    stages: list[dict[str, Any]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
) -> Any:
    """Constroi um duble de DAGDefinition.

    Args:
        dag_id: Identificador da DAG.
        stages: Estagios do pipeline (App DAG).
        tasks: Tarefas de gestao (Core DAG).

    Returns:
        Duble compativel com a interface consumida pelo Orchestrator.
    """
    pipeline = {"stages": stages} if stages is not None else {}
    return cast(Any, _DAGStub(id=dag_id, pipeline=pipeline, tasks=tasks or []))


class FetcherSpy(FetcherPort):
    """FetcherPort com registro de chamadas."""

    def __init__(self, output: Any) -> None:
        self.output = output
        self.calls: list[Any] = []

    def buscar(self, config: dict[str, Any]) -> FetchResult:
        self.calls.append(config)
        return self.output

    def validar_config(self, config: dict[str, Any]) -> bool:
        return True

    def metadados(self) -> dict[str, Any]:
        return {"name": "FetcherSpy", "version": "1.0.0"}


class TransformerSpy(TransformerPort):
    """TransformerPort com registro de chamadas."""

    def __init__(self, output: Any) -> None:
        self.output = output
        self.calls: list[Any] = []

    def transformar(self, dados: FetchResult) -> FetchResult:
        self.calls.append(dados)
        return self.output

    def transformacoes(self) -> list[str]:
        return ["transform"]


class IngestSpy(IngestPort):
    """IngestPort com registro de chamadas."""

    def __init__(self, output: Any = None) -> None:
        self.output = output or IngestResult(success_count=1)
        self.calls: list[Any] = []

    def ingerir(self, dados: FetchResult) -> IngestResult:
        self.calls.append(dados)
        return self.output

    def validar_conexao(self) -> bool:
        return True

    def metadados(self) -> dict[str, Any]:
        return {"name": "IngestSpy", "version": "1.0.0"}


class ValidatorSpy(ValidatorPort):
    """ValidatorPort com registro de chamadas."""

    def __init__(self, output: Any = None) -> None:
        self.output = output or ValidationResult(is_valid=True)
        self.calls: list[Any] = []

    def validar(self, dados: list[dict[str, Any]]) -> ValidationResult:
        self.calls.append(dados)
        return self.output

    def regras(self) -> list[str]:
        return ["K1", "K2", "K3"]


class URNSpy(URNPort):
    """URNPort com registro de chamadas."""

    def __init__(self, output: str = "urn:mca:solo:1") -> None:
        self.output = output
        self.calls: list[Any] = []

    def gerar(self, dados: dict[str, Any]) -> str:
        self.calls.append(dados)
        return self.output

    def validar(self, urn: str) -> bool:
        return urn.startswith("urn:")

    def parsear(self, urn: str) -> dict[str, Any]:
        return {"urn": urn}


class ExplodingFetcher(FetcherPort):
    """Fetcher que falha, para testes de falha explicita."""

    def buscar(self, config: dict[str, Any]) -> FetchResult:
        raise FrameworkError(
            "falha na origem",
            context={"source": "spy", "rule": "TEST-01"},
        )

    def validar_config(self, config: dict[str, Any]) -> bool:
        return True

    def metadados(self) -> dict[str, Any]:
        return {}


class DuckTypedFetcher:
    """Duck-typing: NAO herda de FetcherPort. Deve ser rejeitado (REG-02)."""

    def buscar(self, config: dict[str, Any]) -> FetchResult:  # pragma: no cover
        return FetchResult(items=[])

    def validar_config(self, config: dict[str, Any]) -> bool:
        return True

    def metadados(self) -> dict[str, Any]:
        return {}


@pytest.fixture
def fetch_result() -> Any:
    """Instancia de FetchResult sem acoplamento ao construtor."""
    return MagicMock(spec=FetchResult)


@pytest.fixture
def registry() -> ComponentRegistry:
    return ComponentRegistry()


@pytest.fixture
def orchestrator() -> Orchestrator:
    return Orchestrator()


# ===========================================================================
# 6.1 Instanciacao e Contratos
# ===========================================================================


class TestExecutionResultContrato:
    """6.1 - Imutabilidade e defaults de ExecutionResult."""

    def test_dataclass_e_frozen(self) -> None:
        params = ExecutionResult.__dataclass_params__  # type: ignore[attr-defined]
        assert params.frozen is True

    def test_mutacao_escalar_levanta_frozen(self) -> None:
        result = ExecutionResult(dag_id="app_x")
        with pytest.raises(FrozenInstanceError):
            result.dag_id = "app_y"  # type: ignore[misc]

    def test_defaults(self) -> None:
        result = ExecutionResult(dag_id="app_x")
        assert result.status is ExecutionStatus.SUCCESS
        assert result.stage_results == {}
        assert result.errors == []
        assert result.has_errors is False

    def test_timestamps_utc(self) -> None:
        result = ExecutionResult(dag_id="app_x")
        assert result.started_at.tzinfo is UTC
        assert result.finished_at.tzinfo is UTC

    def test_defaults_nao_compartilhados(self) -> None:
        a = ExecutionResult(dag_id="a")
        b = ExecutionResult(dag_id="b")
        assert a.stage_results is not b.stage_results
        assert a.errors is not b.errors

    def test_has_errors_true(self) -> None:
        result = ExecutionResult(dag_id="a", errors=[{"error": "x"}])
        assert result.has_errors is True

    def test_replace_preserva_imutabilidade(self) -> None:
        original = ExecutionResult(dag_id="a")
        derivado = replace(original, status=ExecutionStatus.FAILED)
        assert original.status is ExecutionStatus.SUCCESS
        assert derivado.status is ExecutionStatus.FAILED
        assert derivado.dag_id == "a"


class TestExecutionStatusEnum:
    """6.1 - Contrato do enum de status."""

    def test_valores_exatos(self) -> None:
        assert {s.value for s in ExecutionStatus} == {
            "SUCCESS",
            "PARTIAL_FAILURE",
            "FAILED",
        }

    def test_e_str_enum(self) -> None:
        assert isinstance(ExecutionStatus.SUCCESS, str)
        assert ExecutionStatus.SUCCESS == "SUCCESS"


class TestComponentRegistryContratoNominal:
    """6.1 - Heranca nominal obrigatoria (Regra de Ouro)."""

    @pytest.mark.parametrize(
        "component",
        [
            FetcherSpy(FetchResult(items=[])),
            TransformerSpy(FetchResult(items=[])),
            IngestSpy(),
            ValidatorSpy(),
            URNSpy(),
        ],
        ids=["fetcher", "transformer", "ingest", "validator", "urn"],
    )
    def test_aceita_todas_as_portas(
        self, registry: ComponentRegistry, component: Any
    ) -> None:
        registry.register("c", component)
        assert registry.get("c") is component

    def test_rejeita_duck_typing(self, registry: ComponentRegistry) -> None:
        with pytest.raises(ConfigurationError) as exc:
            registry.register("duck", DuckTypedFetcher())
        assert exc.value.context["rule"] == "REG-02"

    def test_valid_ports_contem_cinco_portas(self) -> None:
        assert set(ComponentRegistry.VALID_PORTS) == {
            FetcherPort,
            IngestPort,
            TransformerPort,
            ValidatorPort,
            URNPort,
        }


# ===========================================================================
# 6.2 Ordem Topologica e Execucao Sequencial
# ===========================================================================


class TestTopologicalSorterOrdenacao:
    """6.2 - Ordenacao topologica."""

    def test_lista_vazia(self) -> None:
        assert TopologicalSorter.sort([]) == []

    def test_sem_dependencias_preserva_ordem(self) -> None:
        tasks = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        assert [t["id"] for t in TopologicalSorter.sort(tasks)] == ["a", "b", "c"]

    def test_dependencia_simples(self) -> None:
        tasks = [{"id": "b", "depends_on": ["a"]}, {"id": "a"}]
        assert [t["id"] for t in TopologicalSorter.sort(tasks)] == ["a", "b"]

    def test_cadeia_linear_invertida(self) -> None:
        tasks = [
            {"id": "c", "depends_on": ["b"]},
            {"id": "b", "depends_on": ["a"]},
            {"id": "a"},
        ]
        assert [t["id"] for t in TopologicalSorter.sort(tasks)] == ["a", "b", "c"]

    def test_diamante(self) -> None:
        tasks = [
            {"id": "d", "depends_on": ["b", "c"]},
            {"id": "c", "depends_on": ["a"]},
            {"id": "b", "depends_on": ["a"]},
            {"id": "a"},
        ]
        order = [t["id"] for t in TopologicalSorter.sort(tasks)]
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_depends_on_none_e_vazio_equivalentes(self) -> None:
        tasks = [{"id": "a", "depends_on": None}, {"id": "b", "depends_on": []}]
        assert len(TopologicalSorter.sort(tasks)) == 2

    def test_retorna_os_mesmos_objetos(self) -> None:
        task_a = {"id": "a", "extra": 1}
        assert TopologicalSorter.sort([task_a])[0] is task_a

    def test_grafos_desconexos(self) -> None:
        tasks = [{"id": "x"}, {"id": "y", "depends_on": ["x"]}, {"id": "z"}]
        order = [t["id"] for t in TopologicalSorter.sort(tasks)]
        assert order.index("x") < order.index("y")
        assert set(order) == {"x", "y", "z"}


class TestOrchestratorOrdemExecucao:
    """6.2 - Estagios executam em ordem topologica, nao declarada."""

    def test_ordem_topologica_respeitada(
        self, orchestrator: Orchestrator, fetch_result: Any
    ) -> None:
        call_order: list[str] = []

        class OrderedFetcher(FetcherPort):
            def __init__(self, name: str) -> None:
                self.name = name

            def buscar(self, config: dict[str, Any]) -> FetchResult:
                call_order.append(self.name)
                return fetch_result

            def validar_config(self, config: dict[str, Any]) -> bool:
                return True

            def metadados(self) -> dict[str, Any]:
                return {}

        orchestrator.register_component("second", OrderedFetcher("second"))
        orchestrator.register_component("first", OrderedFetcher("first"))

        dag = make_dag(
            stages=[
                {"id": "s2", "component": "second", "depends_on": ["s1"]},
                {"id": "s1", "component": "first"},
            ]
        )
        result = orchestrator.execute_definition(dag)

        assert result.status is ExecutionStatus.SUCCESS
        assert call_order == ["first", "second"]

    def test_stage_results_contem_todos_os_estagios(
        self, orchestrator: Orchestrator, fetch_result: Any
    ) -> None:
        orchestrator.register_component("f", FetcherSpy(fetch_result))
        dag = make_dag(
            stages=[{"id": "s1", "component": "f"}, {"id": "s2", "component": "f"}]
        )
        result = orchestrator.execute_definition(dag)
        assert set(result.stage_results) == {"s1", "s2"}

    def test_timestamps_coerentes(
        self, orchestrator: Orchestrator, fetch_result: Any
    ) -> None:
        orchestrator.register_component("f", FetcherSpy(fetch_result))
        dag = make_dag(stages=[{"id": "s1", "component": "f"}])
        result = orchestrator.execute_definition(dag)
        assert result.started_at <= result.finished_at
        assert result.dag_id == "app_test"


class TestStageExecutorDespacho:
    """6.2 - Despacho por tipo de porta."""

    def test_fetcher_recebe_config(
        self, registry: ComponentRegistry, fetch_result: Any
    ) -> None:
        spy = FetcherSpy(fetch_result)
        registry.register("f", spy)
        out = StageExecutor(registry).execute(
            {"id": "s", "component": "f", "config": {"url": "http://x"}}, {}
        )
        assert out is fetch_result
        assert spy.calls == [{"url": "http://x"}]

    def test_fetcher_config_default_vazio(
        self, registry: ComponentRegistry, fetch_result: Any
    ) -> None:
        spy = FetcherSpy(fetch_result)
        registry.register("f", spy)
        StageExecutor(registry).execute({"id": "s", "component": "f"}, {})
        assert spy.calls == [{}]

    def test_transformer(
        self, registry: ComponentRegistry, fetch_result: Any
    ) -> None:
        spy = TransformerSpy("transformed")
        registry.register("t", spy)
        out = StageExecutor(registry).execute(
            {"id": "s", "component": "t", "input": "prev"}, {"prev": fetch_result}
        )
        assert out == "transformed"
        assert spy.calls == [fetch_result]

    def test_ingest(self, registry: ComponentRegistry, fetch_result: Any) -> None:
        spy = IngestSpy()
        registry.register("i", spy)
        out = StageExecutor(registry).execute(
            {"id": "s", "component": "i", "input": "prev"}, {"prev": fetch_result}
        )
        assert isinstance(out, IngestResult)
        assert spy.calls == [fetch_result]

    def test_validator(self, registry: ComponentRegistry) -> None:
        spy = ValidatorSpy()
        registry.register("v", spy)
        payload = [{"a": 1}]
        out = StageExecutor(registry).execute(
            {"id": "s", "component": "v", "input": "prev"}, {"prev": payload}
        )
        assert isinstance(out, ValidationResult)
        assert spy.calls == [payload]

    def test_urn(self, registry: ComponentRegistry) -> None:
        spy = URNSpy()
        registry.register("u", spy)
        payload = {"tipo": "lei"}
        out = StageExecutor(registry).execute(
            {"id": "s", "component": "u", "input": "prev"}, {"prev": payload}
        )
        assert out == "urn:mca:solo:1"
        assert spy.calls == [payload]


# ===========================================================================
# 6.3 Deteccao de Ciclos e Dependencias Invalidas
# ===========================================================================


class TestTopologicalSorterCiclos:
    """6.3 - Falha explicita em ciclos (TOPO-02)."""

    def test_auto_ciclo(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            TopologicalSorter.sort([{"id": "a", "depends_on": ["a"]}])
        assert exc.value.context["rule"] == "TOPO-02"
        assert exc.value.context["cycle"] == ["a", "a"]

    def test_ciclo_de_dois_nos(self) -> None:
        tasks = [
            {"id": "a", "depends_on": ["b"]},
            {"id": "b", "depends_on": ["a"]},
        ]
        with pytest.raises(ConfigurationError) as exc:
            TopologicalSorter.sort(tasks)
        assert exc.value.context["rule"] == "TOPO-02"
        assert exc.value.context["cycle"][0] == exc.value.context["cycle"][-1]

    def test_ciclo_de_tres_nos(self) -> None:
        tasks = [
            {"id": "a", "depends_on": ["c"]},
            {"id": "b", "depends_on": ["a"]},
            {"id": "c", "depends_on": ["b"]},
        ]
        with pytest.raises(ConfigurationError) as exc:
            TopologicalSorter.sort(tasks)
        assert len(exc.value.context["cycle"]) == 4

    def test_ciclo_parcial_com_no_valido(self) -> None:
        tasks = [
            {"id": "ok"},
            {"id": "a", "depends_on": ["b"]},
            {"id": "b", "depends_on": ["a"]},
        ]
        with pytest.raises(ConfigurationError) as exc:
            TopologicalSorter.sort(tasks)
        assert exc.value.context["rule"] == "TOPO-02"

    def test_mensagem_contem_trilha(self) -> None:
        with pytest.raises(ConfigurationError, match="Ciclo detectado"):
            TopologicalSorter.sort([{"id": "a", "depends_on": ["a"]}])


class TestTopologicalSorterDependenciasInvalidas:
    """6.3 - Dependencia inexistente (TOPO-01)."""

    def test_dependencia_fantasma(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            TopologicalSorter.sort([{"id": "a", "depends_on": ["ghost"]}])
        assert exc.value.context["rule"] == "TOPO-01"
        assert exc.value.context["unknown"] == ["ghost"]
        assert exc.value.context["task_id"] == "a"

    def test_multiplas_dependencias_fantasma(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            TopologicalSorter.sort([{"id": "a", "depends_on": ["g1", "g2"]}])
        assert exc.value.context["unknown"] == ["g1", "g2"]


class TestDetectCycle:
    """6.3 - API nao-lancante de deteccao de ciclo."""

    def test_retorna_none_se_aciclico(self) -> None:
        assert TopologicalSorter.detect_cycle([{"id": "a"}]) is None

    def test_retorna_ciclo(self) -> None:
        cycle = TopologicalSorter.detect_cycle([{"id": "a", "depends_on": ["a"]}])
        assert cycle == ["a", "a"]

    def test_propaga_erro_de_dependencia_inexistente(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            TopologicalSorter.detect_cycle([{"id": "a", "depends_on": ["ghost"]}])
        assert exc.value.context["rule"] == "TOPO-01"


class TestOrchestratorCicloEmRuntime:
    """6.3 - Defesa em profundidade: ciclo detectado mesmo pos-parser."""

    def test_ciclo_produz_resultado_failed(self, orchestrator: Orchestrator) -> None:
        dag = make_dag(
            stages=[
                {"id": "s1", "component": "f", "depends_on": ["s2"]},
                {"id": "s2", "component": "f", "depends_on": ["s1"]},
            ]
        )
        result = orchestrator.execute_definition(dag)
        assert result.status is ExecutionStatus.FAILED
        assert result.has_errors is True
        assert result.errors[0]["context"]["rule"] == "TOPO-02"
        assert result.stage_results == {}

    def test_dependencia_inexistente_produz_failed(
        self, orchestrator: Orchestrator
    ) -> None:
        dag = make_dag(
            stages=[{"id": "s1", "component": "f", "depends_on": ["ghost"]}]
        )
        result = orchestrator.execute_definition(dag)
        assert result.status is ExecutionStatus.FAILED
        assert result.errors[0]["context"]["rule"] == "TOPO-01"


# ===========================================================================
# 6.4 Propagacao de Dados entre Estagios
# ===========================================================================


class TestPropagacaoDeDados:
    """6.4 - Semantica Pipeline/Filter."""

    def test_output_alias_disponivel_no_contexto(
        self, orchestrator: Orchestrator, fetch_result: Any
    ) -> None:
        orchestrator.register_component("f", FetcherSpy(fetch_result))
        orchestrator.register_component("t", TransformerSpy("transformed"))
        dag = make_dag(
            stages=[
                {"id": "s1", "component": "f", "output": "raw"},
                {"id": "s2", "component": "t", "input": "raw", "depends_on": ["s1"]},
            ]
        )
        result = orchestrator.execute_definition(dag)
        assert result.status is ExecutionStatus.SUCCESS
        assert result.stage_results["raw"] is fetch_result
        assert result.stage_results["s2"] == "transformed"

    def test_input_por_stage_id(
        self, orchestrator: Orchestrator, fetch_result: Any
    ) -> None:
        transformer = TransformerSpy("t-out")
        orchestrator.register_component("f", FetcherSpy(fetch_result))
        orchestrator.register_component("t", transformer)
        dag = make_dag(
            stages=[
                {"id": "s1", "component": "f"},
                {"id": "s2", "component": "t", "input": "s1", "depends_on": ["s1"]},
            ]
        )
        orchestrator.execute_definition(dag)
        assert transformer.calls == [fetch_result]

    def test_pipeline_completo_fetch_transform_ingest(
        self, orchestrator: Orchestrator, fetch_result: Any
    ) -> None:
        transformed = MagicMock(spec=FetchResult)
        ingest = IngestSpy()
        orchestrator.register_component("f", FetcherSpy(fetch_result))
        orchestrator.register_component("t", TransformerSpy(transformed))
        orchestrator.register_component("i", ingest)
        dag = make_dag(
            stages=[
                {"id": "fetch", "component": "f", "output": "raw"},
                {
                    "id": "transform",
                    "component": "t",
                    "input": "raw",
                    "output": "clean",
                    "depends_on": ["fetch"],
                },
                {
                    "id": "ingest",
                    "component": "i",
                    "input": "clean",
                    "depends_on": ["transform"],
                },
            ]
        )
        result = orchestrator.execute_definition(dag)
        assert result.status is ExecutionStatus.SUCCESS
        assert ingest.calls == [transformed]
        assert result.errors == []

    def test_input_ausente_no_contexto_gera_erro_de_tipo(
        self, orchestrator: Orchestrator
    ) -> None:
        orchestrator.register_component("t", TransformerSpy("x"))
        dag = make_dag(stages=[{"id": "s1", "component": "t", "input": "missing"}])
        result = orchestrator.execute_definition(dag)
        assert result.status is ExecutionStatus.FAILED
        assert result.errors[0]["context"]["rule"] == "EXEC-02"


# ===========================================================================
# 6.5 Resolucao de Componentes (Registro)
# ===========================================================================


class TestComponentRegistry:
    """6.5 - Ciclo de vida do registro."""

    def test_get_retorna_mesma_instancia(self, registry: ComponentRegistry) -> None:
        spy = FetcherSpy(FetchResult(items=[]))
        registry.register("f", spy)
        assert registry.get("f") is spy

    def test_has(self, registry: ComponentRegistry) -> None:
        assert registry.has("f") is False
        registry.register("f", FetcherSpy(FetchResult(items=[])))
        assert registry.has("f") is True

    def test_list_preserva_ordem_de_registro(
        self, registry: ComponentRegistry
    ) -> None:
        registry.register("b", FetcherSpy(FetchResult(items=[])))
        registry.register("a", IngestSpy())
        assert registry.list() == ["b", "a"]

    def test_list_vazio(self, registry: ComponentRegistry) -> None:
        assert registry.list() == []

    def test_duplicado_reg01(self, registry: ComponentRegistry) -> None:
        registry.register("f", FetcherSpy(FetchResult(items=[])))
        with pytest.raises(ConfigurationError) as exc:
            registry.register("f", FetcherSpy(FetchResult(items=[])))
        assert exc.value.context["rule"] == "REG-01"
        assert exc.value.context["component_id"] == "f"

    def test_duplicado_nao_sobrescreve(self, registry: ComponentRegistry) -> None:
        original = FetcherSpy(FetchResult(items=[]))
        registry.register("f", original)
        with pytest.raises(ConfigurationError):
            registry.register("f", FetcherSpy(FetchResult(items=[])))
        assert registry.get("f") is original

    def test_nao_porta_reg02(self, registry: ComponentRegistry) -> None:
        with pytest.raises(ConfigurationError) as exc:
            registry.register("obj", object())
        assert exc.value.context["rule"] == "REG-02"
        assert exc.value.context["type"] == "object"

    def test_classe_nao_instancia_rejeitada(
        self, registry: ComponentRegistry
    ) -> None:
        with pytest.raises(ConfigurationError) as exc:
            registry.register("cls", FetcherSpy)
        assert exc.value.context["rule"] == "REG-02"

    def test_get_inexistente_reg03(self, registry: ComponentRegistry) -> None:
        with pytest.raises(ConfigurationError) as exc:
            registry.get("ghost")
        assert exc.value.context["rule"] == "REG-03"

    def test_orchestrator_delega_registro(self, orchestrator: Orchestrator) -> None:
        spy = FetcherSpy(FetchResult(items=[]))
        orchestrator.register_component("f", spy)
        assert orchestrator._registry.get("f") is spy

    def test_orchestrator_aceita_registry_injetado(
        self, registry: ComponentRegistry
    ) -> None:
        spy = FetcherSpy(FetchResult(items=[]))
        registry.register("f", spy)
        orch = Orchestrator(registry=registry)
        assert orch._registry is registry

    def test_orchestrator_cria_registry_proprio(self) -> None:
        assert isinstance(Orchestrator()._registry, ComponentRegistry)


# ===========================================================================
# 6.6 Falha Explicita (Edge Cases)
# ===========================================================================


class TestFalhaExplicita:
    """6.6 - Nenhuma violacao e silenciada."""

    def test_dag_inexistente_orch01(self, orchestrator: Orchestrator) -> None:
        with pytest.raises(ConfigurationError) as exc:
            orchestrator.execute_dag("ghost", {})
        assert exc.value.context["rule"] == "ORCH-01"
        assert exc.value.context["dag_id"] == "ghost"

    def test_dag_sem_pipeline_nem_tasks_orch02(
        self, orchestrator: Orchestrator
    ) -> None:
        with pytest.raises(ConfigurationError) as exc:
            orchestrator.execute_definition(make_dag())
        assert exc.value.context["rule"] == "ORCH-02"

    def test_componente_nao_registrado_interrompe(
        self, orchestrator: Orchestrator, fetch_result: Any
    ) -> None:
        orchestrator.register_component("f", FetcherSpy(fetch_result))
        dag = make_dag(
            stages=[
                {"id": "s1", "component": "f"},
                {"id": "s2", "component": "ghost", "depends_on": ["s1"]},
            ]
        )
        result = orchestrator.execute_definition(dag)
        assert result.status is ExecutionStatus.FAILED
        assert result.errors[0]["stage_id"] == "s2"
        assert result.errors[0]["context"]["rule"] == "REG-03"
        assert "s2" not in result.stage_results

    def test_excecao_do_componente_preserva_contexto(
        self, orchestrator: Orchestrator
    ) -> None:
        orchestrator.register_component("boom", ExplodingFetcher())
        dag = make_dag(stages=[{"id": "s1", "component": "boom"}])
        result = orchestrator.execute_definition(dag)
        assert result.status is ExecutionStatus.FAILED
        assert result.errors[0]["context"]["rule"] == "TEST-01"
        assert "falha na origem" in result.errors[0]["error"]

    def test_falha_interrompe_estagios_subsequentes(
        self, orchestrator: Orchestrator, fetch_result: Any
    ) -> None:
        downstream = FetcherSpy(fetch_result)
        orchestrator.register_component("boom", ExplodingFetcher())
        orchestrator.register_component("next", downstream)
        dag = make_dag(
            stages=[
                {"id": "s1", "component": "boom"},
                {"id": "s2", "component": "next", "depends_on": ["s1"]},
            ]
        )
        result = orchestrator.execute_definition(dag)
        assert downstream.calls == []
        assert result.status is ExecutionStatus.FAILED

    @pytest.mark.parametrize(
        ("component", "payload", "rule"),
        [
            (IngestSpy(), "not-a-fetch-result", "EXEC-01"),
            (TransformerSpy("x"), {"a": 1}, "EXEC-02"),
            (ValidatorSpy(), "not-a-list", "EXEC-03"),
            (URNSpy(), ["not", "a", "dict"], "EXEC-04"),
        ],
        ids=["ingest", "transformer", "validator", "urn"],
    )
    def test_input_incompativel(
        self,
        orchestrator: Orchestrator,
        component: Any,
        payload: Any,
        rule: str,
    ) -> None:
        orchestrator.register_component("c", component)
        dag = make_dag(
            stages=[{"id": "s1", "component": "c", "input": "prev"}]
        )
        # Injeta o payload invalido via estagio produtor literal.
        executor = StageExecutor(orchestrator._registry)
        with pytest.raises(ConfigurationError) as exc:
            executor.execute(
                {"id": "s1", "component": "c", "input": "prev"}, {"prev": payload}
            )
        assert exc.value.context["rule"] == rule
        assert exc.value.context["stage_id"] == "s1"
        assert orchestrator.execute_definition(dag).status is ExecutionStatus.FAILED

    def test_toda_excecao_e_framework_error(
        self, registry: ComponentRegistry
    ) -> None:
        with pytest.raises(FrameworkError):
            registry.get("ghost")

    def test_excecao_carrega_contexto_estruturado(
        self, registry: ComponentRegistry
    ) -> None:
        with pytest.raises(FrameworkError) as exc:
            registry.register("obj", object())
        assert isinstance(exc.value.context, dict)
        assert {"component_id", "type", "rule"} <= set(exc.value.context)


# ===========================================================================
# 6.7 Integracao com DAGDefinition
# ===========================================================================


class TestIntegracaoDAGDefinition:
    """6.7 - Core DAG vs App DAG e integracao com DAGParser (ID 1.4)."""

    def test_core_dag_nao_executa_componentes(
        self, orchestrator: Orchestrator
    ) -> None:
        dag = make_dag(
            dag_id="core_observability",
            tasks=[{"id": "t1", "component": "management.metrics"}],
        )
        result = orchestrator.execute_definition(dag)
        assert result.status is ExecutionStatus.SUCCESS
        assert result.stage_results == {}
        assert result.errors == []
        assert result.dag_id == "core_observability"

    def test_pipeline_tem_precedencia_sobre_tasks(
        self, orchestrator: Orchestrator, fetch_result: Any
    ) -> None:
        orchestrator.register_component("f", FetcherSpy(fetch_result))
        dag = cast(
            Any,
            _DAGStub(
                id="app_mixed",
                pipeline={"stages": [{"id": "s1", "component": "f"}]},
                tasks=[{"id": "t1", "component": "management.metrics"}],
            ),
        )
        result = orchestrator.execute_definition(dag)
        assert set(result.stage_results) == {"s1"}

    def test_execute_dag_resolve_por_id(
        self, orchestrator: Orchestrator, fetch_result: Any
    ) -> None:
        orchestrator.register_component("f", FetcherSpy(fetch_result))
        dags = {"app_x": make_dag("app_x", stages=[{"id": "s1", "component": "f"}])}
        result = orchestrator.execute_dag("app_x", dags)
        assert result.dag_id == "app_x"
        assert result.status is ExecutionStatus.SUCCESS

    def test_invariancia_sob_substituicao_de_implementacao(
        self, fetch_result: Any
    ) -> None:
        """Regra de Ouro: trocar o adaptador nao altera o motor."""

        class AdapterA(FetcherPort):
            def buscar(self, config: dict[str, Any]) -> FetchResult:
                return fetch_result

            def validar_config(self, config: dict[str, Any]) -> bool:
                return True

            def metadados(self) -> dict[str, Any]:
                return {}

        class AdapterB(FetcherPort):
            def buscar(self, config: dict[str, Any]) -> FetchResult:
                return fetch_result

            def validar_config(self, config: dict[str, Any]) -> bool:
                return True

            def metadados(self) -> dict[str, Any]:
                return {}

        dag = make_dag(stages=[{"id": "s1", "component": "f"}])
        resultados = []
        for adapter in (AdapterA(), AdapterB()):
            orch = Orchestrator()
            orch.register_component("f", adapter)
            resultados.append(orch.execute_definition(dag))

        assert resultados[0].status is resultados[1].status
        assert set(resultados[0].stage_results) == set(resultados[1].stage_results)

    @pytest.mark.integration
    def test_integra_com_dag_parser(self, tmp_path: Path) -> None:
        """Integracao real ID 1.4 + ID 2.1 via YAML em diretorio temporario."""
        from framework.execution.parser import DAGParser

        yaml_content = (
            "dag:\n"
            "  id: app_integration\n"
            "  description: DAG de integracao\n"
            "  schedule: null\n"
            "  owner: dev\n"
            "  immutable: false\n"
            "tasks: []\n"
            "notifications:\n"
            "  on_failure:\n"
            "    - type: log\n"
            "      level: ERROR\n"
            "pipeline:\n"
            "  stages:\n"
            "    - id: fetch\n"
            "      component: fetcher\n"
            "      output: raw\n"
            "    - id: transform\n"
            "      component: transformer\n"
            "      input: raw\n"
            "      depends_on: [fetch]\n"
        )
        dag_file = tmp_path / "app_integration.yaml"
        dag_file.write_text(yaml_content, encoding="utf-8")

        parser = DAGParser(str(tmp_path), str(tmp_path))
        dag = parser.parse_file(dag_file)

        orch = Orchestrator()
        orch.register_component("fetcher", FetcherSpy(MagicMock(spec=FetchResult)))
        orch.register_component("transformer", TransformerSpy("clean"))
        result = orch.execute_definition(dag)

        assert result.dag_id == "app_integration"
        assert result.status is ExecutionStatus.SUCCESS
        assert result.stage_results["transform"] == "clean"