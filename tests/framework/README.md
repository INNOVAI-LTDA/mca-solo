# 🧪 Testes da Camada Core — `tests/framework/`

Guia de validação manual da suíte de testes do **Milestone M1 — Core Framework**,
cobrindo os artefatos das **Especificações Técnicas ID 1.1** (Hierarquia de Exceções
do Core), **ID 1.2** (Contratos de Dados e Gestão Imutáveis), **ID 1.3** (Portas de
Domínio — ABCs do Core Framework) e **ID 1.4** (Core DAGs — Artefatos Imutáveis de
Gestão + Parser Unificado).

| Artefato de produção | Artefato de teste | Status esperado |
| :--- | :--- | :--- |
| `framework/core/exceptions.py` | `test_core_exceptions.py` | ✅ Implementado (ID 1.1) — 110 testes |
| `framework/core/entities.py` | `test_core_entities.py` | ✅ Implementado (ID 1.2) — 33 testes |
| `framework/core/ports.py` | `test_core_ports.py` | ✅ Implementado (ID 1.3) — 86 testes |
| `framework/core/dags/*.yaml` | `test_core_dags.py` | ✅ Implementado (ID 1.4) — 150 casos (149 passed, 1 skipped) |
| `framework/execution/parser.py` | `test_core_dags.py` (Seção 6.8/6.9) | ✅ Implementado (ID 1.4) — cobertura 96% |
| `framework/execution/*` (demais módulos) | `test_execution.py` | ⏳ Placeholder (vazio) |
| `framework/management/*` | `test_management.py` | ⏳ Placeholder (vazio) |

> 📦 Dependências: além do [`requirements.txt`](../../requirements.txt) da raiz, esta
> pasta contém um [`requirements.txt`](requirements.txt) local com as mesmas fixações,
> permitindo reinstalar o pipeline de teste de forma autônoma a partir daqui.

---

## 1. Pré-requisitos

- **Python ≥ 3.10** (ambiente homologado: **3.12**).
- Dependências de teste declaradas na raiz do projeto em [`requirements.txt`](../../requirements.txt)
  — e replicadas no [`requirements.txt`](requirements.txt) **local desta pasta** —:
  `pytest`, `pytest-cov`, `coverage`, `mypy`, `black`, `flake8`, `ruff`, `PyYAML`,
  `yamllint`, `networkx` (`networkx` é opcional: o teste correspondente usa
  `pytest.importorskip` e faz skip gracioso quando ausente).

