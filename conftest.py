"""Configuracao raiz do pytest para o projeto MCA-Solo.

Garante que os pacotes de producao (``framework``, ``application``) sejam
importaveis de forma deterministica em qualquer ambiente (local ou CI):

1. Insere a raiz do projeto no inicio de ``sys.path``.
2. Preimporta o pacote de producao ``framework`` antes da coleta dos testes,
   evitando colisao de homonimo com o pacote de testes ``tests.framework``
   (em modos de importacao legacy, ``tests/`` no ``sys.path`` faria
   ``import framework`` resolver para ``tests/framework``).
"""

import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent)

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Preimport do pacote de producao: registra 'framework' -> <raiz>/framework
# e todos os submodulos acessiveis (framework.core, framework.execution...).
import framework  # noqa: E402,F401
import framework.core  # noqa: E402,F401
import framework.core.exceptions  # noqa: E402,F401
