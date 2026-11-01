"""Testes dos Core DAGs (Artefatos Imutaveis de Gestao) — Especificacao 1.4.

Cobertura da Estrategia de Testes da Secao 6 da Especificacao Tecnica ID 1.4:
    6.1. Existencia e localizacao (fechamento do conjunto em
         ``framework/core/dags/``).
    6.2. Schema YAML (chaves top-level ``dag``/``tasks``/``notifications`` e
         sub-chaves obrigatorias de ``dag``).
    6.3. Propriedades invariantes (``immutable is True``,
         ``owner == "framework"``, prefixo ``core_``).
    6.4. Disjuncao de IDs entre Core e App DAGs (VAL-08).
    6.5. Aciclicidade do grafo ``depends_on`` (VAL-06; DFS proprio + networkx
         quando disponivel).
    6.6. Tipos de tarefa ``management.*`` (VAL-07, Secao 4.7).
    6.7. Notificacoes (``on_failure`` obrigatorio; canais em
         {log, alert, webhook}).
    6.8. Integracao com o parser unificado (``DAGParser.parse_all()`` /
         ``get_core_dags()``).
    6.9. Falha explicita (testes negativos: immutable=false, id sem prefixo,
         ciclo em depends_on, owner divergente, tipos proibidos).

Critérios de Conformidade mapeados (Secao 5.3):
    - CC-01 -> ``TestPropriedadesInvariantes`` + ``TestIntegracaoParser``
    - CC-02 -> ``TestExistenciaLocalizacao``
    - CC-03 -> ``TestConformidadeInfraestrutura.test_montagem_read_only``
    - CC-04 -> ``TestTiposDeTarefa`` (vocabulario exclusivo ``management.*``)
    - CC-05 -> ``TestDisjuncaoDeIds`` + negativo de sobrescrita

Execucao:
    pytest tests/framework/test_core_dags.py -v
    pytest --cov=framework.execution.parser --cov-report=term-missing
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pytest
import yaml

from framework.core.exceptions import ConfigurationError
from framework.execution.parser import (
    CORE_DAG_PREFIX,
    CORE_OWNER,
    MANAGEMENT_TASK_TYPES,
    NOTIFICATION_CHANNELS,
    DAGDefinition,
    DAGParser,
)

# ---------------------------------------------------------------------------
# Constantes estruturais (fonte unica para testes parametrizados)
# ---------------------------------------------------------------------------

#: Raiz do repositorio (diretorio que contem ``pytest.ini``).
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

#: Diretorio das Core DAGs (imutaveis pelo DEV — VAL-04/CC-02).
CORE_DAGS_DIR: Path = PROJECT_ROOT / "framework" / "core" / "dags"

#: Diretorio das App DAGs (composicao do DEV).
APP_DAGS_DIR: Path = PROJECT_ROOT / "application" / "dags"

#: Conjunto fechado das quatro Core DAGs exigidas pela Issue 1.4.
EXPECTED_CORE_DAG_FILES: Tuple[str, ...] = (
    "metrics_collection.yaml",
    "health_check.yaml",
    "component_lifecycle.yaml",
    "alerting.yaml",
)

#: Mapa arquivo -> id esperado (espaco de nomes ``core_*``).
EXPECTED_IDS: Dict[str, str] = {
    "metrics_collection.yaml": "core_metrics_collection",
    "health_check.yaml": "core_health_check",
    "component_lifecycle.yaml": "core_component_lifecycle",
    "alerting.yaml": "core_alerting",
}

#: Mapa arquivo -> schedule esperado (Secoes 4.3 a 4.6).
EXPECTED_SCHEDULES: Dict[str, Any] = {
    "metrics_collection.yaml": "*/1 * * * *",
    "health_check.yaml": "*/5 * * * *",
    "component_lifecycle.yaml": None,  # event-driven
    "alerting.yaml": "*/2 * * * *",
}

#: Chaves top-level obrigatorias (Secao 4.1, item 1).
REQUIRED_TOP_KEYS: Tuple[str, ...] = ("dag", "tasks", "notifications")

#: Sub-chaves obrigatorias de ``dag`` (Secao 4.1, item 2).
REQUIRED_DAG_KEYS: Tuple[str, ...] = (
    "id",
    "description",
    "schedule",
    "owner",
    "immutable",
)

#: Chaves exclusivas de App DAGs — proibidas em Core DAGs (Secao 4.1, item 8).
FORBIDDEN_CORE_KEYS: Tuple[str, ...] = ("components", "pipeline")

#: Manifestos inspecionados para o criterio CC-03 (montagem ``:ro``).
DEPLOYMENT_MANIFESTS: Tuple[str, ...] = (
    "deployment/docker-compose.yml",
    "deployment/kubernetes/configmaps.yaml",
    "framework/infrastructure/docker-compose.framework.yml",
    "application/config/docker-compose.app.yml",
)


# ---------------------------------------------------------------------------
# Auxiliares puros
# ---------------------------------------------------------------------------


def _core_paths() -> List[Path]:
    """Lista ordenada os quatro arquivos de Core DAGs esperados."""
    return [CORE_DAGS_DIR / name for name in EXPECTED_CORE_DAG_FILES]


def _load(path: Path) -> Dict[str, Any]:
    """Carrega um YAML de teste com ``safe_load`` e exige mapeamento na raiz."""
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict), f"{path.name}: raiz deve ser mapeamento"
    return data


def _dependency_graph(document: Dict[str, Any]) -> Dict[str, List[str]]:
    """Constrói o grafo ``tarefa -> dependencias`` a partir de ``depends_on``."""
    graph: Dict[str, List[str]] = {}
    for task in document.get("tasks", []):
        graph[task["id"]] = list(task.get("depends_on") or [])
    return graph


def _has_cycle(graph: Dict[str, List[str]]) -> bool:
    """Detecta ciclo em grafo dirigido via DFS com marcacao (branco/cinza/preto).

    Args:
        graph: Adjacencia ``no -> lista de nos dependentes``.

    Returns:
        ``True`` se houver ao menos um ciclo.
    """
    white, gray, black = 0, 1, 2
    color: Dict[str, int] = {node: white for node in graph}

    def visit(node: str) -> bool:
        if color[node] == gray:
            return True
        if color[node] == black:
            return False
        color[node] = gray
        for dep in graph.get(node, []):
            if dep in color and visit(dep):
                return True
        color[node] = black
        return False

    return any(color[node] == white and visit(node) for node in graph)


def _valid_core_document(dag_id: str = "core_ok") -> Dict[str, Any]:
    """Retorna um documento de Core DAG valido para mutacoes em testes.

    Args:
        dag_id: Identificador inicial (sempre com prefixo ``core_``).

    Returns:
        Documento novo (nunca compartilhado entre chamadas).
    """
    return {
        "dag": {
            "id": dag_id,
            "description": "Core DAG sintetica de teste",
            "schedule": "*/1 * * * *",
            "owner": CORE_OWNER,
            "immutable": True,
        },
        "tasks": [
            {
                "id": "collect",
                "type": "management.metrics.collect",
                "config": {"aggregation_window": 60},
            }
        ],
        "notifications": {"on_failure": [{"type": "log", "level": "ERROR"}]},
    }


def _write_yaml(path: Path, document: Dict[str, Any]) -> None:
    """Serializa um documento YAML em disco (UTF-8, sem reordenação)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=True)


