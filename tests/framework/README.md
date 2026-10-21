# 🧪 Testes da Camada Core — `tests/framework/`

Guia de validação manual da suíte de testes do **Milestone M1 — Core Framework**,
cobrindo os artefatos das **Especificações Técnicas ID 1.1** (Hierarquia de Exceções
do Core) e **ID 1.2** (Contratos de Dados e Gestão Imutáveis).

| Artefato de produção | Artefato de teste | Status esperado |
| :--- | :--- | :--- |
| `framework/core/exceptions.py` | `test_core_exceptions.py` | ✅ Implementado (ID 1.1) — 110 testes |
| `framework/core/entities.py` | `test_core_entities.py` | ✅ Implementado (ID 1.2) — 33 testes |
| `framework/core/dags` | `test_core_dags.py` | ⏳ Placeholder (vazio) |
| `framework/execution/*` | `test_execution.py` | ⏳ Placeholder (vazio) |
| `framework/management/*` | `test_management.py` | ⏳ Placeholder (vazio) |

> 📦 Dependências: além do [`requirements.txt`](../../requirements.txt) da raiz, esta
> pasta contém um [`requirements.txt`](requirements.txt) local com as mesmas fixações,
> permitindo reinstalar o pipeline de teste de forma autônoma a partir daqui.

---

## 1. Pré-requisitos

- **Python ≥ 3.10** (ambiente homologado: **3.12**).
- Dependências de teste declaradas na raiz do projeto em [`requirements.txt`](../../requirements.txt)
  — e replicadas no [`requirements.txt`](requirements.txt) **local desta pasta** —:
  `pytest`, `pytest-cov`, `coverage`, `mypy`, `black`, `flake8`.

> ℹ️ Os módulos avaliados (`framework/core/exceptions.py` e `framework/core/entities.py`)
> usam apenas a biblioteca padrão (`copy`, `typing`, `dataclasses`, `datetime`, `enum`).
> As dependências abaixo servem exclusivamente para o pipeline de teste/validação estática
> (Seção 7 das specs ID 1.1 e ID 1.2).

### 1.1. Instalação do ambiente