> ℹ️ Os módulos avaliados pelas IDs 1.1–1.3 (`framework/core/exceptions.py`,
> `framework/core/entities.py` e `framework/core/ports.py`) usam apenas a biblioteca
> padrão (`copy`, `typing`, `dataclasses`, `datetime`, `enum`, `abc`). A partir da
> ID 1.4, `framework/execution/parser.py` e `test_core_dags.py` dependem também de
> **PyYAML** (leitura dos artefatos YAML das Core DAGs).
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
ruff --version          # ruff >= 0.4
yamllint --version      # yamllint (validação dos YAMLs das Core DAGs)
python -c "import yaml; print(yaml.__version__)"   # PyYAML >= 6.0
python -c "import jsonschema; print(jsonschema.__version__)"  # opcional (schema JSON)
python -c "import networkx; print(networkx.__version__)"      # opcional (aciclicidade cruzada)
```

---

## 2. Configuração do Pytest (por que basta rodar da raiz)

A execução é determinística graças a dois arquivos na **raiz do projeto**:

- **`pytest.ini`** — define `testpaths = tests`, `python_files = test_*.py` e
  `--import-mode=importlib`.
- **`conftest.py`** — insere a raiz do projeto no `sys.path` e **preimporta**
  o pacote de produção `framework` antes da coleta dos testes, evitando a
  colisão de homônimo com o pacote de testes `tests/framework`
  (`tests/framework/` tem `__init__.py`; `framework/` não tem — namespace package,
  exatamente o cenário que gera o erro de duplicidade no mypy, ver §7).

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

A partir da ID 1.4, `test_core_dags.py` já contém a suíte completa da spec
(Seção 6.1–6.9 — ver §3C). Os demais arquivos (`test_execution.py`,
`test_management.py`) permanecem placeholders vazios até suas respectivas tasks;
o resultado deve ser `no tests ran in <arquivo>` para eles, sem erros de coleta.

---

## 3A. Suíte da Especificação Técnica ID 1.2 — Contratos Imutáveis (`test_core_entities.py`)

Artefato: `framework/core/entities.py` → teste: `tests/framework/test_core_entities.py`.

### 3A.0. Reexecutar TODA a suíte de testes manualmente (visão geral)

A suíte completa do projeto hoje possui **379 casos coletados** (378 passando +
1 skip legítimo), distribuídos em:

| Arquivo | Conteúdo | Qtd. esperada |
| :--- | :--- | :--- |
| `tests/framework/test_core_exceptions.py` | Spec ID 1.1 — Hierarquia de Exceções | 110 passed |
| `tests/framework/test_core_entities.py` | Spec ID 1.2 — Contratos Imutáveis | 33 passed |
| `tests/framework/test_core_ports.py` | Spec ID 1.3 — Portas de Domínio (ABCs) | 86 passed |
| `tests/framework/test_core_dags.py` | Spec ID 1.4 — Core DAGs + Parser Unificado | 149 passed, 1 skipped* |
| `tests/framework/test_execution.py` | Placeholder (task futura) | no tests ran |
| `tests/framework/test_management.py` | Placeholder (task futura) | no tests ran |
| `tests/application/*` | Testes da camada de aplicação | placeholders até o Épico DEV |

\* O único skip é `TestConformidadeInfraestrutura::test_montagem_read_only` na
parametrização `deployment/kubernetes/configmaps.yaml` — o manifesto ainda não foi
entregue por uma task futura de infraestrutura, e o teste pula de forma explícita
(`pytest.skip`). As demais montagens (`docker-compose.yml` e os manifests já
presentes) são verificadas ativamente. Para confirmar o motivo em qualquer momento:
`pytest tests/framework/test_core_dags.py -q -rs`.

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
pytest tests/framework/test_core_dags.py -v       # somente a ID 1.4
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
pytest tests\framework\test_core_dags.py -v       # somente a ID 1.4
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

## 3B. Suíte da Especificação Técnica ID 1.3 — Portas de Domínio (`test_core_ports.py`)

Artefato: `framework/core/ports.py` → teste: `tests/framework/test_core_ports.py`.

### 3B.1. Execução verbosa da ID 1.3 (recomendada)

- Linux:
```bash
pytest tests/framework/test_core_ports.py -v
```
- PowerShell 5.1:
```ps
pytest tests\framework\test_core_ports.py -v
```

Saída esperada: **86 testes passando** (`86 passed`), organizados pelas 6 categorias da Seção 6:

| Classe de teste | Categoria da spec | O que valida |
| :--- | :--- | :--- |
| Barreira de abstração | **6.1** | `FetcherPort()`, `IngestPort()`, `TransformerPort()`, `ValidatorPort()`, `URNPort()` levantam `TypeError` com menção aos métodos abstratos |
| Mixins de contrato (`*ContractTests` + stubs) | **6.2** | Tipos de retorno (`isinstance` de `FetchResult`/`IngestResult`/`ValidationResult`), presença dos métodos obrigatórios (`hasattr`) e assinaturas via `inspect.signature` |
| Substituição (LSP) | **6.3** | `isinstance(stub, Porta)` para as 5 ABCs e uso polimórfico em contexto que espera a porta |
| Contrato incompleto | **6.4** | Subclasse parcial (sem um método abstrato) levanta `TypeError` na instanciação |
| Docstrings/metadados | **6.5** | Docstring não-vazia por ABC e por método; seções `Pre-condicoes`, `Pos-condicoes`, `Invariantes`; corpos apenas com `...` |
| Independência de adaptadores | **6.6** | Análise AST de `ports.py`: nenhum import de `application/` ou `framework.execution/`; dependência unidirecional ports → entities; `__all__` com as 5 portas |

Comandos granulares equivalentes (rode da raiz):

```bash
# Uma categoria inteira (ex.: barreira de abstração)
pytest tests/framework/test_core_ports.py::TestBarreiraDeAbstracao -v

# Filtro por palavra-chave (ex.: todos os cenários de URNPort)
pytest tests/framework/test_core_ports.py -k "urn" -v
```

### 3B.2. Cobertura de código da ID 1.3 (meta ≥ 95%; estado atual: 100%)

```bash
pytest --cov=framework.core.ports --cov-report=term-missing tests/framework/test_core_ports.py
```

Saída esperada — **zero linhas faltantes**:

```
Name                      Stmts   Miss  Cover   Missing
--------------------------------------------------------
framework/core/ports.py      36      0   100%
--------------------------------------------------------
TOTAL                        36      0   100%
```

### 3B.3. Validação estática da ID 1.3 (Seção 7 da spec)

```bash
# mypy: use --explicit-package-bases OU o nome de pacote (framework/__init__.py
# não existe no repositório — ver §7 "Source file found twice" do README)
mypy --explicit-package-bases framework/core/ports.py   # esperado: Success: no issues found
mypy -p framework.core                                  # alternativa: todo o pacote core
black --check framework/core/ports.py tests/framework/test_core_ports.py
ruff check framework/core/ports.py         # linter exigido pela spec ID 1.3
flake8 --max-line-length=88 framework/core/ports.py tests/framework/test_core_ports.py
pylint framework/core/ports.py --disable=all --enable=abstract-method
```

> ℹ️ Sobre o `ruff`: ele pode reportar `UP006`/`UP035` (sugerindo `dict`/`list` nativos em
> vez de `typing.Dict`/`typing.List`). Esses avisos são **intencionais e aceitáveis** neste
> projeto — a Seção 5.1 da spec ID 1.3 exige explicitamente o uso de `Dict[str, Any]`,
> `List[...]` e `Optional[...]` do módulo `typing`, no mesmo padrão de `entities.py`.
> Para silenciá-los pontualmente: `ruff check --ignore UP006,UP035 framework/core/ports.py`.

---

## 3C. Suíte da Especificação Técnica ID 1.4 — Core DAGs (`test_core_dags.py`)

Artefatos: `framework/core/dags/*.yaml` + `framework/execution/parser.py` →
teste: `tests/framework/test_core_dags.py`.

### 3C.1. Execução verbosa da ID 1.4 (recomendada)

- Linux:
```bash
pytest tests/framework/test_core_dags.py -v
```
- PowerShell 5.1:
```ps
pytest tests\framework\test_core_dags.py -v
```

Saída esperada: **149 passed, 1 skipped** (o único skip é a verificação `:ro`
do manifesto `deployment/kubernetes/configmaps.yaml`, ainda não entregue — ver
nota logo acima da tabela), organizados pelas categorias da Seção 6 da spec:

| Classe de teste | Categoria da spec | O que valida |
| :--- | :--- | :--- |
| `TestExistenciaLocalizacao` | **6.1** | Os 4 YAMLs existem e não são vazios em `framework/core/dags/`; fechamento do conjunto (nenhum outro `.yaml`/`.yml`); CC-02/VAL-04; nenhum App DAG declara `immutable: true` |
| `TestSchemaYaml` | **6.2** | Chaves top-level `dag`/`tasks`/`notifications`; sub-chaves obrigatórias de `dag`; `tasks` como lista de mapas com `id`/`type`/`config`; `notifications` como mapa; ausência das chaves exclusivas de App DAG (`components`/`pipeline`); `id`/`schedule` por arquivo; `triggers` só em `component_lifecycle` (event-driven, `schedule: null`) |
| `TestPropriedadesInvariantes` | **6.3** | `immutable is True` (booleano literal), `owner == "framework"`, prefixo `core_` nos 4 IDs; unicidade dos IDs; cobertura das 4 capacidades (observabilidade, disponibilidade, controle, reação) |
| `TestDisjuncaoDeIds` | **6.4** | Interseção entre IDs de Core e App DAGs vazia (VAL-08/CC-05); App DAGs não usam prefixo `core_`; `application/dags/` vazio até a Issue 1.5 |
| `TestAciclicidade` | **6.5** | Grafo `depends_on` acíclico via DFS próprio; dependências referenciam tarefas existentes; ordem topológica respeita a ordem da lista; validação cruzada com `networkx.is_directed_acyclic_graph` (com `importorskip`); sensibilidade do detector de ciclo |
| `TestTiposDeTarefa` | **6.6** | Todo `type` começa com `management.` (VAL-07); sufixo pertence ao vocabulário da Seção 4.7; os 11 tipos do contrato estão materializados; contagem de tarefas por DAG (3/4/3/1); IDs de tarefa únicos por DAG |
| `TestNotificacoes` | **6.7** | `on_failure` presente em todo Core DAG; canais ⊆ `{log, alert, webhook}`; `alerting` declara `on_alert` |
| `TestIntegracaoParser` | **6.8** | `DAGParser(framework_dags_dir="framework/core/dags", app_dags_dir="application/dags").parse_all()` carrega os 4 Core DAGs no registro unificado; `get_core_dags()` retorna exatamente 4; imutabilidade preservada no objeto; metadados/schedule `null` event-driven; cópias defensivas; `parse_file()` individual |
| `TestFalhaExplicita` | **6.9** | Negativos com `ConfigurationError` (que também é `ValueError`): `immutable: false`, `immutable: "true"` (string), ID sem prefixo `core_`, owner divergente, ciclo/auto-dependência em `depends_on`, tipo fora de `management.*`, tipo desconhecido, `components`/`pipeline` proibidos, sem `on_failure`, canal inexistente, notificação não-lista, chaves ausentes, YAML malformado, arquivo inexistente; diagnóstico contém a regra tipada (VAL-01…VAL-08) |
| `TestConformidadeInfraestrutura` | **5.3 (CC)** | CC-03: montagem `:ro` das Core DAGs inspecionando o manifesto de implantação; yamllint `relaxed` nos 4 arquivos (via API quando instalado) |
| `TestHigieneArtefatos` | **7** | ASCII puro, primeira linha identifica a origem, linhas ≤ 88 colunas, descrições sem acentos, auto-inventário da suíte |

Comandos granulares equivalentes (rode da raiz):

```bash
# Uma categoria inteira (ex.: integração com o parser — Seção 6.8)
pytest tests/framework/test_core_dags.py::TestIntegracaoParser -v

# Um único teste negativo (ex.: immutable=false)
pytest "tests/framework/test_core_dags.py::TestFalhaExplicita::test_immutable_false_rejeitado" -v

# Filtro por palavra-chave (ex.: todos os cenários de notificação)
pytest tests/framework/test_core_dags.py -k "notific" -v
```

PowerShell 5.1 (mesmos alvos, separadores `\`):

```ps
pytest tests\framework\test_core_dags.py::TestIntegracaoParser -v
pytest "tests\framework\test_core_dags.py::TestFalhaExplicita::test_immutable_false_rejeitado" -v
```

> 💡 Para listar o motivo de cada skip na ID 1.4:
> `pytest tests/framework/test_core_dags.py -q -rs`

### 3C.2. Cobertura de código (meta ≥ 90%; estado atual: 96%)

- Linux:
```bash
pytest --cov=framework.execution.parser --cov-report=term-missing tests/framework/test_core_dags.py
```
- PowerShell 5.1:
```ps
pytest --cov=framework.execution.parser --cov-report=term-missing tests\framework\test_core_dags.py
```

Saída esperada (linhas *Missing* = ramos defensivos de diretórios alternativos):

```
Name                            Stmts   Miss  Cover   Missing
--------------------------------------------------------------
framework/execution/parser.py     178      8    96%   262, 268, 280, ...
--------------------------------------------------------------
TOTAL                             178      8    96%
```

### 3C.3. Validação estática da ID 1.4 (Seção 7 da spec)

```bash
# Linting dos testes (ruff) — ver nota sobre os ignores documentados
ruff check --ignore UP006,UP035,UP045,RUF022 tests/framework/test_core_dags.py
ruff check framework/execution/parser.py

# Sintaxe YAML dos 4 artefatos (esperado: silêncio / exit code 0)
yamllint -d relaxed framework/core/dags/

# Type hints e formatação
mypy --explicit-package-bases framework/execution/parser.py
black --check framework/execution/parser.py tests/framework/test_core_dags.py
flake8 --max-line-length=88 tests/framework/test_core_dags.py
```

PowerShell 5.1 (equivalentes):

```ps
ruff check --ignore UP006,UP035,UP045,RUF022 tests\framework\test_core_dags.py
yamllint -d relaxed framework\core\dags\
black --check framework\execution\parser.py tests\framework\test_core_dags.py
```

> ℹ️ Sobre os ignores do `ruff`: `UP006`/`UP035`/`UP045` sugerem `dict`/`list`/`X | None`
> nativos em vez de `typing.Dict`/`typing.List`/`typing.Optional`. Esses avisos são
> **intencionais e aceitáveis** neste projeto — as specs ID 1.3/ID 1.4 exigem a notação
> explícita de `typing` (mesmo padrão de `entities.py` e `ports.py`). `RUF022` pede
> ordenação alfabética de `__all__`, decorativa. Para um gate estrito em CI, use o
> comando com `--ignore` acima.

> ⚠️ Nota de ambiente: se aparecer erro de coleta citando `libtmux`
> (`Marks cannot be applied to fixtures`), plugin global incompatível, adicione
> `-p no:libtmux` ao comando pytest (ver §7).

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
  && pytest --cov=framework.core.exceptions --cov=framework.core.entities --cov=framework.core.ports --cov=framework.execution.parser --cov-report=term-missing tests/framework/ \
  && mypy framework/core/exceptions.py framework/core/entities.py framework/core/ports.py \
  && black --check framework/ tests/framework/ \
  && flake8 --max-line-length=88 framework/core/ tests/framework/ \
  && ruff check --ignore UP006,UP035,UP045,RUF022 framework/ tests/framework/ \
  && yamllint -d relaxed framework/core/dags/ \
  && echo "✅ M1: todos os gateways de qualidade passaram"
```
- PowerShell 5.1 (não há `&&` no PS 5.1 — encadeie via `$LastExitCode`):
```ps
& {
    pytest tests\ -v
    if ($LastExitCode -ne 0) { return }
    pytest --cov=framework.core.exceptions --cov=framework.core.entities --cov=framework.core.ports --cov=framework.execution.parser --cov-report=term-missing tests\framework\
    if ($LastExitCode -ne 0) { return }
    mypy framework\core\exceptions.py framework\core\entities.py framework\core\ports.py
    if ($LastExitCode -ne 0) { return }
    black --check framework\ tests\framework\
    if ($LastExitCode -ne 0) { return }
    flake8 --max-line-length=88 framework\core\ tests\framework\
    if ($LastExitCode -ne 0) { return }
    ruff check --ignore UP006,UP035,UP045,RUF022 framework\ tests\framework\
    if ($LastExitCode -ne 0) { return }
    yamllint -d relaxed framework\core\dags\
    if ($LastExitCode -ne 0) { return }
    Write-Output "✅ M1: todos os gateways de qualidade passaram"
}
```

Saída esperada da suíte completa: **378 passed, 1 skipped** (110 da ID 1.1 +
33 da ID 1.2 + 86 da ID 1.3 + 149 da ID 1.4 + 1 skipped: verificação do manifesto
`configmaps.yaml`, ainda não entregue),
com os placeholders (`test_execution.py`, `test_management.py` e
`tests/application/*`) reportando `no tests ran`. Se o plugin global `libtmux`
estiver presente no ambiente, acrescente `-p no:libtmux` a cada comando
(ver tabela da §7).

Cobertura esperada dos módulos do Core + parser unificado (metas: Core ≥ 95%,
parser ≥ 90%; estado atual: Core 100%, parser 96%):

```
Name                             Stmts   Miss  Cover   Missing
 --------------------------------------------------------------
 framework/core/entities.py          68      0   100%
 framework/core/exceptions.py        40      0   100%
 framework/core/ports.py             36      0   100%
 framework/execution/parser.py      178      8    96%
 --------------------------------------------------------------
 TOTAL                              322      8    98%
```

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

**ID 1.3 — Portas de Domínio / ABCs (`test_core_ports.py`):**
- [ ] `pytest`: **86 passed**, 0 failed, 0 errors.
- [ ] Cobertura de `framework/core/ports.py`: **100%** (meta da spec: ≥ 95%).
- [ ] `mypy`: nenhum erro de tipagem (portas ↔ entidades compatíveis).
- [ ] `black --check`: arquivos inalterados (formatados).
- [ ] `ruff check`: sem violações relevantes (ver nota 3B.3 sobre `UP006/UP035`).
- [ ] `flake8`: exit code `0` (sem violações com `--max-line-length=88`).
- [ ] Sem imports circulares: `ports.py → entities.py` é unidirecional.

**ID 1.4 — Core DAGs / Parser Unificado (`test_core_dags.py`):**
- [ ] `pytest`: **149 passed, 1 skipped** (skip apenas sem `networkx`), 0 failed, 0 errors.
- [ ] Os 4 YAMLs existem em `framework/core/dags/` e o diretório está fechado (só eles).
- [ ] Propriedades invariantes: `immutable: true`, `owner: framework`, prefixo `core_`.
- [ ] Cobertura de `framework/execution/parser.py`: **96%** (meta da spec: ≥ 90%).
- [ ] `yamllint -d relaxed framework/core/dags/`: exit code `0`.
- [ ] `ruff check --ignore UP006,UP035,UP045,RUF022`: exit code `0` nos testes e no parser.
- [ ] `mypy`: nenhum erro de tipagem em `parser.py` (use `--explicit-package-bases`).
- [ ] Testes negativos (Seção 6.9) confirmam falha explícita: `ConfigurationError`
      (subclasse de `ValueError`) interrompe o carregamento — sem fallback silencioso.

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
| Cobertura mostra `0%` ou módulo não rastreado | Nome do alvo incorreto no `--cov` | Usar exatamente `--cov=framework.core.exceptions` / `--cov=framework.core.entities` / `--cov=framework.core.ports` / `--cov=framework.execution.parser` (notação de ponto, caminho importável) |
| Coleta da ID 1.4 aborta com `ModuleNotFoundError: No module named 'yaml'` | PyYAML ausente no ambiente (introduzido pela ID 1.4 — parser e testes leem os YAMLs das Core DAGs) | `pip install PyYAML` ou reinstale as dependências: `pip install -r tests/framework/requirements.txt` |
| `test_montagem_read_only[deployment/kubernetes/configmaps.yaml]` aparece como `SKIPPED` | Manifesto de implantação ainda não entregue por task futura de infraestrutura (skip explícito com `pytest.skip`) | Nenhum — comportamento esperado; rode `pytest tests/framework/test_core_dags.py -q -rs` para ver o motivo de cada skip. Quando o arquivo for entregue, o teste passa a executar sozinho |
| `test_aciclicidade_via_networkx` aparece como `SKIPPED` | `networkx` é opcional (`pytest.importorskip`) — o teste DFS próprio já cobre o mesmo cenário | Instale para executar também a validação cruzada: `pip install networkx` (já fixado no requirements local) |
| Erro ao carregar Core DAG durante `parse_all()` em código de produção | Violação intencional de VAL-01…VAL-08 (falha explícita — não há fallback silencioso) | Corrija o artefato: `immutable: true`, `owner: framework`, prefixo `core_`, tipos `management.*`, sem ciclos; nunca edite os YAMLs de `framework/core/dags/` (montados `:ro`) |
| `mypy`: `Source file found twice under different module names: "core" and "framework.core"` | O diretório `framework/` **não possui** `__init__.py` (namespace package), então o mypy resolve o mesmo arquivo por dois nomes ao usar caminhos explícitos | Adicione a flag: `mypy --explicit-package-bases framework/core/ports.py` — ou verifique pelo nome de pacote: `mypy -p framework.core` (ambos terminam com `Success: no issues found`) |

---

## 8. Referências

- Especificação Técnica ID 1.1 — Seções 6 (estratégia de testes) e 7 (ferramentas).
- Especificação Técnica ID 1.2 — Seções 6 (cenários 6.1–6.5) e 7 (ferramentas).
- Especificação Técnica ID 1.3 — Seções 6 (cenários 6.1–6.6) e 7 (ferramentas, com `ruff`).
- Especificação Técnica ID 1.4 — Seções 4 (schema YAML das Core DAGs), 5 (regras VAL-01…VAL-08
  e critérios CC-01…CC-05), 6 (cenários 6.1–6.9) e 7 (ferramentas: `pytest`, `pytest-cov`,
  `yamllint`, `jsonschema`, `ruff`).
- `docs/arquitetura_molde_v3_dags_separacao.md` (Seções 3, 5, 7, 11) e
  `docs/arquitetura_molde_v2_orquestracao_gestao.md` (Seção 3) — separação
  Core DAGs (Gestão, imutável) × App DAGs (Orquestração, mutável).
- `docs/contracts.md` (Seções 3, 4 e 5), `docs/arquitetura_molde_v2_orquestracao_gestao.md`
  (Seções 2 e 3.2.1), `docs/examples.md` — contratos de Domínio e Gestão.
- [`requirements.txt`](requirements.txt) — dependências fixadas locais desta pasta.
- [`../../requirements.txt`](../../requirements.txt) — dependências fixadas da raiz do pipeline.
