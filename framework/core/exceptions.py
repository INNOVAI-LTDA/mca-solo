"""Hierarquia de excecoes padronizadas do Core do MCA-Solo (ID 1.1).

Este modulo define a arvore de excecoes do framework, utilizada pelo
Involucre de Gestao para classificar falhas, gerar logs estruturados (JSON)
e correlacionar traces sem conhecer a ferramenta interna do componente.

Regra de Ouro: a excecao nao e apenas um mecanismo de interrupcao de fluxo;
ela e o veiculo de transporte de contexto de falha para a camada de
Observabilidade (6 Sinais: Metricas, Logs, Traces, Explicabilidade,
Responsabilizacao, Auditabilidade).

Classes expostas:
    - FrameworkError: base de todas as excecoes do framework.
    - ConfigurationError: YAML da DAG invalido, env vars ausentes, manifesto
      malformado.
    - FetcherError: erro de rede, timeout ou payload inesperado de API
      externa.
    - IngestorError: falha de escrita no destino (Neo4j, Postgres) ou queda
      de conexao com o grafo.
    - TransformerError: falha de processamento de dados (LLM retornando JSON
      invalido, erro de parsing de URI).
    - ValidationError: violacao de invariantes de dominio (K1-K3 de Kelsen,
      schema LRMoo).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional


class FrameworkError(Exception):
    """Erro generico do framework, base de toda a hierarquia de excecoes.

    Deve ser levantada quando nenhum subtipo mais especifico se aplicar.
    O Involucre de Gestao pode capturar qualquer erro do framework com um
    unico bloco ``except FrameworkError``.

    Attributes:
        message: Mensagem legivel do erro (str).
        context: Dicionario de metadados para observabilidade. E copiado de
            forma defensiva no construtor, garantindo imutabilidade externa,
            e exposto como propriedade de apenas leitura.
        cause: Excecao original que deu origem a este erro, preservando o
            encadeamento nativo do Python (``raise ... from ...``).

    Examples:
        >>> err = FrameworkError("Falha generica", context={"dag": "d1"})
        >>> err.message
        'Falha generica'
        >>> err.context["dag"]
        'd1'
        >>> try:
        ...     raise ValueError("origem")
        ... except ValueError as exc:
        ...     raise FrameworkError("falha", cause=exc)
        Traceback (most recent call last):
          ...
        framework.core.exceptions.FrameworkError: falha
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        """Inicializa a excecao base do framework.

        Args:
            message: Mensagem legivel do erro.
            context: Metadados estruturados para observabilidade. Uma copia
                defensiva e armazenada internamente; ``None`` vira ``{}``.
            cause: Excecao original encadeada, passada ao construtor nativo
                para preservar o traceback (suporte a ``raise from``).
        """
        super().__init__(message)
        self._message: str = message
        self._context: Dict[str, Any] = copy.deepcopy(context) if context else {}
        self._cause: Optional[BaseException] = cause
        # Encadeamento explicito: preserva o traceback original e da suporte
        # nativo ao padrao `raise ... from ...` do Python.
        if cause is not None:
            self.__cause__ = cause

    @property
    def message(self) -> str:
        """Retorna a mensagem legivel do erro (apenas leitura)."""
        return self._message

    @property
    def context(self) -> Dict[str, Any]:
        """Retorna o dicionario de metadados (apenas leitura, copia defensiva)."""
        return self._context

    @property
    def cause(self) -> Optional[BaseException]:
        """Retorna a excecao original encadeada (apenas leitura)."""
        return self._cause

    def __str__(self) -> str:
        """Formata a mensagem com o contexto para logs estruturados."""
        if self._context:
            return f"{self._message} | context={self._context}"
        return self._message


