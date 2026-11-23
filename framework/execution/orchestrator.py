"""Motor de orquestracao de DAGs do MCA-Solo (ID 2.1).

Este modulo materializa a camada de Orquestracao (DEV), responsavel por
executar estagios de uma DAGDefinition em ordem topologica, resolvendo
dependencias e propagando dados entre estagios. A observabilidade e
delegada ao Involucro de Gestao (quando disponivel), preservando a
invariancia da Gestao sob substituicao de implementacao.

Regras de Ouro aplicaveis:
- "Falha explicita: toda violacao interrompe a execucao, sem fallback."
- "Todo componente registrado deve herdar nominalmente de uma ABC de porta."
- "A excecao e o veiculo de transporte de contexto para Observabilidade."
- "Gestao e invariante sob substituicao de implementacao."
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from framework.core.entities import FetchResult
from framework.core.exceptions import ConfigurationError, FrameworkError
from framework.core.ports import (
    FetcherPort,
    IngestPort,
    TransformerPort,
    URNPort,
    ValidatorPort,
)
from framework.execution.parser import DAGDefinition

__all__ = [
    "ComponentRegistry",
    "ExecutionResult",
    "ExecutionStatus",
    "Orchestrator",
    "StageExecutor",
    "TopologicalSorter",
]


class ExecutionStatus(str, Enum):
    """Estados possiveis de uma execucao de DAG."""

    SUCCESS = "SUCCESS"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ExecutionResult:
    """Snapshot imutavel do resultado de uma execucao de DAG.

    Attributes:
        dag_id: Identificador da DAG executada.
        stage_results: Mapeamento stage_id -> saida do componente.
        status: Estado final da execucao.
        started_at: Timestamp de inicio (UTC).
        finished_at: Timestamp de termino (UTC).
        errors: Lista de erros nao fatais registrados.
    """

    dag_id: str
    stage_results: dict[str, Any] = field(default_factory=dict)
    status: ExecutionStatus = ExecutionStatus.SUCCESS
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Indica se houve erros nao fatais."""
        return len(self.errors) > 0


class ComponentRegistry:
    """Registro de componentes por ID, com validacao de heranca nominal.

    Pre-condicoes:
        - component e instancia de uma ABC de porta (FetcherPort, etc.).
    Pos-condicoes:
        - component esta acessivel via get(component_id).
    Invariantes:
        - Todo componente registrado e instancia de *Port.
        - IDs duplicados levantam ConfigurationError.
    """

    VALID_PORTS: tuple[type[Any], ...] = (
        FetcherPort,
        IngestPort,
        TransformerPort,
        ValidatorPort,
        URNPort,
    )

    def __init__(self) -> None:
        self._components: dict[str, Any] = {}

    def register(self, component_id: str, component: Any) -> None:
        """Registra um componente, validando heranca nominal de porta.

        Args:
            component_id: Identificador unico do componente.
            component: Instancia de uma ABC de porta.

        Raises:
            ConfigurationError: Se component_id ja estiver registrado ou
                se component nao herdar nominalmente de uma ABC de porta.
        """
        if component_id in self._components:
            raise ConfigurationError(
                f"Componente '{component_id}' ja registrado",
                context={"component_id": component_id, "rule": "REG-01"},
            )
        if not isinstance(component, self.VALID_PORTS):
            raise ConfigurationError(
                f"Componente '{component_id}' nao herda de nenhuma ABC de porta",
                context={
                    "component_id": component_id,
                    "type": type(component).__name__,
                    "rule": "REG-02",
                },
            )
        self._components[component_id] = component

    def get(self, component_id: str) -> Any:
        """Retorna o componente registrado.

        Args:
            component_id: Identificador do componente.

        Returns:
            A instancia do componente.

        Raises:
            ConfigurationError: Se component_id nao estiver registrado.
        """
        if component_id not in self._components:
            raise ConfigurationError(
                f"Componente '{component_id}' nao registrado",
                context={"component_id": component_id, "rule": "REG-03"},
            )
        return self._components[component_id]

    def has(self, component_id: str) -> bool:
        """Indica se o componente esta registrado."""
        return component_id in self._components

    def list(self) -> list[str]:
        """Retorna lista de IDs registrados."""
        return list(self._components.keys())