def _make_parser(tmp_path: Path, core_docs: Dict[str, Dict[str, Any]]) -> DAGParser:
    """Escreve documentos YAML em diretorio temporario e cria o parser.

    Args:
        tmp_path: Diretorio base fornecido pelo fixture ``tmp_path``.
        core_docs: Mapa ``nome_do_arquivo -> documento`` para as Core DAGs.

    Returns:
        Um ``DAGParser`` apontando para os diretorios temporarios.
    """
    core_dir = tmp_path / "core_dags"
    app_dir = tmp_path / "app_dags"
    core_dir.mkdir(parents=True, exist_ok=True)
    app_dir.mkdir(parents=True, exist_ok=True)
    for name, doc in core_docs.items():
        _write_yaml(core_dir / name, doc)
    return DAGParser(str(core_dir), str(app_dir))


# ---------------------------------------------------------------------------
# Inventario carregado uma unica vez (module-level, deterministico)
# ---------------------------------------------------------------------------

CORE_DOCUMENTS: Dict[str, Dict[str, Any]] = {
    name: _load(CORE_DAGS_DIR / name) for name in EXPECTED_CORE_DAG_FILES
}

ALL_FILE_PARAMS: Tuple[Tuple[str, Dict[str, Any]], ...] = tuple(
    (name, CORE_DOCUMENTS[name]) for name in EXPECTED_CORE_DAG_FILES
)

PARAM_IDS: Tuple[str, ...] = tuple(name for name, _ in ALL_FILE_PARAMS)


@pytest.fixture(scope="module")
def parsed_registry() -> Dict[str, DAGDefinition]:
    """Registro unificado produzido pelo parser real do repositorio."""
    parser = DAGParser(str(CORE_DAGS_DIR), str(APP_DAGS_DIR))
    return parser.parse_all()


# ---------------------------------------------------------------------------
# 6.1 Testes de existencia e localizacao
# ---------------------------------------------------------------------------