class ConfigurationError(FrameworkError):
    """Erro de configuracao do framework ou de componentes.

    Levantar quando o YAML da DAG for invalido, faltarem variaveis de
    ambiente ou o manifesto do componente estiver malformado.

    Attributes:
        message: Mensagem legivel do erro (str).
        context: Dicionario de metadados para observabilidade (copia
            defensiva, propriedade de apenas leitura).
        cause: Excecao original que deu origem ao erro (encadeamento nativo).

    Examples:
        >>> try:
        ...     config = load_yaml("dag.yaml")  # noqa
        ... except FileNotFoundError as exc:
        ...     raise ConfigurationError(
        ...         "DAG nao encontrada",
        ...         context={"path": "dag.yaml"},
        ...         cause=exc,
        ...     ) from exc
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        """Inicializa o erro de configuracao.

        Args:
            message: Mensagem legivel do erro.
            context: Metadados estruturados para observabilidade (copia
                defensiva automatica; ``None`` vira ``{}``).
            cause: Excecao original encadeada para preservar o traceback.
        """
        super().__init__(message, context=context, cause=cause)


class FetcherError(FrameworkError):
    """Erro em operacoes de extracao de dados (Fetchers).

    Levantar quando a API externa (ex.: Senado, DOU) retornar erro de rede,
    timeout, ou payload inesperado.

    Attributes:
        message: Mensagem legivel do erro (str).
        context: Dicionario de metadados para observabilidade (copia
            defensiva, propriedade de apenas leitura).
        cause: Excecao original que deu origem ao erro (encadeamento nativo).

    Examples:
        >>> try:
        ...     response = requests.get(url, timeout=15)  # noqa
        ... except TimeoutError as original_error:
        ...     raise FetcherError(
        ...         "Timeout na API do Senado",
        ...         context={"url": url, "timeout": 15},  # noqa
        ...         cause=original_error,
        ...     ) from original_error
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        """Inicializa o erro de fetch.

        Args:
            message: Mensagem legivel do erro.
            context: Metadados estruturados para observabilidade (copia
                defensiva automatica; ``None`` vira ``{}``).
            cause: Excecao original encadeada para preservar o traceback.
        """
        super().__init__(message, context=context, cause=cause)


class IngestorError(FrameworkError):
    """Erro em operacoes de ingestao de dados (Ingestores).

    Levantar quando a escrita no destino (ex.: Neo4j, Postgres) falhar, ou a
    conexao com o grafo cair.

    Attributes:
        message: Mensagem legivel do erro (str).
        context: Dicionario de metadados para observabilidade (copia
            defensiva, propriedade de apenas leitura).
        cause: Excecao original que deu origem ao erro (encadeamento nativo).

    Examples:
        >>> try:
        ...     graph.run(query)  # noqa
        ... except ConnectionError as original_error:
        ...     raise IngestorError(
        ...         "Conexao com o Neo4j caiu",
        ...         context={"destination": "neo4j"},
        ...         cause=original_error,
        ...     ) from original_error
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        """Inicializa o erro de ingestao.

        Args:
            message: Mensagem legivel do erro.
            context: Metadados estruturados para observabilidade (copia
                defensiva automatica; ``None`` vira ``{}``).
            cause: Excecao original encadeada para preservar o traceback.
        """
        super().__init__(message, context=context, cause=cause)


class TransformerError(FrameworkError):
    """Erro em operacoes de transformacao de dados (Transformers).

    Levantar quando o processamento de dados falhar (ex.: LLM retornar JSON
    invalido, erro de parsing de URI).

    Attributes:
        message: Mensagem legivel do erro (str).
        context: Dicionario de metadados para observabilidade (copia
            defensiva, propriedade de apenas leitura).
        cause: Excecao original que deu origem ao erro (encadeamento nativo).

    Examples:
        >>> try:
        ...     data = json.loads(llm_output)  # noqa
        ... except json.JSONDecodeError as original_error:
        ...     raise TransformerError(
        ...         "LLM retornou JSON invalido",
        ...         context={"component": "norma_parser"},
        ...         cause=original_error,
        ...     ) from original_error
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        """Inicializa o erro de transformacao.

        Args:
            message: Mensagem legivel do erro.
            context: Metadados estruturados para observabilidade (copia
                defensiva automatica; ``None`` vira ``{}``).
            cause: Excecao original encadeada para preservar o traceback.
        """
        super().__init__(message, context=context, cause=cause)


class ValidationError(FrameworkError):
    """Erro de validacao de dados contra invariantes de dominio.

    Levantar quando os dados violarem invariantes de dominio (ex.:
    Invariantes K1-K3 de Kelsen, ou schema LRMoo).

    Attributes:
        message: Mensagem legivel do erro (str).
        context: Dicionario de metadados para observabilidade (copia
            defensiva, propriedade de apenas leitura).
        cause: Excecao original que deu origem ao erro (encadeamento nativo).

    Examples:
        >>> try:
        ...     validar_kelsen(norma)  # noqa
        ... except AssertionError as original_error:
        ...     raise ValidationError(
        ...         "Violacao da invariante K2",
        ...         context={"urn": urn, "invariante": "K2"},  # noqa
        ...         cause=original_error,
        ...     ) from original_error
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        """Inicializa o erro de validacao.

        Args:
            message: Mensagem legivel do erro.
            context: Metadados estruturados para observabilidade (copia
                defensiva automatica; ``None`` vira ``{}``).
            cause: Excecao original encadeada para preservar o traceback.
        """
        super().__init__(message, context=context, cause=cause)


__all__ = [
    "FrameworkError",
    "ConfigurationError",
    "FetcherError",
    "IngestorError",
    "TransformerError",
    "ValidationError",
]