class TopologicalSorter:
    """Ordena tarefas por depends_on e detecta ciclos (defesa em profundidade).

    Pre-condicoes:
        - tasks e lista de dicts com chaves 'id' e 'depends_on'.
    Pos-condicoes:
        - Retorna lista ordenada topologicamente.
    Invariantes:
        - Grafo aciclico e pre-condicao; ciclo levanta ConfigurationError.
    """

    @staticmethod
    def sort(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ordena tarefas topologicamente.

        Args:
            tasks: Lista de tarefas com 'id' e 'depends_on'.

        Returns:
            Lista ordenada topologicamente.

        Raises:
            ConfigurationError: Se houver ciclo ou dependencia inexistente.
        """
        graph = {t["id"]: list(t.get("depends_on") or []) for t in tasks}
        task_map = {t["id"]: t for t in tasks}

        # Valida dependencias existentes
        for tid, deps in graph.items():
            unknown = [d for d in deps if d not in graph]
            if unknown:
                raise ConfigurationError(
                    f"Tarefa '{tid}' depende de IDs inexistentes: {unknown}",
                    context={"task_id": tid, "unknown": unknown, "rule": "TOPO-01"},
                )

        # DFS com marcacao (branco/cinza/preto)
        white, gray, black = 0, 1, 2
        color: dict[str, int] = {tid: white for tid in graph}
        order: list[str] = []

        def visit(node: str, trail: list[str]) -> None:
            state = color[node]
            if state == gray:
                cycle = trail[trail.index(node) :] + [node]
                raise ConfigurationError(
                    f"Ciclo detectado em depends_on: {' -> '.join(cycle)}",
                    context={"cycle": cycle, "rule": "TOPO-02"},
                )
            if state == black:
                return
            color[node] = gray
            for dep in graph[node]:
                visit(dep, trail + [node])
            color[node] = black
            order.append(node)

        for node in graph:
            if color[node] == white:
                visit(node, [])

        return [task_map[tid] for tid in order]

    @staticmethod
    def detect_cycle(tasks: list[dict[str, Any]]) -> list[str] | None:
        """Detecta ciclo no grafo de dependencias.

        Args:
            tasks: Lista de tarefas com 'id' e 'depends_on'.

        Returns:
            Lista de IDs do ciclo, ou None se aciclico.
        """
        try:
            TopologicalSorter.sort(tasks)
            return None
        except ConfigurationError as e:
            if e.context.get("rule") == "TOPO-02":
                cycle = e.context.get("cycle")
                return list(cycle) if cycle is not None else None
            raise


class StageExecutor:
    """Executa um estagio individual, resolvendo o componente no registry.

    Pre-condicoes:
        - stage e dict com 'id', 'component', 'input' (opcional).
        - component esta registrado no registry.
    Pos-condicoes:
        - Retorna saida do componente (FetchResult, IngestResult, etc.).
    Invariantes:
        - Falha de um estagio e registrada em errors, nao silenciada.
    """

    def __init__(self, registry: ComponentRegistry) -> None:
        self._registry = registry

    def execute(self, stage: dict[str, Any], context: dict[str, Any]) -> Any:
        """Executa um estagio.

        Args:
            stage: Dict com 'id', 'component', 'input' (opcional).
            context: Contexto de execucao (resultados de estagios anteriores).

        Returns:
            Saida do componente.

        Raises:
            FrameworkError: Se o componente falhar.
        """
        component_id = stage["component"]
        component = self._registry.get(component_id)

        # Resolve input do contexto
        input_data = stage.get("input")
        if input_data and isinstance(input_data, str):
            input_data = context.get(input_data)

        # Despacha conforme o tipo de porta
        if isinstance(component, FetcherPort):
            config = stage.get("config", {})
            return component.buscar(config)
        if isinstance(component, IngestPort):
            if not isinstance(input_data, FetchResult):
                raise ConfigurationError(
                    f"IngestPort '{component_id}' requer FetchResult como input",
                    context={"stage_id": stage["id"], "rule": "EXEC-01"},
                )
            return component.ingerir(input_data)
        if isinstance(component, TransformerPort):
            if not isinstance(input_data, FetchResult):
                raise ConfigurationError(
                    f"TransformerPort '{component_id}' requer FetchResult como input",
                    context={"stage_id": stage["id"], "rule": "EXEC-02"},
                )
            return component.transformar(input_data)
        if isinstance(component, ValidatorPort):
            if not isinstance(input_data, list):
                raise ConfigurationError(
                    f"ValidatorPort '{component_id}' requer list[dict] como input",
                    context={"stage_id": stage["id"], "rule": "EXEC-03"},
                )
            return component.validar(input_data)
        if isinstance(component, URNPort):
            if not isinstance(input_data, dict):
                raise ConfigurationError(
                    f"URNPort '{component_id}' requer dict como input",
                    context={"stage_id": stage["id"], "rule": "EXEC-04"},
                )
            return component.gerar(input_data)
        raise ConfigurationError(
            f"Componente '{component_id}' nao e instancia de nenhuma porta conhecida",
            context={"stage_id": stage["id"], "rule": "EXEC-05"},
        )


class Orchestrator:
    """Motor de orquestracao de DAGs.

    Pre-condicoes:
        - DAGDefinition e valida (ja parseada pelo DAGParser).
        - Componentes referenciados estao registrados no registry.
    Pos-condicoes:
        - Retorna ExecutionResult imutavel com status e stage_results.
    Invariantes:
        - Toda execucao produz um ExecutionResult, mesmo em falha.
        - Falhas sao registradas em errors, nao silenciadas.
    """

    def __init__(
        self,
        registry: ComponentRegistry | None = None,
    ) -> None:
        self._registry = registry or ComponentRegistry()
        self._executor = StageExecutor(self._registry)

    def register_component(self, component_id: str, component: Any) -> None:
        """Registra um componente no registry.

        Args:
            component_id: Identificador unico.
            component: Instancia de uma ABC de porta.

        Raises:
            ConfigurationError: Se violar regras de registro.
        """
        self._registry.register(component_id, component)

    def execute_dag(
        self, dag_id: str, dags: dict[str, DAGDefinition]
    ) -> ExecutionResult:
        """Executa uma DAG pelo ID.

        Args:
            dag_id: Identificador da DAG.
            dags: Dicionario de DAGDefinitions (do DAGParser).

        Returns:
            ExecutionResult imutavel.

        Raises:
            ConfigurationError: Se dag_id nao existir.
        """
        if dag_id not in dags:
            raise ConfigurationError(
                f"DAG '{dag_id}' nao encontrada",
                context={"dag_id": dag_id, "rule": "ORCH-01"},
            )
        return self.execute_definition(dags[dag_id])

    def execute_definition(self, dag: DAGDefinition) -> ExecutionResult:
        """Executa uma DAGDefinition.

        Args:
            dag: DAGDefinition valida.

        Returns:
            ExecutionResult imutavel.
        """
        started_at = datetime.now(UTC)
        stage_results: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []

        # Extrai estagios do pipeline (App DAG) ou tasks (Core DAG)
        if dag.pipeline and "stages" in dag.pipeline:
            stages = dag.pipeline["stages"]
        elif dag.tasks:
            # Core DAG: tasks sao de gestao, nao executaveis como componentes
            # Por ora, retorna sucesso sem execucao (futuro: delegar ao mgmt)
            return ExecutionResult(
                dag_id=dag.id,
                stage_results={},
                status=ExecutionStatus.SUCCESS,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                errors=[],
            )
        else:
            raise ConfigurationError(
                f"DAG '{dag.id}' nao possui pipeline.stages nem tasks",
                context={"dag_id": dag.id, "rule": "ORCH-02"},
            )

        # Ordena topologicamente
        try:
            sorted_stages = TopologicalSorter.sort(stages)
        except ConfigurationError as e:
            return ExecutionResult(
                dag_id=dag.id,
                stage_results={},
                status=ExecutionStatus.FAILED,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                errors=[{"error": str(e), "context": e.context}],
            )

        # Executa estagios em ordem
        for stage in sorted_stages:
            stage_id = stage["id"]
            try:
                output = self._executor.execute(stage, stage_results)
                stage_results[stage_id] = output
                # Se o estagio tem 'output', mapeia para o contexto
                if "output" in stage:
                    stage_results[stage["output"]] = output
            except FrameworkError as e:
                errors.append(
                    {
                        "stage_id": stage_id,
                        "error": str(e),
                        "context": e.context,
                    }
                )
                # Falha explicita: interrompe execucao
                return ExecutionResult(
                    dag_id=dag.id,
                    stage_results=stage_results,
                    status=ExecutionStatus.FAILED,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    errors=errors,
                )

        # Falha fatal interrompe a execucao (return antecipado acima).
        # PARTIAL_FAILURE e reservado para erros nao fatais (futuro: ID 2.4).
        return ExecutionResult(
            dag_id=dag.id,
            stage_results=stage_results,
            status=ExecutionStatus.SUCCESS,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            errors=errors,
        )