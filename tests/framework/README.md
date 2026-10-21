# 🧪 Testes da Camada Core — `tests/framework/`

Guia de validação manual da suíte de testes do **Milestone M1 — Core Framework**,
com foco no artefato da **Especificação Técnica ID 1.1** (Hierarquia de Exceções do Core).

| Artefato de produção | Artefato de teste | Status esperado |
| :--- | :--- | :--- |
| `framework/core/exceptions.py` | `test_core_exceptions.py` | ✅ Implementado (ID 1.1) |
| `framework/core/dags` | `test_core_dags.py` | ⏳ Placeholder (vazio) |
| `framework/execution/*` | `test_execution.py` | ⏳ Placeholder (vazio) |
| `framework/management/*` | `test_management.py` | ⏳ Placeholder (vazio) |

---

## 1. Pré-requisitos

- **Python ≥ 3.10** (ambiente homologado: **3.12**).
- Dependências de teste declaradas na raiz do projeto em [`requirements.txt`](../../requirements.txt):
  `pytest`, `pytest-cov`, `coverage`, `mypy`, `black`, `flake8`.

> ℹ️ O módulo `framework/core/exceptions.py` usa apenas a biblioteca padrão (`copy`, `typing`).
> As dependências abaixo servem exclusivamente para o pipeline de teste/validação estática (Seção 7 da spec).

### 1.1. Instalação do ambiente

```bash
# A partir da RAIZ do projeto (/workspace ou clone local)
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Verifique as versões instaladas:

```bash
python --version        # Python 3.12.x
pytest --version        # pytest >= 8.0
mypy --version          # mypy >= 1.10
black --version         # black >= 24.0
flake8 --version        # flake8 >= 7.0
```

---

## 2. Configuração do Pytest (por que basta rodar da raiz)

A execução é determinística graças a dois arquivos na **raiz do projeto**:

- **`pytest.ini`** — define `testpaths = tests`, `python_files = test_*.py` e
  `--import-mode=importlib`.
- **`conftest.py`** — insere a raiz do projeto no `sys.path` e **preimporta**
  o pacote de produção `framework` antes da coleta dos testes, evitando a
  colisão de homônimo com o pacote de testes `tests/framework`.

⚠️ **Importante:** execute os comandos sempre a partir da **raiz do repositório**
(diretório que contém `pytest.ini`), nunca de dentro de `tests/framework/`. Não é
necessário definir `PYTHONPATH` nem instalar o projeto como pacote.

---

## 3. Execução dos testes (Seção 6 da especificação)

### 3.1. Suíte completa, modo verboso (recomendado)

```bash
pytest tests/framework/test_core_exceptions.py -v
```

Saída esperada: **110 testes passando** (`110 passed`), organizados nas 4 categorias da Seção 6:

| Classe de teste | Categoria da spec | O que valida |
| :--- | :--- | :--- |
| `TestInstanciacaoEContratos` | **6.1** | Instanciação só com `message`; atributo `message` acessível; `context` padrão `{}`; `cause` padrão `None`; `__str__` enriquecido |
| `TestImutabilidadeDoContexto` | **6.2** | Cópia defensiva (mutar o dict original não afeta a exceção); deep copy de estruturas aninhadas; propriedades `message`/`context`/`cause` read-only (`AttributeError`) |
| `TestHerancaECaptura` | **6.3** | `isinstance(x, FrameworkError)` para as 5 subclasses; herança direta; captura polimórfica via `except FrameworkError` |
| `TestEncadeamento` | **6.4** | `raise ... from ...` preserva `__cause__`; construtor com `cause=` popula `__cause__`; ausência de `cause` mantém `__cause__ is None` |

### 3.2. Execução granular (útil para depurar um cenário específico)

```bash
# Uma categoria inteira (ex.: imutabilidade — crítica para Observabilidade)
pytest tests/framework/test_core_exceptions.py::TestImutabilidadeDoContexto -v

# Um único teste
pytest "tests/framework/test_core_exceptions.py::TestEncadeamento::test_args_contem_cause_para_classe_base" -v

# Apenas casos parametrizados específicos (ex.: ValidationError)
pytest tests/framework/test_core_exceptions.py -k "ValidationError" -v
```

### 3.3. Toda a pasta `tests/framework/`

```bash
pytest tests/framework/ -v
```

Os demais arquivos (`test_core_dags.py`, `test_execution.py`, `test_management.py`)
são placeholders vazios até suas respectivas tasks; o resultado deve ser
`no tests ran in <arquivo>` para eles, sem erros de coleta.

---

## 4. Cobertura de código (meta: 100%)

```bash
pytest --cov=framework.core.exceptions --cov-report=term-missing tests/framework/test_core_exceptions.py
```

Saída esperada — **zero linhas faltantes**:

```
Name                           Stmts   Miss  Cover   Missing
------------------------------------------------------------
framework/core/exceptions.py      40      0   100%
------------------------------------------------------------
TOTAL                             40      0   100%
```

Relatório HTML opcional (abrir `htmlcov/index.html` no navegador):

```bash
pytest --cov=framework.core.exceptions --cov-report=html tests/framework/test_core_exceptions.py
```

---

## 5. Validação estática (Seção 7 da especificação)

Execute os três verificadores a partir da raiz do projeto:

```bash
# Type hints (PEP 484) — esperado: "Success: no issues found in 1 source file"
mypy framework/core/exceptions.py

