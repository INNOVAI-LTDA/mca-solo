"""Testes dos contratos de dados e gestao imutaveis (ID 1.2).

Cobertura da Strategia de Testes da Secao 6 da Especificacao Tecnica:
    6.1. Barreira de imutabilidade (``frozen`` / ``FrozenInstanceError``).
    6.2. Copia defensiva (padrao ``with_*`` via ``dataclasses.replace``).
    6.3. Invariantes e propriedades computadas (casos de borda).
    6.4. Defaults e isolamento de estado (``default_factory``).
    6.5. Gestao (``ComponentMetrics``): tipagem do status e proveniencia.

Execucao:
    pytest tests/framework/test_core_entities.py -v
    pytest --cov=framework.core.entities --cov-report=term-missing
"""

from __future__ import annotations

import dataclasses
from dataclasses import FrozenInstanceError
from datetime import datetime
from typing import List, Type

import pytest

from framework.core.entities import (
    ComponentMetrics,
    ComponentStatus,
    FetchResult,
    IngestResult,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# 6.1. Testes de Imutabilidade (Barreira `frozen`)
# ---------------------------------------------------------------------------
class TestImutabilidade:
    """Garante que a barreira ``frozen=True`` cobre todas as entidades."""

    def test_fetch_result_e_frozen(self) -> None:
        """Atribuir novo valor a ``items`` deve levantar FrozenInstanceError."""
        result = FetchResult(items=[1, 2, 3])
        with pytest.raises(FrozenInstanceError):
            result.items = []  # type: ignore[misc]

    def test_fetch_result_bloqueia_atributos_novos(self) -> None:
        """Injetar atributo inexistente deve levantar FrozenInstanceError."""
        result = FetchResult(items=[])
        with pytest.raises(FrozenInstanceError):
            result.novo_campo = "x"  # type: ignore[attr-defined]

    def test_ingest_result_e_frozen(self) -> None:
        """Contadores de ingestao sao fatos historicos imutaveis."""
        result = IngestResult(success_count=1)
        with pytest.raises(FrozenInstanceError):
            result.success_count = 999  # type: ignore[misc]

    def test_validation_result_e_frozen(self) -> None:
        """O snapshot de validacao nao pode ser adulterado em memoria."""
        result = ValidationResult(is_valid=True)
        with pytest.raises(FrozenInstanceError):
            result.is_valid = False  # type: ignore[misc]

    def test_component_metrics_e_frozen(self) -> None:
        """``metrics.status = 'DEGRADADO'`` deve levantar FrozenInstanceError."""
        metrics = ComponentMetrics(component_id="c1")
        with pytest.raises(FrozenInstanceError):
            metrics.status = "DEGRADADO"  # type: ignore[assignment,misc]

    def test_component_metrics_bloqueia_mutation_de_campos_numericos(self) -> None:
        """Indicadores operacionais do snapshot tambem sao imutaveis."""
        metrics = ComponentMetrics(component_id="c1", execution_count=5)
        with pytest.raises(FrozenInstanceError):
            metrics.execution_count = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 6.2. Testes de Cópia Defensiva (Padrão `with_*`)
# ---------------------------------------------------------------------------
class TestCopiaDefensiva:
    """Garante que ``with_error`` materializa novas instancias sem mutar a original."""

    def test_with_error_preserva_instancia_original(self) -> None:
        """Original permanece com ``errors == []``; nova contem o erro."""
        result = FetchResult(items=[{"urn": "lei-1"}], errors=[])
        novo_result = result.with_error("Timeout", {"url": "https://exemplo.gov"})

        # Instancia original intacta (rastro de auditoria preservado).
        assert result.errors == []
        assert result.has_errors is False

        # Nova instancia contem exatamente o erro adicionado.
        assert len(novo_result.errors) == 1
        assert novo_result.errors[0]["error"] == "Timeout"
        assert novo_result.errors[0]["context"] == {"url": "https://exemplo.gov"}
        assert "timestamp" in novo_result.errors[0]
        assert novo_result.has_errors is True

        # Sao objetos distintos na memoria.
        assert id(result) != id(novo_result)

    def test_with_error_sem_contexto_normaliza_para_dict_vazio(self) -> None:
        """``contexto=None`` deve ser normalizado para ``{}`` no registro."""
        novo = FetchResult(items=[]).with_error("Falha de parsing")
        assert novo.errors[0]["context"] == {}

    def test_with_error_em_cadeia_acumula_erros_sem_mutar_intermediarios(self) -> None:
        """Encadear ``with_error`` preserva cada snapshot intermediario."""
        base = FetchResult(items=[1])
        passo1 = base.with_error("E1")
        passo2 = passo1.with_error("E2", {"etapa": "fetch"})

        assert base.errors == []
        assert len(passo1.errors) == 1
        assert len(passo2.errors) == 2
        assert [e["error"] for e in passo2.errors] == ["E1", "E2"]
        assert id(passo1) != id(passo2)

    def test_with_error_copia_defensiva_do_dicionario_de_contexto(self) -> None:
        """Mutar o dict externo apos ``with_error`` nao afeta o registro gravado."""
        contexto_externo = {"url": "https://a"}
        novo = FetchResult(items=[]).with_error("Timeout", contexto_externo)
        contexto_externo["url"] = "https://B"  # tentativa de adulteracao externa

        assert novo.errors[0]["context"]["url"] == "https://a"

    def test_with_error_preserva_demais_campos(self) -> None:
        """``dataclasses.replace`` herda items, metadata e fetched_at."""
        original = FetchResult(
            items=[1, 2], metadata={"source": "senado"}, fetched_at=datetime(2026, 1, 1)
        )
        novo = original.with_error("W")

        assert novo.items == original.items
        assert novo.metadata == {"source": "senado"}
        assert novo.fetched_at == datetime(2026, 1, 1)
        assert isinstance(novo, FetchResult)


# ---------------------------------------------------------------------------
# 6.3. Testes de Invariantes e Propriedades Computadas
# ---------------------------------------------------------------------------
class TestPropriedadesComputadas:
    """Valida as propriedades derivadas e seus casos de borda."""

    def test_has_errors_se_e_somente_se_houver_erros(self) -> None:
        """``has_errors`` espelha estritamente ``len(errors) > 0``."""
        vazio = FetchResult(items=[1, 2, 3])
        assert vazio.has_errors is False

        com_erro = vazio.with_error("Timeout")
        assert com_erro.has_errors is True

    def test_items_count_reflete_len_items(self) -> None:
        """``items_count`` e o numero de itens extraidos."""
        assert FetchResult(items=[]).items_count == 0
        assert FetchResult(items=[{"a": 1}, {"b": 2}]).items_count == 2

    def test_total_count_e_soma_estrita_dos_contadores(self) -> None:
        """``total_count == success_count + failure_count`` sempre."""
        resultado = IngestResult(success_count=7, failure_count=3)
        assert (
            resultado.total_count == resultado.success_count + resultado.failure_count
        )
        assert resultado.total_count == 10

        zerado = IngestResult()
        assert zerado.total_count == 0

    def test_success_rate_evita_zero_division(self) -> None:
        """Com ``total_count == 0``, ``success_rate`` deve ser ``0.0``."""
        assert IngestResult().success_rate == 0.0

    def test_success_rate_percentual(self) -> None:
        """Taxa calculada em percentual sobre o total processado."""
        assert IngestResult(success_count=8, failure_count=2).success_rate == 80.0
        assert IngestResult(success_count=0, failure_count=5).success_rate == 0.0
        assert IngestResult(success_count=5, failure_count=0).success_rate == 100.0

    def test_violations_count_reflete_len_violations(self) -> None:
        """``violations_count`` e o numero de regras violadas."""
        valido = ValidationResult(is_valid=True)
        assert valido.violations_count == 0

        invalido = ValidationResult(
            is_valid=False,
            violations=[
                {"rule": "H1", "description": "Nivel sem subnivel"},
                {"rule": "K1", "description": "Conflito hierarquico"},
            ],
        )
        assert invalido.violations_count == 2

    def test_invariante_violations_nao_vazio_exige_is_valid_false(self) -> None:
        """Violacoes nao vazias com ``is_valid=True`` devem ser recusadas."""
        assert (
            ValidationResult(is_valid=False, violations=[{"rule": "H1"}]).is_valid
            is False
        )

        with pytest.raises(ValueError):
            ValidationResult(is_valid=True, violations=[{"rule": "H1"}])

    def test_invariante_is_valid_false_exige_violations(self) -> None:
        """``is_valid=False`` sem violacoes registradas e um estado incoerente."""
        with pytest.raises(ValueError):
            ValidationResult(is_valid=False, violations=[])

    def test_propriedades_nao_mutam_estado(self) -> None:
        """Ler propriedades computadas NAO altera o snapshot imutavel."""
        resultado = IngestResult(success_count=3, failure_count=1)
        antes = dataclasses.asdict(resultado)

        _ = resultado.total_count
        _ = resultado.success_rate

        assert dataclasses.asdict(resultado) == antes


# ---------------------------------------------------------------------------
# 6.4. Testes de Defaults e Isolamento de Estado
# ---------------------------------------------------------------------------
class TestDefaultsEIsolamento:
    """Prova que ``default_factory`` evita compartilhamento de estado."""

    def test_defaults_de_fetch_result(self) -> None:
        """Instancia sem opcionais: listas/dicts vazios e timestamp definido."""
        result = FetchResult(items=[])
        assert result.metadata == {}
        assert result.errors == []
        assert isinstance(result.fetched_at, datetime)

    def test_default_factory_isola_listas_entre_instancias(self) -> None:
        """Materializar erros em um objeto nao pode afetar o outro."""
        r1 = FetchResult(items=[1])
        r2 = FetchResult(items=[2])

        # Listas default sao objetos distintos por instancia.
        assert r1.errors is not r2.errors
        assert r1.metadata is not r2.metadata

        # Evolucao de estado via copia defensiva em r1.
        r1_novo = r1.with_error("Timeout", {"url": "https://x"})

        assert r1.errors == []
        assert r2.errors == []  # segunda instancia permanece intocada
        assert len(r1_novo.errors) == 1

    def test_default_factory_isola_dicts_entre_instancias(self) -> None:
        """Mutar o dict default de um objeto nao vaza para o outro."""
        r1 = FetchResult(items=[])
        r2 = FetchResult(items=[])
        r1.metadata["source"] = "senado"  # brecha interna controlada p/ teste

        assert r2.metadata == {}

    def test_default_factory_de_ingest_result(self) -> None:
        """Contadores zerados e colecoes independentes por instancia."""
        r1 = IngestResult()
        r2 = IngestResult()
        assert r1.ingested_ids is not r2.ingested_ids
        assert r1.errors is not r2.errors
        assert r1.success_count == 0 and r1.failure_count == 0
        assert isinstance(r1.ingested_at, datetime)

    def test_default_factory_de_validation_result(self) -> None:
        """Violacoes e timestamp com defaults independentes."""
        v1 = ValidationResult(is_valid=True)
        v2 = ValidationResult(is_valid=True)
        assert v1.violations is not v2.violations
        assert v1.violations == []
        assert isinstance(v1.validated_at, datetime)

    def test_default_factory_de_component_metrics(self) -> None:
        """Snapshot nasce zerado, PRONTO e sem ultima execucao."""
        metrics = ComponentMetrics(component_id="ingestor_neo4j")
        assert metrics.execution_count == 0
        assert metrics.success_rate == 0.0
        assert metrics.average_duration == 0.0
        assert metrics.error_rate == 0.0
        assert metrics.last_execution is None
        assert metrics.status is ComponentStatus.PRONTO
        assert isinstance(metrics.collected_at, datetime)


# ---------------------------------------------------------------------------
# 6.5. Testes de Gestão (ComponentMetrics)
# ---------------------------------------------------------------------------
class TestComponentMetricsGestao:
    """Valida o contrato de telemetria do Grupo B (Gestao)."""

    def test_instanciacao_com_snapshot_inicial(self) -> None:
        """``last_execution=None`` e ``status=ComponentStatus.PRONTO``."""
        metrics = ComponentMetrics(
            component_id="fetcher_camara",
            last_execution=None,
            status=ComponentStatus.PRONTO,
        )
        assert metrics.last_execution is None
        assert metrics.status == ComponentStatus.PRONTO

    def test_status_possui_tipagem_rigida_de_enum(self) -> None:
        """O tipo de ``status`` deve ser ``ComponentStatus`` (sem string magica)."""
        metrics = ComponentMetrics(component_id="c1")
        assert isinstance(metrics.status, ComponentStatus)
        assert type(metrics.status) is ComponentStatus

    def test_proveniencia_de_gestao_sem_execution_id(self) -> None:
        """Contrato de Gestao diferencia-se do Dominio: nao tem ``execution_id``."""
        campos = {f.name for f in dataclasses.fields(ComponentMetrics)}
        assert "component_id" in campos
        assert "collected_at" in campos
        assert "execution_id" not in campos

        metrics = ComponentMetrics(component_id="c1")
        assert metrics.component_id == "c1"
        assert isinstance(metrics.collected_at, datetime)

    def test_component_status_enum_valores(self) -> None:
        """Enumeracao cobre os quatro estados do ciclo de vida (v2, 3.2.1)."""
        assert {s.value for s in ComponentStatus} == {
            "PRONTO",
            "EXECUTANDO",
            "DEGRADADO",
            "PARADO",
        }
        assert ComponentStatus.DEGRADADO.value == "DEGRADADO"

    def test_component_status_e_compativel_com_str(self) -> None:
        """``ComponentStatus(str, Enum)`` mantem interoperabilidade de str."""
        assert isinstance(ComponentStatus.PARADO, str)
        assert ComponentStatus.EXECUTANDO == "EXECUTANDO"

    def test_snapshot_completo_de_telemetria(self) -> None:
        """Todos os indicadores operacionais do molde v2 estao presentes."""
        agora = datetime(2026, 10, 22, 12, 0, 0)
        metrics = ComponentMetrics(
            component_id="transformer_llm",
            collected_at=agora,
            execution_count=42,
            success_rate=95.5,
            average_duration=3.14,
            error_rate=4.5,
            last_execution=agora,
            status=ComponentStatus.DEGRADADO,
        )
        assert metrics.execution_count == 42
        assert metrics.success_rate == 95.5
        assert metrics.average_duration == 3.14
        assert metrics.error_rate == 4.5
        assert metrics.last_execution == agora
        assert metrics.status is ComponentStatus.DEGRADADO

    def test_entidades_de_dominio_sao_dataclasses_frozen(self) -> None:
        """Barreira estrutural: todas as 4 entidades usam ``frozen=True``."""
        classes: List[Type[object]] = [
            FetchResult,
            IngestResult,
            ValidationResult,
            ComponentMetrics,
        ]
        for cls in classes:
            assert dataclasses.is_dataclass(cls)
            params = dataclasses.fields(cls)  # smoke: e dataclass materializada
            assert len(params) > 0
            frozen = getattr(cls, "__dataclass_params__").frozen
            assert frozen is True
