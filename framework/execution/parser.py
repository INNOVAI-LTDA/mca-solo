"""Parser unificado de DAGs YAML do MCA-Solo (Especificacao Tecnica ID 1.4).

Este modulo materializa a separacao entre **Gestao** (Core DAGs, imutaveis
pelo DEV) e **Orquestracao** (App DAGs, mutaveis pelo DEV), conforme
``docs/arquitetura_molde_v3_dags_separacao.md`` (Secoes 5, 7 e 11) e
``docs/contracts.md`` (Secoes 7.4 e 9.2).

Regra de Ouro (ID 1.4):
    Todo Core DAG deve ter ``immutable: true``, residir em
    ``framework/core/dags/``, possuir ``id`` no espaco de nomes ``core_*``
    (disjunto do espaco das App DAGs) e implementar exclusivamente
    funcionalidades de Gestao (tipos de tarefa ``management.*``).

Principio da Falha Explicita (Secao 5.2 da spec ID 1.4):
    Toda violacao de validacao interrompe o carregamento com diagnostico
    tipado (``ConfigurationError``, subclasse de ``ValueError``). NAO ha
    fallback silencioso.

Regras de validacao implementadas (Secao 5.1):
    - VAL-01: Core DAG deve ter ``immutable: true``.
    - VAL-02: Core DAG deve ter ``owner: "framework"``.
    - VAL-03: Core DAG ``id`` deve comecar com o prefixo ``core_``.
    - VAL-04: Core DAG deve residir em diretorio de Core DAGs (:ro).
    - VAL-05: YAML deve conformar ao schema (chaves obrigatorias; ausencia
      de ``components``/``pipeline`` em Core DAGs).
    - VAL-06: grafo de ``depends_on`` deve ser aciclico.
    - VAL-07: tipos de tarefa de Core DAG devem pertencer a ``management.*``.
    - VAL-08: IDs de Core e App DAGs devem ser disjuntos.
    - VAL-09: App DAG nao pode ter ``immutable: true`` (v3, Secao 7.3).

Exemplo basico::

    >>> parser = DAGParser("framework/core/dags", "application/dags")
    >>> registro = parser.parse_all()
    >>> sorted(parser.get_core_dags())  # doctest: +SKIP
    ['core_alerting', 'core_component_lifecycle', 'core_health_check',
     'core_metrics_collection']
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from framework.core.exceptions import ConfigurationError

__all__ = [
    "CORE_DAG_PREFIX",
    "CORE_DAG_REQUIRED_KEYS",
    "CORE_OWNER",
    "DAGDefinition",
    "DAGParser",
    "MANAGEMENT_TASK_TYPES",
    "NOTIFICATION_CHANNELS",
]

#: Prefixo obrigatorio do espaco de nomes das Core DAGs (VAL-03).
CORE_DAG_PREFIX: str = "core_"

#: Proprietario obrigatorio das Core DAGs (VAL-02).
CORE_OWNER: str = "framework"

#: Chaves obrigatorias dentro do bloco ``dag`` (VAL-05, Secao 4.1 item 2).
CORE_DAG_REQUIRED_KEYS: tuple = (
    "id",
    "description",
    "schedule",
    "owner",
    "immutable",
)

#: Canais de notificacao permitidos (Secao 4.2 / teste 6.7).
NOTIFICATION_CHANNELS: frozenset = frozenset({"log", "alert", "webhook"})

#: Conjunto valido de tipos de tarefa de Gestao (Secao 4.7 - VAL-07).
MANAGEMENT_TASK_TYPES: frozenset = frozenset(
    {
        "management.metrics.collect",
        "management.metrics.aggregate",
        "management.metrics.expose",
        "management.health.check_connectivity",
        "management.health.check_resources",
        "management.health.check_dependencies",
        "management.health.generate_report",
        "management.lifecycle.start",
        "management.lifecycle.stop",
        "management.lifecycle.restart",
        "management.alerting.evaluate_rules",
    }
)


@dataclass
class DAGDefinition:
    """Representa uma DAG parseada de YAML (contrato ``docs/contracts.md`` 7.4).

    Invariantes:
        - ``id`` e unico no registro unificado (Core + App).
        - ``immutable`` e ``True`` para Core DAGs, ``False`` para App DAGs.
        - Core DAGs nunca declaram ``components`` nem ``pipeline``.

    Attributes:
        id: Identificador da DAG (prefixo ``core_`` nas Core DAGs).
        description: Descricao legavel da finalidade da DAG.
        schedule: Expressao cron ou ``None`` (DAG event-driven).
        owner: Proprietario da DAG (``framework`` nas Core DAGs).
        immutable: ``True`` somente para Core DAGs.
        tasks: Lista ordenada de tarefas (dicts com ``id``/``type``/``config``).
        components: Componentes declarados (apenas App DAGs).
        pipeline: Fluxo de estagios (apenas App DAGs).
        connectors: Conectores de comunicacao (apenas App DAGs).
        notifications: Mapa de notificacoes (``on_failure``/``on_success``/...).
        triggers: Disparadores evento-tarefa (apenas Core DAGs; v3 Secao 5.3.3).
        source_path: Caminho do arquivo YAML de origem (diagnostico).
    """

    id: str
    description: str
    schedule: Optional[str]
    owner: str
    immutable: bool
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    components: List[Dict[str, Any]] = field(default_factory=list)
    pipeline: Dict[str, Any] = field(default_factory=dict)
    connectors: List[Dict[str, Any]] = field(default_factory=list)
    notifications: Dict[str, Any] = field(default_factory=dict)
    triggers: List[Dict[str, Any]] = field(default_factory=list)
    source_path: Optional[str] = None

    @property
    def is_core(self) -> bool:
        """Indica se esta DAG pertence ao nucleo imutavel do framework."""
        return self.immutable


class DAGParser:
    """Parser unificado de DAGs YAML (Core + App) com falha explicita.

    Pre-condicoes:
        - Os diretorios informados existem (ou estao vazios).
        - Os arquivos possuem extensao ``.yaml`` ou ``.yml``.

    Pos-condicoes:
        - Apos ``parse_all()``, ``get_core_dags()`` e ``get_app_dags()``
          retornam registros validados pelas regras VAL-01..VAL-09.

    Invariantes:
        - Qualquer violacao de contrato levanta ``ConfigurationError``
          (subclasse de ``ValueError``) - nunca ha degradacao silenciosa.

    Examples:
        >>> from pathlib import Path
        >>> parser = DAGParser("framework/core/dags", "application/dags")
        >>> dag = parser.parse_file(Path("framework/core/dags/alerting.yaml"))
        >>> dag.id
        'core_alerting'
        >>> dag.immutable
        True
    """

    def __init__(self, framework_dags_dir: str, app_dags_dir: str) -> None:
        """Inicializa o parser com os dois diretorios de DAGs.

        Args:
            framework_dags_dir: Diretorio das Core DAGs (ex.:
                ``framework/core/dags``). Montado como ``:ro`` em runtime.
            app_dags_dir: Diretorio das App DAGs (ex.:
                ``application/dags``). Montado como ``:rw`` em runtime.
        """
        self.framework_dags_dir: Path = Path(framework_dags_dir)
        self.app_dags_dir: Path = Path(app_dags_dir)

        self.core_dags: Dict[str, DAGDefinition] = {}
        self.app_dags: Dict[str, DAGDefinition] = {}

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------
    def parse_all(self) -> Dict[str, DAGDefinition]:
        """Parseia todas as DAGs (Core + App) e retorna o registro unificado.

        Returns:
            Dicionario ``{id: DAGDefinition}`` com Core e App DAGs.

        Raises:
            ConfigurationError: Se qualquer regra VAL-01..VAL-09 for violada.
        """
        self._parse_core_dags()
        self._parse_app_dags()
        self._validate_no_conflicts()
        return {**self.core_dags, **self.app_dags}

    def parse_file(self, yaml_file: Path) -> DAGDefinition:
        """Parseia e valida um arquivo YAML individual sem registra-lo.

        Args:
            yaml_file: Caminho do arquivo ``.yaml``/``.yml``.

        Returns:
            A ``DAGDefinition`` validada.

        Raises:
            ConfigurationError: Se o YAML for ilegivel ou violar o schema.
        """
        path = Path(yaml_file)
        data = self._load_yaml(path)
        dag = self._build_definition(data, path)
        self._validate_definition(dag, is_core=self._is_core_source(path))
        return dag

    def get_core_dags(self) -> Dict[str, DAGDefinition]:
        """Retorna copia do registro de Core DAGs ja parseadas."""
        return self.core_dags.copy()

    def get_app_dags(self) -> Dict[str, DAGDefinition]:
        """Retorna copia do registro de App DAGs ja parseadas."""
        return self.app_dags.copy()

    # ------------------------------------------------------------------
    # Pipeline interno
    # ------------------------------------------------------------------
    def _parse_core_dags(self) -> None:
        """Parseia as Core DAGs do diretorio do framework (VAL-01..VAL-07)."""
        for yaml_file in self._iter_yaml_files(self.framework_dags_dir):
            dag = self.parse_file(yaml_file)
            self.core_dags[dag.id] = dag

    def _parse_app_dags(self) -> None:
        """Parseia as App DAGs do diretorio da aplicacao (VAL-08, VAL-09)."""
        for yaml_file in self._iter_yaml_files(self.app_dags_dir):
            if not yaml_file.read_bytes().strip():
                # Placeholder criado pelo scaffold (create_dir.ps1): a App DAG
                # correspondente ainda nao foi implementada (Issue 1.5). O
                # nucleo imutavel permanece valido e o carregamento segue.
                continue
            data = self._load_yaml(yaml_file)
            dag = self._build_definition(data, yaml_file)

            # VAL-09: App DAGs nao podem ser imutaveis (v3, Secao 7.3).
            if dag.immutable:
                raise ConfigurationError(
                    f"App DAG {dag.id} nao pode ter immutable=true",
                    context={"path": str(yaml_file), "rule": "VAL-09"},
                )

            # VAL-08 (antecipada): App DAG nao pode sobrescrever Core DAG.
            if dag.id in self.core_dags:
                raise ConfigurationError(
                    f"App DAG {dag.id} nao pode sobrescrever Core DAG",
                    context={"path": str(yaml_file), "rule": "VAL-08"},
                )

            self.app_dags[dag.id] = dag

    def _validate_no_conflicts(self) -> None:
        """Valida disjuncao de IDs entre Core e App DAGs (VAL-08)."""
        conflicts = set(self.core_dags.keys()) & set(self.app_dags.keys())
        if conflicts:
            raise ConfigurationError(
                f"Conflito de IDs entre Core e App DAGs: {sorted(conflicts)}",
                context={"rule": "VAL-08", "conflicts": sorted(conflicts)},
            )

    # ------------------------------------------------------------------
    # Leitura e construcao
    # ------------------------------------------------------------------
    @staticmethod
    def _iter_yaml_files(directory: Path) -> List[Path]:
        """Lista deterministicamente os arquivos YAML de um diretorio."""
        if not directory.is_dir():
            return []
        files = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
        return sorted(set(files))

    @staticmethod
    def _load_yaml(yaml_file: Path) -> Dict[str, Any]:
        """Carrega um arquivo YAML com ``safe_load`` (falha explicita).

        Args:
            yaml_file: Caminho do documento YAML.

        Returns:
            O mapeamento desserializado.

        Raises:
            ConfigurationError: Se o arquivo nao existir, contiver erro de
                sintaxe YAML, ou nao for um mapeamento na raiz.
        """
        try:
            with open(yaml_file, "r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except FileNotFoundError as exc:
            raise ConfigurationError(
                f"DAG nao encontrada: {yaml_file}",
                context={"path": str(yaml_file)},
                cause=exc,
            ) from exc
        except yaml.YAMLError as exc:
            raise ConfigurationError(
                f"Erro de sintaxe YAML em {yaml_file}: {exc}",
                context={"path": str(yaml_file)},
                cause=exc,
            ) from exc

        if not isinstance(data, dict):
            raise ConfigurationError(
                f"Documento YAML de {yaml_file} deve ser um mapeamento na raiz",
                context={"path": str(yaml_file), "rule": "VAL-05"},
            )
        return data

    def _is_core_source(self, yaml_file: Path) -> bool:
        """Determina se o arquivo provem do diretorio de Core DAGs (VAL-04).

        Args:
            yaml_file: Caminho do arquivo YAML.

        Returns:
            ``True`` se o arquivo estiver sob ``framework_dags_dir``.
        """
        try:
            resolved = yaml_file.resolve()
        except OSError:
            resolved = yaml_file
        core_root = self.framework_dags_dir.resolve()
        return resolved.parent == core_root or core_root in resolved.parents

    @staticmethod
    def _build_definition(data: Dict[str, Any], yaml_file: Path) -> DAGDefinition:
        """Constroi a ``DAGDefinition`` a partir do dicionario YAML bruto.

        Nao valida conteudo semantico - apenas extrai campos com defaults do
        contrato ``docs/contracts.md`` Secao 9.2 e exige as chaves
        estruturais obrigatorias (VAL-05).

        Args:
            data: Documento YAML ja desserializado.
            yaml_file: Caminho de origem (usado no diagnostico).

        Returns:
            A definicao estruturada da DAG.

        Raises:
            ConfigurationError: Se faltarem chaves obrigatorias ou se os
                tipos das chaves top-level forem incorretos.
        """
        dag_data = data.get("dag")
        if not isinstance(dag_data, dict):
            raise ConfigurationError(
                f"{yaml_file}: chave top-level 'dag' e obrigatoria e deve ser mapeamento",
                context={"path": str(yaml_file), "rule": "VAL-05"},
            )

        missing = [key for key in CORE_DAG_REQUIRED_KEYS if key not in dag_data]
        if missing:
            raise ConfigurationError(
                f"{yaml_file}: chaves obrigatorias ausentes em dag: {missing}",
                context={"path": str(yaml_file), "rule": "VAL-05", "missing": missing},
            )

        for top_key in ("tasks", "notifications"):
            if top_key not in data:
                raise ConfigurationError(
                    f"{yaml_file}: chave top-level '{top_key}' e obrigatoria",
                    context={"path": str(yaml_file), "rule": "VAL-05"},
                )

        tasks = data["tasks"]
        if not isinstance(tasks, list):
            raise ConfigurationError(
                f"{yaml_file}: 'tasks' deve ser uma lista ordenada",
                context={"path": str(yaml_file), "rule": "VAL-05"},
            )

        notifications = data["notifications"]
        if not isinstance(notifications, dict):
            raise ConfigurationError(
                f"{yaml_file}: 'notifications' deve ser um dicionario",
                context={"path": str(yaml_file), "rule": "VAL-05"},
            )

        return DAGDefinition(
            id=dag_data["id"],
            description=dag_data["description"],
            schedule=dag_data["schedule"],
            owner=dag_data["owner"],
            immutable=dag_data["immutable"],
            tasks=tasks,
            components=data.get("components", []),
            pipeline=data.get("pipeline", {}),
            connectors=data.get("connectors", []),
            notifications=notifications,
            triggers=data.get("triggers", []),
            source_path=str(yaml_file),
        )

    # ------------------------------------------------------------------
    # Validacoes semanticas
    # ------------------------------------------------------------------
    def _validate_definition(self, dag: DAGDefinition, *, is_core: bool) -> None:
        """Aplica as regras VAL-01..VAL-07 a uma Core DAG recem-parseada.

        Para App DAGs a validacao estrutural completa fica a cargo da
        Issue 1.5; aqui apenas o caminho de Core DAG exerce o conjunto.

        Args:
            dag: Definicao construida a partir do YAML.
            is_core: ``True`` quando a origem e o diretorio de Core DAGs.

        Raises:
            ConfigurationError: Ao menor desvio do contrato de Core DAG.
        """
        if not is_core:
            return

        # VAL-01: imutabilidade obrigatoria (booleano literal True).
        if dag.immutable is not True:
            raise ConfigurationError(
                f"Core DAG {dag.id} deve ter immutable=true",
                context={"path": dag.source_path, "rule": "VAL-01"},
            )

        # VAL-02: propriedade do framework.
        if dag.owner != CORE_OWNER:
            raise ConfigurationError(
                f"Core DAG {dag.id} deve ter owner='framework'",
                context={"path": dag.source_path, "rule": "VAL-02", "owner": dag.owner},
            )

        # VAL-03: espaco de nomes disjunto via prefixo core_.
        if not isinstance(dag.id, str) or not dag.id.startswith(CORE_DAG_PREFIX):
            raise ConfigurationError(
                f"Core DAG {dag.id} deve ter id com prefixo '{CORE_DAG_PREFIX}'",
                context={"path": dag.source_path, "rule": "VAL-03"},
            )

        # VAL-04: localizacao fisica (reforco: arquivo sob diretorio de Core).
        if dag.source_path is None or not self._is_core_source(Path(dag.source_path)):
            raise ConfigurationError(
                f"Core DAG {dag.id} deve residir em framework/core/dags/",
                context={"path": dag.source_path, "rule": "VAL-04"},
            )

        # VAL-05 (complementar): Core DAGs nao declaram components/pipeline.
        if dag.components or dag.pipeline:
            raise ConfigurationError(
                f"Core DAG {dag.id} nao pode declarar 'components' nem 'pipeline' "
                "(chaves exclusivas de App DAGs)",
                context={"path": dag.source_path, "rule": "VAL-05"},
            )

        self._validate_tasks(dag)
        self._validate_notifications(dag)

    @staticmethod
    def _validate_tasks(dag: DAGDefinition) -> None:
        """Valida tipos de tarefa (VAL-07) e aciclicidade do grafo (VAL-06).

        Args:
            dag: Core DAG a validar.

        Raises:
            ConfigurationError: Para tarefa sem ``id``/``type``/``config``,
                tipo fora de ``management.*``, dependencia inexistente ou
                ciclo no grafo ``depends_on``.
        """
        task_ids: Set[str] = set()
        for task in dag.tasks:
            if not isinstance(task, dict):
                raise ConfigurationError(
                    f"Core DAG {dag.id}: cada tarefa deve ser um mapeamento",
                    context={"path": dag.source_path, "rule": "VAL-05"},
                )
            for key in ("id", "type", "config"):
                if key not in task:
                    raise ConfigurationError(
                        f"Core DAG {dag.id}: tarefa {task.get('id', task)} "
                        f"esta sem a chave obrigatoria '{key}'",
                        context={"path": dag.source_path, "rule": "VAL-05"},
                    )
            task_ids.add(task["id"])

            # VAL-07: tipo deve pertencer ao vocabulario management.*
            task_type = task["type"]
            if not isinstance(task_type, str) or not task_type.startswith("management."):
                raise ConfigurationError(
                    f"Core DAG {dag.id}: tarefa {task['id']} tem tipo invalido "
                    f"'{task_type}'; Core DAGs usam exclusivamente management.*",
                    context={"path": dag.source_path, "rule": "VAL-07"},
                )
            if task_type not in MANAGEMENT_TASK_TYPES:
                raise ConfigurationError(
                    f"Core DAG {dag.id}: tarefa {task['id']} usa tipo desconhecido "
                    f"'{task_type}'",
                    context={
                        "path": dag.source_path,
                        "rule": "VAL-07",
                        "allowed": sorted(MANAGEMENT_TASK_TYPES),
                    },
                )

        # Dependencias inexistentes + VAL-06 (ciclo) por DFS com marcacao.
        graph = {t["id"]: list(t.get("depends_on") or []) for t in dag.tasks}
        for tid, deps in graph.items():
            unknown = [dep for dep in deps if dep not in task_ids]
            if unknown:
                raise ConfigurationError(
                    f"Core DAG {dag.id}: tarefa {tid} depende de ids inexistentes: "
                    f"{unknown}",
                    context={"path": dag.source_path, "rule": "VAL-05"},
                )

        white, gray, black = 0, 1, 2
        color: Dict[str, int] = {tid: white for tid in graph}

        def visit(node: str, trail: List[str]) -> None:
            state = color[node]
            if state == gray:
                cycle = trail[trail.index(node):] + [node]
                raise ConfigurationError(
                    f"Core DAG {dag.id}: ciclo detectado em depends_on: "
                    f"{' -> '.join(cycle)}",
                    context={"path": dag.source_path, "rule": "VAL-06"},
                )
            if state == black:
                return
            color[node] = gray
            for dep in graph[node]:
                visit(dep, trail + [node])
            color[node] = black

        for node in graph:
            if color[node] == white:
                visit(node, [])

    @staticmethod
    def _validate_notifications(dag: DAGDefinition) -> None:
        """Valida canais de notificacao e presenca obrigatoria de ``on_failure``.

        Exigencias da spec ID 1.4 (Secoes 3.2, 4.2 e teste 6.7):
            - Todo Core DAG possui ao menos uma notificacao ``on_failure``.
            - Cada canal declarado tem ``type`` em {log, alert, webhook}.

        Args:
            dag: Core DAG a validar.

        Raises:
            ConfigurationError: Na ausencia de ``on_failure`` ou em canal
                malformado/nao permitido.
        """
        on_failure = dag.notifications.get("on_failure")
        if not on_failure:
            raise ConfigurationError(
                f"Core DAG {dag.id} deve declarar ao menos uma notificacao "
                "on_failure (falha explicita de monitoramento)",
                context={"path": dag.source_path, "rule": "VAL-05"},
            )

        for event, channels in dag.notifications.items():
            if not isinstance(channels, list):
                raise ConfigurationError(
                    f"Core DAG {dag.id}: notifications.{event} deve ser uma lista "
                    "de canais",
                    context={"path": dag.source_path, "rule": "VAL-05"},
                )
            for channel in channels:
                if not isinstance(channel, dict) or "type" not in channel:
                    raise ConfigurationError(
                        f"Core DAG {dag.id}: canal de notificacao invalido em "
                        f"notifications.{event}: {channel}",
                        context={"path": dag.source_path, "rule": "VAL-05"},
                    )
                if channel["type"] not in NOTIFICATION_CHANNELS:
                    raise ConfigurationError(
                        f"Core DAG {dag.id}: canal '{channel['type']}' nao permitido "
                        f"em notifications.{event}; permitidos: "
                        f"{sorted(NOTIFICATION_CHANNELS)}",
                        context={"path": dag.source_path, "rule": "VAL-05"},
                    )