# Formatação PEP 8 — esperado: "All done! ✨ 🍰 ✨ ... left unchanged"
black --check framework/core/exceptions.py tests/framework/test_core_exceptions.py

# Linter — ver nota 5.1 sobre o max-line-length
flake8 --max-line-length=88 framework/core/exceptions.py tests/framework/test_core_exceptions.py
```

> 💡 Para corrigir formatação automaticamente: `black framework/core/exceptions.py tests/framework/test_core_exceptions.py`

### 5.1. Nota sobre flake8 × black

O `black` usa largura de linha de **88 caracteres** (padrão da comunidade), enquanto o
`flake8` padrão reclama a partir de **80**. Por isso o comando acima inclui
`--max-line-length=88`, alinhando os dois ferramentas. Alternativa permanente: criar um
`.flake8` na raiz com:

```ini
[flake8]
max-line-length = 88
extend-ignore = E203, W503
```

---

## 6. Checklist de validação manual (Definition of Done — ID 1.1)

Rode tudo em sequência e confira cada resultado:
- Linux:
```bash
pytest tests/framework/test_core_exceptions.py -v \
  && pytest --cov=framework.core.exceptions --cov-report=term-missing tests/framework/test_core_exceptions.py \
  && mypy framework/core/exceptions.py \
  && black --check framework/core/exceptions.py tests/framework/test_core_exceptions.py \
  && flake8 --max-line-length=88 framework/core/exceptions.py tests/framework/test_core_exceptions.py \
  && echo "✅ ID 1.1: todos os gateways de qualidade passaram"
```
- Powershell (5.1):
```ps
& {
    pytest tests/framework/test_core_exceptions.py -v
    if ($LastExitCode -ne 0) { return }
    pytest --cov=framework.core.exceptions --cov-report=term-missing tests/framework/test_core_exceptions.py
    if ($LastExitCode -ne 0) { return }
    mypy framework/core/exceptions.py
    if ($LastExitCode -ne 0) { return }
    black --check framework/core/exceptions.py tests/framework/test_core_exceptions.py
    if ($LastExitCode -ne 0) { return }
    flake8 --max-line-length=88 framework/core/exceptions.py tests/framework/test_core_exceptions.py
    if ($LastExitCode -ne 0) { return }
    Write-Output "✅ ID 1.1: todos os gateways de qualidade passaram"
}
```

- [ ] `pytest`: **110 passed**, 0 failed, 0 errors.
- [ ] Cobertura de `framework/core/exceptions.py`: **100%** (coluna *Missing* vazia).
- [ ] `mypy`: nenhum erro de tipagem.
- [ ] `black --check`: arquivos inalterados (formatados).
- [ ] `flake8`: exit code `0` (sem violações com `--max-line-length=88`).

---

## 7. Solução de problemas

| Sintoma | Causa provável | Correção |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'framework'` | Pytest executado fora da raiz do projeto, sem o `conftest.py` raiz | Rodar a partir do diretório que contém `pytest.ini` |
| `ImportError` ao importar `tests.framework` colidindo com `framework` de produção | Uso de `--import-mode=prepend`/legacy manualmente | Manter `--import-mode=importlib` definido em `pytest.ini` |
| `command not found: pytest` | Ambiente virtual não ativado ou deps não instaladas | `source .venv/bin/activate` e `pip install -r requirements.txt` |
| Erro na inicialização citando um plugin de terceiros (ex.: `libtmux`) | Plugin instalado **globalmente** e carregado automaticamente pelo pytest, incompatível com a versão instalada do pytest | Desative o plugin na linha de comando: `pytest -p no:libtmux tests/framework/test_core_exceptions.py -v`, ou remova-o do ambiente global (`pip uninstall pytest-libtmux`). Em último caso, recrie o venv limpo conforme §1.1 |
| Cobertura mostra `0%` ou módulo não rastreado | Nome do alvo incorreto no `--cov` | Usar exatamente `--cov=framework.core.exceptions` (notação de ponto, caminho importável) |

---

## 8. Referências

- Especificação Técnica ID 1.1 — Seções 6 (estratégia de testes) e 7 (ferramentas).
- `docs/contracts.md`, `docs/observability.md` — contratos do Invólucro de Gestão.
- [`requirements.txt`](../../requirements.txt) — dependências fixadas do pipeline.