```bash
# A partir da RAIZ do projeto (/workspace ou clone local)
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell 5.1) — pode ser necessário liberar scripts uma única vez:
#   Set-ExecutionPolicy -Scope CurrentUser ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1

# Instalar as dependências (indistintamente):
pip install -r requirements.txt
# ou, usando o requirements LOCAL desta pasta (mesmas fixações):
pip install -r tests/framework/requirements.txt
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

## 3A. Suíte da Especificação Técnica ID 1.2 — Contratos Imutáveis (`test_core_entities.py`)

Artefato: `framework/core/entities.py` → teste: `tests/framework/test_core_entities.py`.

### 3A.0. Reexecutar TODA a suíte de testes manualmente (visão geral)

A suíte completa do projeto hoje possui **143 testes** distribuídos em:

| Arquivo | Conteúdo | Qtd. esperada |
| :--- | :--- | :--- |
| `tests/framework/test_core_exceptions.py` | Spec ID 1.1 — Hierarquia de Exceções | 110 passed |
| `tests/framework/test_core_entities.py` | Spec ID 1.2 — Contratos Imutáveis | 33 passed |
| `tests/framework/test_core_dags.py` | Placeholder (task futura) | no tests ran |
| `tests/framework/test_execution.py` | Placeholder (task futura) | no tests ran |
| `tests/framework/test_management.py` | Placeholder (task futura) | no tests ran |
| `tests/application/*` | Testes da camada de aplicação | incluídos no total |

**Passo único obrigatório:** posicionar-se na **raiz do repositório** (o diretório que
contém `pytest.ini` e `conftest.py`) antes de qualquer comando — a configuração de
import é determinística justamente por causa desses dois arquivos (ver §2).

- **Linux (bash/zsh):**
```bash
cd /caminho/para/raiz-do-projeto        # ex.: cd ~/mca-solo
source .venv/bin/activate               # ativa o ambiente virtual

# 1) Toda a suíte (todos os diretórios definidos em testpaths=tests)
pytest -v

# 2) equivalentes granulares:
pytest tests/ -v                        # todos os testes
pytest tests/framework/ -v              # somente a camada framework/core
pytest tests/framework/test_core_entities.py -v   # somente a ID 1.2
```

- **PowerShell 5.1:**
```ps
Set-Location C:\caminho\para\raiz-do-projeto    # ex.: Set-Location $env:USERPROFILE\mca-solo
.\.venv\Scripts\Activate.ps1                    # se recusar, rode uma vez:
                                                # Set-ExecutionPolicy -Scope CurrentUser ExecutionPolicy RemoteSigned

# 1) Toda a suíte
pytest -v

# 2) Equivalentes granulares (use \ ou / nos caminhos — ambos funcionam):
pytest tests\ -v
pytest tests\framework\ -v
pytest tests\framework\test_core_entities.py -v
```

> 💡 **Sempre prefira `pytest ...` simples** (com o venv ativado) ou, equivalentemente,
> `python -m pytest ...` — este último garante que o interpretador em uso é o do venv,
> mesmo se você esqueceu de ativá-lo. O executável global `pytest` pode resolver para
> um Python diferente do esperado.

### 3A.1. Execução verbosa da ID 1.2 (recomendada)

- Linux:
```bash
pytest tests/framework/test_core_entities.py -v
```
- PowerShell 5.1:
```ps
pytest tests\framework\test_core_entities.py -v
```

Saída esperada: **33 testes passando** (`33 passed`), organizados pelas 5 classes da Seção 6:

| Classe de teste | Categoria da spec | O que valida |
| :--- | :--- | :--- |
| `TestImutabilidade` | **6.1** | Barreira `frozen`: atribuição em atributo existente/novo levanta `dataclasses.FrozenInstanceError` em `FetchResult`, `IngestResult`, `ValidationResult` e `ComponentMetrics` (inclusive mutation de campos numéricos) |
| `TestCopiaDefensiva` | **6.2** | `with_error()` retorna NOVA instância (`id` diferentes); original permanece `errors == []`; encadeamento preserva snapshots intermediários; cópia defensiva do dict de `contexto`; demais campos preservados via `dataclasses.replace` |
| `TestPropriedadesComputadas` | **6.3** | `has_errors` sse `len(errors) > 0`; `items_count`/`violations_count`; `total_count = success + failure`; `success_rate == 0.0` quando `total_count == 0` (anti `ZeroDivisionError`); invariantes de `is_valid ⟺ violations` (`ValueError` no construtor se violados); propriedades não mutam estado |
| `TestDefaultsEIsolamento` | **6.4** | Duas instâncias sem argumentos possuem coleções/dicts independentes (`default_factory` correto, sem compartilhamento de estado) e defaults corretos para as 4 entidades |
| `TestComponentMetricsGestao` | **6.5** | Snapshot inicial (`last_execution=None`, `status=PRONTO`); tipagem rígida `type(status) is ComponentStatus`; proveniência de gestão (`component_id`, `collected_at`) SEM `execution_id`; valores do Enum e compatibilidade `str`; verificação estrutural de `frozen=True` nas entidades de domínio |

Comandos granulares equivalentes (rode da raiz):

```bash
# Uma categoria inteira (ex.: barreira de imutabilidade — crítica para Auditabilidade)
pytest tests/framework/test_core_entities.py::TestImutabilidade -v

# Um único teste
pytest "tests/framework/test_core_entities.py::TestCopiaDefensiva::test_with_error_preserva_instancia_original" -v

# Filtro por palavra-chave (ex.: todos os cenários de IngestResult)
pytest tests/framework/test_core_entities.py -k "ingest" -v
```

### 3A.3. Cobertura de código (meta ≥ 90%; estado atual: 100%)

```bash
pytest --cov=framework.core.entities --cov-report=term-missing tests/framework/test_core_entities.py
```

Saída esperada — **zero linhas faltantes**:

```
Name                        Stmts   Miss  Cover   Missing
---------------------------------------------------------
framework/core/entities.py     68      0   100%
---------------------------------------------------------
TOTAL                          68      0   100%
```

Relatório HTML opcional (abrir `htmlcov/index.html` no navegador):

```bash
pytest --cov=framework.core.entities --cov-report=html tests/framework/test_core_entities.py
```

### 3A.4. Validação estática da ID 1.2 (Seção 7 da spec)

```bash
mypy framework/core/entities.py            # esperado: Success: no issues found
black --check framework/core/entities.py tests/framework/test_core_entities.py
flake8 --max-line-length=88 framework/core/entities.py tests/framework/test_core_entities.py
```

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

## 6. Checklist de validação manual (Definition of Done)

### 6.1. Reexecução COMPLETA da suíte (todas as tasks do M1, em sequência)

- Linux:
```bash
pytest tests/ -v \
  && pytest --cov=framework.core.exceptions --cov=framework.core.entities --cov-report=term-missing tests/framework/ \
  && mypy framework/core/exceptions.py framework/core/entities.py \
  && black --check framework/ tests/framework/ \
  && flake8 --max-line-length=88 framework/core/ tests/framework/ \
  && echo "✅ M1: todos os gateways de qualidade passaram"
```
- PowerShell 5.1 (não há `&&` no PS 5.1 — encadeie via `$LastExitCode`):
```ps
& {
    pytest tests\ -v
    if ($LastExitCode -ne 0) { return }
    pytest --cov=framework.core.exceptions --cov=framework.core.entities --cov-report=term-missing tests\framework\
    if ($LastExitCode -ne 0) { return }
    mypy framework\core\exceptions.py framework\core\entities.py
    if ($LastExitCode -ne 0) { return }
    black --check framework\ tests\framework\
    if ($LastExitCode -ne 0) { return }
    flake8 --max-line-length=88 framework\core\ tests\framework\
    if ($LastExitCode -ne 0) { return }
    Write-Output "✅ M1: todos os gateways de qualidade passaram"
}
```

Saída esperada da suíte completa: **143 passed** (110 da ID 1.1 + 33 da ID 1.2 + testes
da camada `tests/application/`), com os placeholders reportando `no tests ran`.

### 6.2. Checklist por especificação

**ID 1.1 — Hierarquia de Exceções (`test_core_exceptions.py`):**
- [ ] `pytest`: **110 passed**, 0 failed, 0 errors.
- [ ] Cobertura de `framework/core/exceptions.py`: **100%** (coluna *Missing* vazia).
- [ ] `mypy`: nenhum erro de tipagem.
- [ ] `black --check`: arquivos inalterados (formatados).
- [ ] `flake8`: exit code `0` (sem violações com `--max-line-length=88`).

**ID 1.2 — Contratos Imutáveis (`test_core_entities.py`):**
- [ ] `pytest`: **33 passed**, 0 failed, 0 errors.
- [ ] Cobertura de `framework/core/entities.py`: **100%** (meta da spec: ≥ 90%).
- [ ] `mypy`: nenhum erro de tipagem (foco em `Enum` e `Optional`).
- [ ] `black --check`: arquivos inalterados (formatados).
- [ ] `flake8`: exit code `0` (sem violações com `--max-line-length=88`).

---

## 7. Solução de problemas

| Sintoma | Causa provável | Correção |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'framework'` | Pytest executado fora da raiz do projeto, sem o `conftest.py` raiz | Rodar a partir do diretório que contém `pytest.ini` |
| `ImportError` ao importar `tests.framework` colidindo com `framework` de produção | Uso de `--import-mode=prepend`/legacy manualmente | Manter `--import-mode=importlib` definido em `pytest.ini` |
| `command not found: pytest` | Ambiente virtual não ativado ou deps não instaladas | Linux: `source .venv/bin/activate` · PS 5.1: `.\.venv\Scripts\Activate.ps1` · depois `pip install -r requirements.txt` |
| `python.exe -x.y.dll not found` ao ativar o venv no Windows | Atalho antigo do Python no PATH apontando para versão desinstalada | Use o caminho completo: `& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m pytest ...` ou recrie o venv (§1.1) |
| `Set-ExecutionPolicy` bloqueia `Activate.ps1` no PowerShell 5.1 | Política de execução padrão (`Restricted`) | `Set-ExecutionPolicy -Scope CurrentUser ExecutionPolicy RemoteSigned` (uma única vez) |
| Coleta aborta com `Failed: Marks cannot be applied to fixtures` citando `libtmux` | Plugin instalado **globalmente** e carregado automaticamente pelo pytest, incompatível com a versão instalada do pytest | Desative o plugin na linha de comando: `pytest -p no:libtmux tests/framework/test_core_entities.py -v`, ou remova-o do ambiente global (`pip uninstall pytest-libtmux`). Em último caso, recrie o venv limpo conforme §1.1 |
| Cobertura mostra `0%` ou módulo não rastreado | Nome do alvo incorreto no `--cov` | Usar exatamente `--cov=framework.core.exceptions` / `--cov=framework.core.entities` (notação de ponto, caminho importável) |

---

## 8. Referências

- Especificação Técnica ID 1.1 — Seções 6 (estratégia de testes) e 7 (ferramentas).
- Especificação Técnica ID 1.2 — Seções 6 (cenários 6.1–6.5) e 7 (ferramentas).
- `docs/contracts.md` (Seções 4 e 5), `docs/arquitetura_molde_v2_orquestracao_gestao.md`
  (Seção 3.2.1), `docs/examples.md` — contratos de Domínio e Gestão.
- [`requirements.txt`](requirements.txt) — dependências fixadas locais desta pasta.
- [`../../requirements.txt`](../../requirements.txt) — dependências fixadas da raiz do pipeline.
