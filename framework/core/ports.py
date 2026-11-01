"""Portas de domínio (ABCs) do Core Framework do MCA-Solo (ID 1.3).

Este módulo materializa o contrato formal das **portas de domínio** no
padrão Arquitetura Hexagonal (Ports & Adapters), conforme as Seções 3 e 5
de ``docs/contracts.md``, a Seção 2 de
``docs/arquitetura_molde_v2_orquestracao_gestao.md`` e ``docs/examples.md``.

Componentes heterogêneos (fetchers de APIs governamentais, ingestors em
Neo4j, transformers baseados em LLM, validators kelsenianos, geradores de
URN) precisam de um contrato que garanta sua substituibilidade e permita
que o framework os orquestre e gerencie de forma uniforme.

Escolha arquitetural -- subtipagem nominal via ABCs: embora
``docs/contracts.md`` originalmente use ``typing.Protocol`` (subtipagem
estrutural, PEP 544), o núcleo imutável do framework adota ``abc.ABC``
(subtipagem nominal) porque:

1. **Validação em tempo de execução**: tentar instanciar uma classe que não
   implementou todos os métodos abstratos levanta ``TypeError``
   imediatamente, capturando erros de contrato antes do deploy.
2. **Vínculo explícito e auditável**: a herança cria uma relação verificável
   entre adaptador e contrato, fortalecendo o Liskov Substitution Principle
   (LSP).
3. **Ecossistema maduro de testes**: mixins de teste baseados em ABCs são
   idiomáticos em ``pytest``, permitindo reutilizar suítes de contrato entre
   múltiplos adaptadores.
4. **Alinhamento com o axioma AX-02** (``v1``): "Todo componente registrado
   é gerido" -- a herança nominal garante que o registro possa verificar
   contratualmente a conformidade.

Regra de Ouro: todo componente registrado no MCA-Solo deve herdar
nominalmente de uma ABC de porta definida neste módulo. A herança é o
mecanismo de validação em tempo de execução; a ausência de herança é uma
falha de contrato que impede o registro.

Taxonomia das portas (fluxo de dados):
    - FetcherPort (Entrada / Driving): ``None`` -> ``FetchResult``.
    - IngestPort (Saída / Driven): ``FetchResult`` -> ``IngestResult``.
    - TransformerPort (Processamento): ``FetchResult`` -> ``FetchResult``.
    - ValidatorPort (Validação): ``List[Dict]`` -> ``ValidationResult``.
    - URNPort (Identificação): ``Dict`` -> ``str`` (``urn:lex:br:...``).

Dependências: este módulo depende exclusivamente das entidades de domínio
de ``framework.core.entities`` (dependência unidirecional ports -> entities,
nunca o contrário). Não há imports de ``application/`` nem de
``framework/execution/`` -- as portas são o lado estável do hexágono.

Compatibilidade futura: as ABCs serão envolvidas pelo ``InvolucroGestao``
(Issue 2.x), que espera os métodos ``identificador()``,
``versao_contrato()`` e ``manifesto()``. Tais métodos serão adicionados via
``ContratoComponente`` em épico posterior, não nesta Issue.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List

from framework.core.entities import FetchResult, IngestResult, ValidationResult

__all__ = [
    "FetcherPort",
    "IngestPort",
    "TransformerPort",
    "URNPort",
    "ValidatorPort",
]


class FetcherPort(abc.ABC):
    """Contrato para fontes de dados (adapters de entrada/driving).

    Pre-condicoes:
        - config e um dicionario valido para o fetcher especifico
        - validar_config(config) retorna True

    Pos-condicoes:
        - Retorna FetchResult com items, metadata e errors
        - items e uma lista de dicionarios com proveniencia completa
        - errors contem falhas nao fatais (quando aplicavel)

    Invariantes:
        - buscar nunca retorna items parcialmente marcados como integros
        - Falha de contrato levanta excecao tipada, nunca retorno silencioso

    Examples:
        Implementações esperadas: ``SenadoAdapter``, ``NCMAdapter``,
        ``RoDOUAdapter``, ``CarfAdapter``.
    """

    @abc.abstractmethod
    def buscar(self, config: Dict[str, Any]) -> FetchResult:
        """Extrai dados da fonte externa.

        Args:
            config: Configuracao especifica do fetcher (URLs, filtros, etc.)

        Returns:
            FetchResult com os dados extraidos.

        Raises:
            FetcherError: Se a extracao falhar de forma irrecuperavel.
            ConfigurationError: Se a configuracao for invalida.
        """
        ...

    @abc.abstractmethod
    def validar_config(self, config: Dict[str, Any]) -> bool:
        """Valida se a configuracao e valida para este fetcher.

        Args:
            config: Configuracao a ser validada.

        Returns:
            True se valida, False caso contrario.

        Raises:
            ConfigurationError: Se a estrutura da configuracao for
                irremediavelmente invalida (em vez de apenas incompleta).
        """
        ...

    @abc.abstractmethod
    def metadados(self) -> Dict[str, Any]:
        """Retorna metadados sobre o fetcher (versao, capacidades, etc.).

        Args:
            (nenhum)

        Returns:
            Dicionario com metadados do fetcher (ex.: versao, capacidades).

        Raises:
            FetcherError: Se os metadados nao puderem ser determinados.
        """
        ...


class IngestPort(abc.ABC):
    """Contrato para destinos de dados (adapters de saida/driven).

    Pre-condicoes:
        - dados e um FetchResult valido
        - validar_conexao() retorna True

    Pos-condicoes:
        - Retorna IngestResult com contadores de sucesso e falha
        - ingested_ids contem identificadores dos itens ingeridos
        - errors contem falhas individuais (quando aplicavel)

    Invariantes:
        - ingerir nunca corrompe dados ja persistidos
        - Falha de contrato levanta excecao tipada

    Examples:
        Implementações esperadas: ``Neo4jAdapter``, ``PostgresAdapter``,
        ``OpenSearchAdapter``.
    """

    @abc.abstractmethod
    def ingerir(self, dados: FetchResult) -> IngestResult:
        """Ingesta dados no destino.

        Args:
            dados: Dados extraidos pelo fetcher (``FetchResult`` valido).

        Returns:
            IngestResult com estatisticas da ingestao.

        Raises:
            IngestorError: Se a ingestao falhar de forma irrecuperavel.
        """
        ...

    @abc.abstractmethod
    def validar_conexao(self) -> bool:
        """Valida se a conexao com o destino esta funcionando.

        Args:
            (nenhum)

        Returns:
            True se conectavel, False caso contrario.

        Raises:
            IngestorError: Se a validacao de conexao falhar de forma
                irrecuperavel (ex.: credenciais ausentes).
        """
        ...

    @abc.abstractmethod
    def metadados(self) -> Dict[str, Any]:
        """Retorna metadados sobre o ingestor.

        Args:
            (nenhum)

        Returns:
            Dicionario com metadados do ingestor (ex.: backend, versao).

        Raises:
            IngestorError: Se os metadados nao puderem ser determinados.
        """
        ...


class TransformerPort(abc.ABC):
    """Contrato para transformacao de dados.

    Pre-condicoes:
        - dados e um FetchResult valido

    Pos-condicoes:
        - Retorna FetchResult com dados transformados
        - Metadados originais sao preservados

    Invariantes:
        - transformar nunca remove proveniencia
        - Falha de contrato levanta excecao tipada

    Examples:
        Implementações esperadas: ``MatchEngineAdapter``,
        ``LLMProcessorAdapter``, ``NormalizerAdapter``.
    """

    @abc.abstractmethod
    def transformar(self, dados: FetchResult) -> FetchResult:
        """Transforma dados extraidos.

        Args:
            dados: Dados de entrada (``FetchResult`` valido).

        Returns:
            FetchResult com dados transformados e proveniencia preservada.

        Raises:
            TransformerError: Se a transformacao falhar de forma
                irrecuperavel (ex.: LLM retornando JSON malformado).
        """
        ...

    @abc.abstractmethod
    def transformacoes(self) -> List[str]:
        """Retorna lista de transformacoes aplicadas.

        Args:
            (nenhum)

        Returns:
            Lista de nomes (identificadores) das transformacoes que este
            componente aplica.

        Raises:
            TransformerError: Se as transformacoes nao puderem ser
                enumeradas.
        """
        ...


class ValidatorPort(abc.ABC):
    """Contrato para validacao de invariantes de dominio.

    Pre-condicoes:
        - dados e uma lista de itens a serem validados

    Pos-condicoes:
        - Retorna ValidationResult indicando validade e violacoes
        - violacoes contem detalhes de cada regra violada

    Invariantes:
        - validar nunca modifica os dados de entrada
        - Falha de contrato levanta excecao tipada

    Examples:
        Implementações esperadas: ``InvariantsValidator``,
        ``SchemaValidator``, ``KelsenValidator``.
    """

    @abc.abstractmethod
    def validar(self, dados: List[Dict[str, Any]]) -> ValidationResult:
        """Valida dados contra regras de negocio.

        Args:
            dados: Dados a serem validados (lista de itens/dicionarios).

        Returns:
            ValidationResult indicando se e valido e as violacoes
            encontradas.

        Raises:
            ValidationError: Se a validacao em si falhar de forma
                irrecuperavel (ex.: schema base indisponivel).
        """
        ...

    @abc.abstractmethod
    def regras(self) -> List[str]:
        """Retorna lista de regras que este validator aplica.

        Args:
            (nenhum)

        Returns:
            Lista de identificadores das regras aplicadas (ex.: regras
            kelsenianas K1-K3).

        Raises:
            ValidationError: Se as regras nao puderem ser enumeradas.
        """
        ...


class URNPort(abc.ABC):
    """Contrato para geracao e validacao de URNs canonicos.

    Pre-condicoes:
        - dados contem campos necessarios para geracao do URN

    Pos-condicoes:
        - Retorna URN no formato urn:lex:br:...
        - URN e unico e deterministico para os mesmos dados

    Invariantes:
        - gerar sempre retorna o mesmo URN para os mesmos dados
        - validar retorna True apenas para URNs no formato correto

    Examples:
        Implementações esperadas: ``LexURNGenerator``,
        ``CustomURNGenerator``.
    """

    @abc.abstractmethod
    def gerar(self, dados: Dict[str, Any]) -> str:
        """Gera URN canonico a partir de dados.

        Args:
            dados: Dados da norma/elemento (jurisdicao, tipo, data, numero).

        Returns:
            URN canonico (ex.: "urn:lex:br:federal:lei:2004-03-01;10865").

        Raises:
            ConfigurationError: Se campos obrigatorios estiverem ausentes.
            ValidationError: Se o URN gerado violar o formato canonico.
        """
        ...

    @abc.abstractmethod
    def validar(self, urn: str) -> bool:
        """Valida se um URN esta no formato correto.

        Args:
            urn: String do URN a ser validada.

        Returns:
            True se o URN esta no formato canonico, False caso contrario.

        Raises:
            ValidationError: Se a validacao estrutural falhar de forma
                irrecuperavel.
        """
        ...

    @abc.abstractmethod
    def parsear(self, urn: str) -> Dict[str, Any]:
        """Faz parse de um URN em seus componentes.

        Args:
            urn: String do URN canonico a ser decomposto.

        Returns:
            Dicionario com os componentes do URN (ex.: pais, jurisdicao,
            tipo, data, numero).

        Raises:
            ValidationError: Se o URN nao estiver no formato canonico e
                nao puder ser decomposto.
        """
        ...