class TestExistenciaLocalizacao:
    """Secao 6.1 — os quatro arquivos existem e o conjunto e fechado."""

    @pytest.mark.parametrize("name", EXPECTED_CORE_DAG_FILES)
    def test_arquivo_existe(self, name: str) -> None:
        caminho = CORE_DAGS_DIR / name
        assert caminho.is_file(), f"Core DAG ausente: {caminho}"
        assert caminho.stat().st_size > 0, f"Core DAG vazia: {caminho}"

    def test_diretorio_e_o_esperado(self) -> None:
        """CC-02/VAL-04: residem exatamente em framework/core/dags/."""
        assert CORE_DAGS_DIR.is_dir()
        assert CORE_DAGS_DIR.parts[-3:] == ("framework", "core", "dags")

    def test_fechamento_do_conjunto(self) -> None:
        """Nenhum outro YAML existe no diretorio de Core DAGs."""
        presentes = sorted(p.name for p in CORE_DAGS_DIR.glob("*.yaml"))
        assert presentes == sorted(EXPECTED_CORE_DAG_FILES)
        assert not list(CORE_DAGS_DIR.glob("*.yml"))

    def test_nenhum_core_dag_em_application_dags(self) -> None:
        """Separacao fisica: App DAGs jamais declaram imutabilidade."""
        for path in APP_DAGS_DIR.glob("*.yaml"):
            texto = path.read_text(encoding="utf-8")
            assert "immutable: true" not in texto, (
                f"App DAG {path.name} declara immutable: true"
            )

    def test_lista_de_caminhos_auxiliar(self) -> None:
        assert len(_core_paths()) == 4
        assert all(p.suffix == ".yaml" for p in _core_paths())


# ---------------------------------------------------------------------------
# 6.2 Testes de schema YAML
# ---------------------------------------------------------------------------


class TestSchemaYaml:
    """Secao 6.2 — parse YAML e chaves obrigatorias (VAL-05)."""

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_chaves_top_level(self, name: str, document: Dict[str, Any]) -> None:
        for key in REQUIRED_TOP_KEYS:
            assert key in document, f"{name}: chave top-level '{key}' ausente"

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_sub_chaves_de_dag(self, name: str, document: Dict[str, Any]) -> None:
        dag_meta = document["dag"]
        assert isinstance(dag_meta, dict)
        for key in REQUIRED_DAG_KEYS:
            assert key in dag_meta, f"{name}: dag.{key} ausente"

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_tasks_sao_lista_de_mapas(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        tasks = document["tasks"]
        assert isinstance(tasks, list) and tasks, (
            f"{name}: tasks deve ser lista nao vazia"
        )
        for task in tasks:
            assert isinstance(task, dict)
            for key in ("id", "type", "config"):
                assert key in task, f"{name}: tarefa {task} sem chave '{key}'"

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_notifications_e_mapa(self, name: str, document: Dict[str, Any]) -> None:
        notifications = document["notifications"]
        assert isinstance(notifications, dict)
        permitidos = {"on_failure", "on_success", "on_warning", "on_alert"}
        assert set(notifications) <= permitidos, (
            f"{name}: evento de notificacao fora do contrato"
        )

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_sem_chaves_exclusivas_de_app_dag(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        """Secao 4.1 item 8: Core DAGs nao declaram components/pipeline."""
        for key in FORBIDDEN_CORE_KEYS:
            assert key not in document, f"{name}: chave proibida '{key}' presente"

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_id_corresponde_ao_esperado(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        assert document["dag"]["id"] == EXPECTED_IDS[name]

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_schedule_corresponde_ao_esperado(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        assert document["dag"]["schedule"] == EXPECTED_SCHEDULES[name]

    def test_component_lifecycle_event_driven_com_triggers(self) -> None:
        """Secao 4.5: unico Core DAG com ``triggers`` e ``schedule: null``."""
        document = CORE_DOCUMENTS["component_lifecycle.yaml"]
        assert document["dag"]["schedule"] is None
        triggers = document["triggers"]
        assert isinstance(triggers, list) and len(triggers) == 3
        eventos = {t["event"] for t in triggers}
        assert eventos == {
            "component.start_requested",
            "component.stop_requested",
            "component.restart_requested",
        }
        tarefas = {t["id"] for t in document["tasks"]}
        for trigger in triggers:
            assert trigger["task"] in tarefas

    def test_triggers_apenas_em_component_lifecycle(self) -> None:
        for name in EXPECTED_CORE_DAG_FILES:
            if name == "component_lifecycle.yaml":
                continue
            assert "triggers" not in CORE_DOCUMENTS[name], (
                f"{name}: bloco 'triggers' so e permitido em component_lifecycle"
            )


# ---------------------------------------------------------------------------
# 6.3 Testes de propriedades invariantes
# ---------------------------------------------------------------------------


class TestPropriedadesInvariantes:
    """Secao 6.3 — imutabilidade, propriedade e espaco de nomes (CC-01)."""

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_immutable_e_booleano_true(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        immutable = document["dag"]["immutable"]
        assert immutable is True, f"{name}: dag.immutable deve ser True literal"

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_owner_e_framework(self, name: str, document: Dict[str, Any]) -> None:
        assert document["dag"]["owner"] == CORE_OWNER, (
            f"{name}: dag.owner deve ser 'framework'"
        )

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_id_tem_prefixo_core(self, name: str, document: Dict[str, Any]) -> None:
        assert document["dag"]["id"].startswith(CORE_DAG_PREFIX), (
            f"{name}: dag.id deve comecar com 'core_'"
        )

    def test_ids_sao_unicos_no_conjunto(self) -> None:
        ids = [doc["dag"]["id"] for doc in CORE_DOCUMENTS.values()]
        assert len(ids) == len(set(ids)) == 4

    def test_cobertura_das_quatro_capacidades(self) -> None:
        """Secao 3.1: observabilidade, disponibilidade, controle e reacao."""
        capacidades = set()
        for document in CORE_DOCUMENTS.values():
            for task in document["tasks"]:
                capacidades.add(task["type"].split(".")[1])
        assert capacidades == {"metrics", "health", "lifecycle", "alerting"}


# ---------------------------------------------------------------------------
# 6.4 Testes de disjuncao de IDs
# ---------------------------------------------------------------------------


class TestDisjuncaoDeIds:
    """Secao 6.4 — intersecao vazia entre espacos core/app (VAL-08/CC-05)."""

    @staticmethod
    def _app_ids() -> Set[str]:
        """Coleta ids declarados nas App DAGs (ignora arquivos vazios)."""
        ids: Set[str] = set()
        for path in APP_DAGS_DIR.glob("*.yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("dag"), dict):
                dag_id = data["dag"].get("id")
                if isinstance(dag_id, str):
                    ids.add(dag_id)
        return ids

    def test_intersecao_vazia(self) -> None:
        core_ids = {doc["dag"]["id"] for doc in CORE_DOCUMENTS.values()}
        assert core_ids & self._app_ids() == set()

    def test_app_dags_nao_usam_prefixo_core(self) -> None:
        """Espaco ``core_*`` e reservado: App DAGs jamais o assumem."""
        for dag_id in self._app_ids():
            assert not dag_id.startswith(CORE_DAG_PREFIX)

    def test_app_dags_vazias_para_issue_1_5(self) -> None:
        """Os YAMLs de aplicacao seguem vazios (escopo da Issue 1.5)."""
        for path in APP_DAGS_DIR.glob("*.yaml"):
            assert path.stat().st_size == 0, (
                f"{path.name} preenchido fora do escopo da Issue 1.4"
            )


# ---------------------------------------------------------------------------
# 6.5 Testes de aciclicidade
# ---------------------------------------------------------------------------


class TestAciclicidade:
    """Secao 6.5 — grafo ``depends_on`` acíclico (VAL-06/CO-01)."""

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_grafo_aciclico_por_dfs(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        graph = _dependency_graph(document)
        assert not _has_cycle(graph), f"{name}: ciclo detectado em depends_on"

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_dependencias_existem(self, name: str, document: Dict[str, Any]) -> None:
        graph = _dependency_graph(document)
        known: Set[str] = set(graph)
        for task_id, deps in graph.items():
            unknown = [dep for dep in deps if dep not in known]
            assert not unknown, f"{name}: tarefa {task_id} depende de {unknown}"

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_ordem_topologica_respeita_lista(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        """Dependencias devem preceder a tarefa na lista ordenada de ``tasks``."""
        order = {task["id"]: idx for idx, task in enumerate(document["tasks"])}
        for task_id, deps in _dependency_graph(document).items():
            for dep in deps:
                assert order[dep] < order[task_id], (
                    f"{name}: dependencia {dep} declarada depois de {task_id}"
                )

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_aciclicidade_via_networkx(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        """Reconfirmacao independente com networkx quando instalado."""
        nx = pytest.importorskip("networkx")
        graph = nx.DiGraph()
        for task in document["tasks"]:
            graph.add_node(task["id"])
            for dep in task.get("depends_on") or []:
                graph.add_edge(task["id"], dep)
        assert nx.is_directed_acyclic_graph(graph), f"{name}: grafo nao e DAG"

    def test_detector_de_ciclo_e_sensivel(self) -> None:
        """O auxiliar DFS precisa detectar o ciclo que ele pretende impedir."""
        assert _has_cycle({"a": ["b"], "b": ["a"]}) is True
        assert _has_cycle({"a": ["b"], "b": []}) is False


# ---------------------------------------------------------------------------
# 6.6 Testes de tipos de tarefa
# ---------------------------------------------------------------------------


class TestTiposDeTarefa:
    """Secao 6.6 — vocabulario ``management.*`` (VAL-07/CC-04)."""

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_tipos_possuem_prefixo_management(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        for task in document["tasks"]:
            assert task["type"].startswith("management."), (
                f"{name}: tarefa {task['id']} com tipo {task['type']}"
            )

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_tipos_pertencem_ao_conjunto_valido(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        for task in document["tasks"]:
            assert task["type"] in MANAGEMENT_TASK_TYPES, (
                f"{name}: tipo fora do conjunto da Secao 4.7: {task['type']}"
            )

    def test_todos_os_tipos_do_contrato_estao_materializados(self) -> None:
        """A Secao 4.7 define 11 tipos; os quatro DAGs os cobrem integralmente."""
        usados: Set[str] = {
            task["type"] for doc in CORE_DOCUMENTS.values() for task in doc["tasks"]
        }
        assert usados == set(MANAGEMENT_TASK_TYPES)

    def test_contagem_de_tarefas_por_dag(self) -> None:
        contagem = {name: len(doc["tasks"]) for name, doc in CORE_DOCUMENTS.items()}
        assert contagem == {
            "metrics_collection.yaml": 3,
            "health_check.yaml": 4,
            "component_lifecycle.yaml": 3,
            "alerting.yaml": 1,
        }

    def test_ids_de_tarefa_unicos_por_dag(self) -> None:
        for name, document in CORE_DOCUMENTS.items():
            ids = [task["id"] for task in document["tasks"]]
            assert len(ids) == len(set(ids)), f"{name}: ids de tarefa duplicados"


# ---------------------------------------------------------------------------
# 6.7 Testes de notificacoes
# ---------------------------------------------------------------------------


class TestNotificacoes:
    """Secao 6.7 — ``on_failure`` obrigatorio e canais permitidos."""

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_on_failure_presente(self, name: str, document: Dict[str, Any]) -> None:
        on_failure = document["notifications"].get("on_failure")
        assert isinstance(on_failure, list) and on_failure, (
            f"{name}: notificacoes on_failure obrigatorias (falha explicita)"
        )

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_canais_do_conjunto_permitido(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        for evento, canais in document["notifications"].items():
            assert isinstance(canais, list), f"{name}: {evento} deve ser lista"
            for canal in canais:
                assert isinstance(canal, dict) and "type" in canal, (
                    f"{name}: canal malformado em {evento}"
                )
                assert canal["type"] in NOTIFICATION_CHANNELS, (
                    f"{name}: canal '{canal['type']}' nao permitido"
                )

    def test_canais_usados_sao_subconjunto_permittido(self) -> None:
        """Somente {log, alert} aparecem hoje; webhook segue permitido."""
        usados: Set[str] = {
            canal["type"]
            for doc in CORE_DOCUMENTS.values()
            for canais in doc["notifications"].values()
            for canal in canais
        }
        assert usados <= set(NOTIFICATION_CHANNELS)
        assert NOTIFICATION_CHANNELS == frozenset({"log", "alert", "webhook"})

    def test_alerting_declara_on_alert(self) -> None:
        """Secao 4.2: bloco ``on_alert`` e exclusivo de alerting.yaml."""
        assert "on_alert" in CORE_DOCUMENTS["alerting.yaml"]["notifications"]
        for name, document in CORE_DOCUMENTS.items():
            if name == "alerting.yaml":
                continue
            assert "on_alert" not in document["notifications"]


# ---------------------------------------------------------------------------
# 6.8 Testes de integracao com o parser
# ---------------------------------------------------------------------------


class TestIntegracaoParser:
    """Secao 6.8 — carregamento pelo parser unificado (CC-01/CC-09)."""

    def test_parse_all_executa(self, parsed_registry: Dict[str, DAGDefinition]) -> None:
        assert len(parsed_registry) >= 4

    def test_quatro_core_dags_no_registro_unificado(
        self, parsed_registry: Dict[str, DAGDefinition]
    ) -> None:
        for dag_id in EXPECTED_IDS.values():
            assert dag_id in parsed_registry, f"{dag_id} ausente no registro"

    def test_get_core_dags_retorna_exatamente_quatro(self) -> None:
        parser = DAGParser(str(CORE_DAGS_DIR), str(APP_DAGS_DIR))
        parser.parse_all()
        core = parser.get_core_dags()
        assert set(core) == set(EXPECTED_IDS.values())
        assert len(core) == 4

    def test_imutabilidade_preservada_no_objeto(
        self, parsed_registry: Dict[str, DAGDefinition]
    ) -> None:
        for dag_id, dag in parsed_registry.items():
            if dag_id.startswith(CORE_DAG_PREFIX):
                assert dag.immutable is True
                assert dag.owner == CORE_OWNER
                assert dag.is_core is True

    def test_metadados_yaml_preservados(
        self, parsed_registry: Dict[str, DAGDefinition]
    ) -> None:
        dag = parsed_registry["core_metrics_collection"]
        assert dag.description == (
            "Coleta metricas padronizadas de todos os componentes"
        )
        assert dag.schedule == "*/1 * * * *"
        assert [task["id"] for task in dag.tasks] == [
            "collect_component_metrics",
            "aggregate_metrics",
            "expose_metrics_endpoint",
        ]

    def test_schedule_null_event_driven(
        self, parsed_registry: Dict[str, DAGDefinition]
    ) -> None:
        lifecycle = parsed_registry["core_component_lifecycle"]
        assert lifecycle.schedule is None
        assert len(lifecycle.triggers) == 3

    def test_get_app_dags_vazio_ate_issue_1_5(self) -> None:
        parser = DAGParser(str(CORE_DAGS_DIR), str(APP_DAGS_DIR))
        parser.parse_all()
        assert parser.get_app_dags() == {}

    def test_registros_sao_copias_defensivas(self) -> None:
        parser = DAGParser(str(CORE_DAGS_DIR), str(APP_DAGS_DIR))
        parser.parse_all()
        snapshot = parser.get_core_dags()
        snapshot.pop("core_alerting")
        assert "core_alerting" in parser.get_core_dags()

    def test_parse_file_individual(self) -> None:
        parser = DAGParser(str(CORE_DAGS_DIR), str(APP_DAGS_DIR))
        dag = parser.parse_file(CORE_DAGS_DIR / "health_check.yaml")
        assert dag.id == "core_health_check"
        assert len(dag.tasks) == 4
        assert dag.components == [] and dag.pipeline == {}


# ---------------------------------------------------------------------------
# 6.9 Testes de falha explicita (negativos)
# ---------------------------------------------------------------------------


class TestFalhaExplicita:
    """Secao 6.9 — violacoes interrompem o carregamento com ValueError."""

    def test_immutable_false_rejeitado(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["dag"]["immutable"] = False
        parser = _make_parser(tmp_path, {"bad_immutable.yaml": doc})
        with pytest.raises(ValueError) as excinfo:
            parser.parse_all()
        assert "immutable=true" in str(excinfo.value)
        assert isinstance(excinfo.value, ConfigurationError)

    def test_immutable_string_verdadeiro_rejeitado(self, tmp_path: Path) -> None:
        """Apenas o booleano ``true`` vale — string ``"true"`` e rejeitada."""
        doc = _valid_core_document()
        doc["dag"]["immutable"] = "true"
        parser = _make_parser(tmp_path, {"bad_str.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_id_sem_prefixo_core_rejeitado(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["dag"]["id"] = "metrics_collection"
        parser = _make_parser(tmp_path, {"bad_id.yaml": doc})
        with pytest.raises(ValueError) as excinfo:
            parser.parse_all()
        assert "prefixo" in str(excinfo.value)

    def test_owner_divergente_rejeitado(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["dag"]["owner"] = "dev_team"
        parser = _make_parser(tmp_path, {"bad_owner.yaml": doc})
        with pytest.raises(ValueError) as excinfo:
            parser.parse_all()
        assert "owner='framework'" in str(excinfo.value)

    def test_ciclo_em_depends_on_rejeitado(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["tasks"] = [
            {
                "id": "a",
                "type": "management.metrics.collect",
                "config": {},
                "depends_on": ["b"],
            },
            {
                "id": "b",
                "type": "management.metrics.aggregate",
                "config": {},
                "depends_on": ["a"],
            },
        ]
        parser = _make_parser(tmp_path, {"bad_cycle.yaml": doc})
        with pytest.raises(ValueError) as excinfo:
            parser.parse_all()
        assert "ciclo" in str(excinfo.value)

    def test_auto_dependencia_rejeitada(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["tasks"][0]["depends_on"] = [doc["tasks"][0]["id"]]
        parser = _make_parser(tmp_path, {"self_cycle.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_tipo_fora_de_management_rejeitado(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["tasks"][0]["type"] = "business.etl.run"
        parser = _make_parser(tmp_path, {"bad_type.yaml": doc})
        with pytest.raises(ValueError) as excinfo:
            parser.parse_all()
        assert "management." in str(excinfo.value)

    def test_tipo_management_desconhecido_rejeitado(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["tasks"][0]["type"] = "management.metrics.teleport"
        parser = _make_parser(tmp_path, {"unknown_type.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_components_proibido_em_core_dag(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["components"] = [{"id": "x", "type": "mca.X", "config": {}}]
        parser = _make_parser(tmp_path, {"with_components.yaml": doc})
        with pytest.raises(ValueError) as excinfo:
            parser.parse_all()
        assert "components" in str(excinfo.value)

    def test_pipeline_proibido_em_core_dag(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["pipeline"] = {"stages": []}
        parser = _make_parser(tmp_path, {"with_pipeline.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_sem_on_failure_rejeitado(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["notifications"] = {"on_success": [{"type": "log", "level": "INFO"}]}
        parser = _make_parser(tmp_path, {"no_on_failure.yaml": doc})
        with pytest.raises(ValueError) as excinfo:
            parser.parse_all()
        assert "on_failure" in str(excinfo.value)

    def test_canal_inexistente_rejeitado(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["notifications"]["on_failure"] = [{"type": "carrier_pigeon"}]
        parser = _make_parser(tmp_path, {"bad_channel.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_notificacao_nao_lista_rejeitada(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["notifications"]["on_failure"] = {"type": "log"}
        parser = _make_parser(tmp_path, {"notif_dict.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_chave_dag_ausente_rejeitada(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        del doc["dag"]
        parser = _make_parser(tmp_path, {"no_dag.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    @pytest.mark.parametrize("key", REQUIRED_DAG_KEYS)
    def test_sub_chave_obrigatoria_ausente_rejeitada(
        self, tmp_path: Path, key: str
    ) -> None:
        doc = _valid_core_document()
        del doc["dag"][key]
        parser = _make_parser(tmp_path, {f"missing_{key}.yaml": doc})
        with pytest.raises(ValueError) as excinfo:
            parser.parse_all()
        assert key in str(excinfo.value), f"falha deveria citar '{key}'"

    @pytest.mark.parametrize("key", ("tasks", "notifications"))
    def test_top_level_ausente_rejeitado(self, tmp_path: Path, key: str) -> None:
        doc = _valid_core_document()
        del doc[key]
        parser = _make_parser(tmp_path, {f"missing_{key}.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_sintaxe_yaml_invalida_rejeitada(self, tmp_path: Path) -> None:
        core_dir = tmp_path / "core_dags"
        core_dir.mkdir(parents=True, exist_ok=True)
        (core_dir / "broken.yaml").write_text(
            "dag: [unclosed\n  id: core_x\n", encoding="utf-8"
        )
        parser = DAGParser(str(core_dir), str(tmp_path / "app_dags"))
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_documento_nao_mapeamento_rejeitado(self, tmp_path: Path) -> None:
        core_dir = tmp_path / "core_dags"
        core_dir.mkdir(parents=True, exist_ok=True)
        (core_dir / "scalar.yaml").write_text("- 1\n- 2\n", encoding="utf-8")
        parser = DAGParser(str(core_dir), str(tmp_path / "app_dags"))
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_tasks_nao_lista_rejeitada(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["tasks"] = {"id": "collect"}
        parser = _make_parser(tmp_path, {"tasks_dict.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_tarefa_sem_config_rejeitada(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        del doc["tasks"][0]["config"]
        parser = _make_parser(tmp_path, {"no_config.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_tarefa_nao_mapa_rejeitada(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["tasks"] = ["apenas_string"]
        parser = _make_parser(tmp_path, {"task_scalar.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_dependencia_inexistente_rejeitada(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["tasks"][0]["depends_on"] = ["fantasma"]
        parser = _make_parser(tmp_path, {"ghost_dep.yaml": doc})
        with pytest.raises(ValueError):
            parser.parse_all()

    def test_app_dag_imutavel_rejeitada(self, tmp_path: Path) -> None:
        """CS-03: App DAG com immutable=true interrompe o carregamento."""
        core_doc = _valid_core_document()
        app_doc = copy.deepcopy(core_doc)
        app_doc["dag"]["id"] = "app_bad"
        app_doc["dag"]["owner"] = "dev_team"
        app_doc["dag"]["immutable"] = True
        parser = _make_parser(tmp_path, {"core_ok.yaml": core_doc})
        _write_yaml(Path(parser.app_dags_dir) / "bad_app.yaml", app_doc)
        with pytest.raises(ValueError) as excinfo:
            parser.parse_all()
        assert "App DAG" in str(excinfo.value)

    def test_colisao_de_id_entre_app_e_core_rejeitada(self, tmp_path: Path) -> None:
        """CC-05: App DAG nao pode sobrescrever Core DAG (teste de colisao)."""
        core_doc = _valid_core_document()
        app_doc = copy.deepcopy(core_doc)  # mesmo id core_ok -> colisao
        app_doc["dag"]["immutable"] = False
        parser = _make_parser(tmp_path, {"core_ok.yaml": core_doc})
        _write_yaml(Path(parser.app_dags_dir) / "collision.yaml", app_doc)
        with pytest.raises(ValueError) as excinfo:
            parser.parse_all()
        assert "sobrescrever" in str(excinfo.value)

    def test_core_dag_fora_do_diretorio_core_rejeitada(self, tmp_path: Path) -> None:
        """VAL-04: Core DAG materializada fora de framework/core/dags/ falha."""
        doc = _valid_core_document()
        misplaced = tmp_path / "elsewhere" / "core_ok.yaml"
        _write_yaml(misplaced, doc)
        parser = _make_parser(tmp_path, {})
        with pytest.raises(ValueError):
            parser.parse_file(misplaced)

    def test_diagnostico_contem_regra_tipada(self, tmp_path: Path) -> None:
        doc = _valid_core_document()
        doc["dag"]["immutable"] = False
        parser = _make_parser(tmp_path, {"diag.yaml": doc})
        with pytest.raises(ConfigurationError) as excinfo:
            parser.parse_all()
        error = excinfo.value
        assert error.context["rule"] == "VAL-01"
        assert "diag.yaml" in error.context["path"]

    def test_arquivo_inexistente_rejeitado(self, tmp_path: Path) -> None:
        parser = _make_parser(tmp_path, {})
        with pytest.raises(ValueError):
            parser.parse_file(tmp_path / "nao_existe.yaml")


# ---------------------------------------------------------------------------
# Secao 5.3 — criterios de conformidade adicionais (CC-03)
# ---------------------------------------------------------------------------


class TestConformidadeInfraestrutura:
    """CC-03: Core DAGs montadas como ``:ro`` no manifesto de implantacao."""

    @pytest.mark.parametrize("manifest", DEPLOYMENT_MANIFESTS)
    def test_montagem_read_only(self, manifest: str) -> None:
        path = PROJECT_ROOT / manifest
        if not path.is_file():
            pytest.skip(f"manifesto ainda nao entregue: {manifest}")
        texto = path.read_text(encoding="utf-8")
        if "framework/core/dags" in texto:
            assert ":ro" in texto, (
                f"{manifest}: montagem de Core DAGs deve usar ':ro'"
            )

    def test_yamllint_relaxado_se_disponivel(self) -> None:
        """Secao 7: yamllint -d relaxed framework/core/dags/ (quando instalado)."""
        pytest.importorskip("yamllint")
        from yamllint import config as yl_config
        from yamllint import linter

        # Equivalente programatico de `yamllint -d relaxed`: a configuracao
        # 'relaxed' e herdada via 'extends:' e o primeiro argumento de
        # linter.run() e um file-like object (nao caminho).
        linha = yl_config.YamlLintConfig("extends: relaxed")
        for caminho in _core_paths():
            with open(caminho, encoding="utf-8") as handle:
                problemas = list(linter.run(handle, linha))
            erros = [p for p in problemas if p.level == "error"]
            assert not erros, f"{caminho.name}: erros yamllint: {erros}"


# ---------------------------------------------------------------------------
# Higiene estatica dos artefatos
# ---------------------------------------------------------------------------


class TestHigieneArtefatos:
    """Qualidade dos YAMLs entregues (Secoes 8.3 e 8.5)."""

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_ascii_puro(self, name: str, document: Dict[str, Any]) -> None:
        """Sem acentos: consistencia com os docs e seguranca de encoding."""
        raw = (CORE_DAGS_DIR / name).read_bytes()
        assert all(byte < 0x80 for byte in raw), f"{name}: bytes nao-ASCII"
        assert isinstance(document, dict)

    @pytest.mark.parametrize("name,document", ALL_FILE_PARAMS, ids=PARAM_IDS)
    def test_primeira_linha_identifica_origem(
        self, name: str, document: Dict[str, Any]
    ) -> None:
        """Rastreabilidade: cabecalho com o caminho do artefato."""
        primeira = (CORE_DAGS_DIR / name).read_text(encoding="utf-8").splitlines()[0]
        assert primeira.startswith("# framework/core/dags/")

    def test_linhas_dentro_de_88_colunas(self) -> None:
        for name in EXPECTED_CORE_DAG_FILES:
            linhas = (CORE_DAGS_DIR / name).read_text(encoding="utf-8").splitlines()
            longas = [ln for ln in linhas if len(ln) > 88]
            assert not longas, f"{name}: linhas acima de 88 colunas: {longas}"

    def test_description_nao_usa_acentos(self) -> None:
        for name, document in CORE_DOCUMENTS.items():
            assert document["dag"]["description"].isascii(), (
                f"{name}: descricao com caracteres nao-ASCII"
            )

    def test_inventario_de_teste_e_autodescritivo(self) -> None:
        """O modulo expoe o inventario usado pelos parametrizados."""
        assert len(EXPECTED_CORE_DAG_FILES) == 4
        assert set(EXPECTED_IDS) == set(EXPECTED_CORE_DAG_FILES)
        assert len(PARAM_IDS) == 4
        assert len(CORE_DOCUMENTS) == 4
