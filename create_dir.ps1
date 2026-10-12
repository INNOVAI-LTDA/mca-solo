# ============================================================================
# create_dir.ps1 - Cria Esqueleto de Diretórios MCA Framework
# ============================================================================
# Descrição: Cria apenas a estrutura de diretórios e arquivos vazios
#            conforme documentação arquitetura_molde_v3_dags_separacao.md
#
# Uso: .\create_dir.ps1 [-RootPath <caminho>] [-Force]
#
# Parâmetros:
#   -RootPath   Caminho raiz onde criar a estrutura (padrão: diretório atual)
#   -Force      Remove e recria arquivos existentes
#
# Autor: MCA Framework Team
# Versão: 1.1
# Data: 2026-10-13
# ============================================================================

param(
    [string]$RootPath = (Get-Location).Path,
    [switch]$Force
)

# ============================================================================
# CONFIGURAÇÃO INICIAL
# ============================================================================

$ErrorActionPreference = "Stop"
$script:StartTime = Get-Date
$script:CreatedDirs = 0
$script:CreatedFiles = 0
$script:SkippedFiles = 0

# Cores para output
$Colors = @{
    Info    = "Cyan"
    Success = "Green"
    Warning = "Yellow"
    Error   = "Red"
    Header  = "Magenta"
}

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

function Write-Header {
    param([string]$Message)
    Write-Host "`n$('=' * 80)" -ForegroundColor $Colors.Header
    Write-Host "  $Message" -ForegroundColor $Colors.Header
    Write-Host "$('=' * 80)`n" -ForegroundColor $Colors.Header
}

function Write-Info    { param([string]$Message) Write-Host "[INFO] $Message" -ForegroundColor $Colors.Info }
function Write-Success { param([string]$Message) Write-Host "[OK]   $Message" -ForegroundColor $Colors.Success }
function Write-Warning { param([string]$Message) Write-Host "[WARN] $Message" -ForegroundColor $Colors.Warning }
function Write-Error   { param([string]$Message) Write-Host "[ERR]  $Message" -ForegroundColor $Colors.Error }

function New-Directory {
    param([string]$Path, [string]$Description)
    try {
        if (-not (Test-Path $Path)) {
            New-Item -ItemType Directory -Path $Path -Force | Out-Null
            $script:CreatedDirs++
            Write-Success "DIR  $Description"
        } else {
            Write-Info "DIR (já existe) $Description"
        }
    } catch {
        Write-Error "Falha ao criar diretório: $Path - $($_.Exception.Message)"
        throw
    }
}

function New-EmptyFile {
    param([string]$Path, [string]$Description)
    try {
        if ((Test-Path $Path) -and -not $Force) {
            $script:SkippedFiles++
            Write-Warning "FILE (já existe) $Description"
            return
        }
        
        $directory = Split-Path $Path -Parent
        if (-not (Test-Path $directory)) {
            New-Item -ItemType Directory -Path $directory -Force | Out-Null
        }
        
        # Remove se existe e -Force
        if ((Test-Path $Path) -and $Force) {
            Remove-Item $Path -Force
        }
        
        # Cria arquivo vazio
        New-Item -ItemType File -Path $Path -Force | Out-Null
        $script:CreatedFiles++
        Write-Success "FILE $Description"
    } catch {
        Write-Error "Falha ao criar arquivo: $Path - $($_.Exception.Message)"
        throw
    }
}

# ============================================================================
# INÍCIO
# ============================================================================

Write-Header "MCA Framework - Criando Esqueleto de Diretórios"
Write-Info "Root Path : $RootPath"
Write-Info "Force Mode: $Force"

# Caminhos base
$FrameworkPath   = Join-Path $RootPath "framework"
$ApplicationPath = Join-Path $RootPath "application"
$DeploymentPath  = Join-Path $RootPath "deployment"
$TestsPath       = Join-Path $RootPath "tests"

# ============================================================================
# 1. FRAMEWORK (Core - Imutável pelo DEV)
# ============================================================================

Write-Header "1. FRAMEWORK (Core - Imutável)"

# 1.1 Core
New-Directory "$FrameworkPath/core/dags" "framework/core/dags (Core DAGs - Gestão)"

# Core DAGs
New-EmptyFile "$FrameworkPath/core/dags/metrics_collection.yaml"    "metrics_collection.yaml"
New-EmptyFile "$FrameworkPath/core/dags/health_check.yaml"          "health_check.yaml"
New-EmptyFile "$FrameworkPath/core/dags/component_lifecycle.yaml"   "component_lifecycle.yaml"
New-EmptyFile "$FrameworkPath/core/dags/alerting.yaml"              "alerting.yaml"

# Core Python
New-EmptyFile "$FrameworkPath/core/ports.py"                        "core/ports.py"
New-EmptyFile "$FrameworkPath/core/entities.py"                     "core/entities.py"
New-EmptyFile "$FrameworkPath/core/exceptions.py"                   "core/exceptions.py"
New-EmptyFile "$FrameworkPath/core/__init__.py"                     "core/__init__.py"

# 1.2 Management
New-Directory "$FrameworkPath/management/metrics"    "framework/management/metrics"
New-Directory "$FrameworkPath/management/logging"    "framework/management/logging"
New-Directory "$FrameworkPath/management/tracing"    "framework/management/tracing"
New-Directory "$FrameworkPath/management/alerting"   "framework/management/alerting"
New-Directory "$FrameworkPath/management/dashboard"  "framework/management/dashboard"

New-EmptyFile "$FrameworkPath/management/__init__.py"               "management/__init__.py"
New-EmptyFile "$FrameworkPath/management/metrics/__init__.py"       "management/metrics/__init__.py"
New-EmptyFile "$FrameworkPath/management/logging/__init__.py"       "management/logging/__init__.py"
New-EmptyFile "$FrameworkPath/management/tracing/__init__.py"       "management/tracing/__init__.py"
New-EmptyFile "$FrameworkPath/management/alerting/__init__.py"      "management/alerting/__init__.py"
New-EmptyFile "$FrameworkPath/management/dashboard/__init__.py"     "management/dashboard/__init__.py"

# 1.3 Execution
New-Directory "$FrameworkPath/execution"             "framework/execution"

New-EmptyFile "$FrameworkPath/execution/parser.py"                  "execution/parser.py"
New-EmptyFile "$FrameworkPath/execution/orchestrator.py"            "execution/orchestrator.py"
New-EmptyFile "$FrameworkPath/execution/connectors.py"              "execution/connectors.py"
New-EmptyFile "$FrameworkPath/execution/lifecycle.py"               "execution/lifecycle.py"
New-EmptyFile "$FrameworkPath/execution/__init__.py"                "execution/__init__.py"

# 1.4 Infrastructure
New-Directory "$FrameworkPath/infrastructure/config" "framework/infrastructure/config"

New-EmptyFile "$FrameworkPath/infrastructure/Dockerfile.framework"  "infrastructure/Dockerfile.framework"
New-EmptyFile "$FrameworkPath/infrastructure/docker-compose.framework.yml" "infrastructure/docker-compose.framework.yml"
New-EmptyFile "$FrameworkPath/infrastructure/config/framework.env"  "infrastructure/config/framework.env"
New-EmptyFile "$FrameworkPath/infrastructure/config/logging.yaml"   "infrastructure/config/logging.yaml"

# ============================================================================
# 2. APPLICATION (Controlado pelo DEV)
# ============================================================================

Write-Header "2. APPLICATION (Controlado pelo DEV)"

# 2.1 App DAGs
New-Directory "$ApplicationPath/dags"                "application/dags (App DAGs - Orquestração)"

New-EmptyFile "$ApplicationPath/dags/rodou_solo_pipeline.yaml"    "dags/rodou_solo_pipeline.yaml"
New-EmptyFile "$ApplicationPath/dags/senado_ncm_ingestion.yaml"   "dags/senado_ncm_ingestion.yaml"
New-EmptyFile "$ApplicationPath/dags/comex_monitoring.yaml"       "dags/comex_monitoring.yaml"

# 2.2 Components
New-Directory "$ApplicationPath/components"          "application/components"

New-EmptyFile "$ApplicationPath/components/rodou_adapter.py"      "components/rodou_adapter.py"
New-EmptyFile "$ApplicationPath/components/senado_adapter.py"     "components/senado_adapter.py"
New-EmptyFile "$ApplicationPath/components/ncm_adapter.py"        "components/ncm_adapter.py"
New-EmptyFile "$ApplicationPath/components/neo4j_adapter.py"      "components/neo4j_adapter.py"
New-EmptyFile "$ApplicationPath/components/__init__.py"           "components/__init__.py"

# 2.3 Config
New-Directory "$ApplicationPath/config"              "application/config"

New-EmptyFile "$ApplicationPath/config/app.env"                     "config/app.env"
New-EmptyFile "$ApplicationPath/config/docker-compose.app.yml"      "config/docker-compose.app.yml"
New-EmptyFile "$ApplicationPath/config/secrets.yaml"                "config/secrets.yaml"

# ============================================================================
# 3. DEPLOYMENT
# ============================================================================

Write-Header "3. DEPLOYMENT"

New-Directory "$DeploymentPath/kubernetes"           "deployment/kubernetes"
New-Directory "$DeploymentPath/helm/templates"       "deployment/helm/templates"

New-EmptyFile "$DeploymentPath/docker-compose.yml"                  "deployment/docker-compose.yml"
New-EmptyFile "$DeploymentPath/Dockerfile"                          "deployment/Dockerfile"

New-EmptyFile "$DeploymentPath/kubernetes/namespace.yaml"           "kubernetes/namespace.yaml"
New-EmptyFile "$DeploymentPath/kubernetes/deployment.yaml"          "kubernetes/deployment.yaml"
New-EmptyFile "$DeploymentPath/kubernetes/service.yaml"             "kubernetes/service.yaml"
New-EmptyFile "$DeploymentPath/kubernetes/configmap.yaml"           "kubernetes/configmap.yaml"

New-EmptyFile "$DeploymentPath/helm/Chart.yaml"                     "helm/Chart.yaml"
New-EmptyFile "$DeploymentPath/helm/values.yaml"                    "helm/values.yaml"

# ============================================================================
# 4. TESTS
# ============================================================================

Write-Header "4. TESTS"

New-Directory "$TestsPath/framework"                 "tests/framework"
New-Directory "$TestsPath/application"               "tests/application"

New-EmptyFile "$TestsPath/framework/test_core_dags.py"            "tests/framework/test_core_dags.py"
New-EmptyFile "$TestsPath/framework/test_management.py"           "tests/framework/test_management.py"
New-EmptyFile "$TestsPath/framework/test_execution.py"            "tests/framework/test_execution.py"
New-EmptyFile "$TestsPath/framework/__init__.py"                  "tests/framework/__init__.py"

New-EmptyFile "$TestsPath/application/test_app_dags.py"           "tests/application/test_app_dags.py"
New-EmptyFile "$TestsPath/application/test_components.py"         "tests/application/test_components.py"
New-EmptyFile "$TestsPath/application/test_integration.py"        "tests/application/test_integration.py"
New-EmptyFile "$TestsPath/application/__init__.py"                "tests/application/__init__.py"

# ============================================================================
# 5. ARQUIVOS RAIZ
# ============================================================================

Write-Header "5. ARQUIVOS RAIZ"

New-EmptyFile "$RootPath/config.yaml"                  "config.yaml"
New-EmptyFile "$RootPath/.gitignore"                   ".gitignore"
New-EmptyFile "$RootPath/README.md"                    "README.md"
New-EmptyFile "$RootPath/requirements.txt"             "requirements.txt"

# ============================================================================
# 6. DOCS (Documentação)
# ============================================================================

Write-Header "6. DOCS (Documentação)"

New-Directory "$RootPath/docs"                         "docs"

New-EmptyFile "$RootPath/docs/arquitetura_molde_fundamentacao.md"        "docs/arquitetura_molde_fundamentacao.md"
New-EmptyFile "$RootPath/docs/arquitetura_molde_v2_orquestracao_gestao.md" "docs/arquitetura_molde_v2_orquestracao_gestao.md"
New-EmptyFile "$RootPath/docs/arquitetura_molde_v3_dags_separacao.md"    "docs/arquitetura_molde_v3_dags_separacao.md"
New-EmptyFile "$RootPath/docs/implementation_guide.md"                   "docs/implementation_guide.md"
New-EmptyFile "$RootPath/docs/contracts.md"                              "docs/contracts.md"
New-EmptyFile "$RootPath/docs/examples.md"                               "docs/examples.md"
New-EmptyFile "$RootPath/docs/observability.md"                          "docs/observability.md"

# ============================================================================
# RESUMO FINAL
# ============================================================================

Write-Header "Resumo"

$endTime = Get-Date
$duration = $endTime - $script:StartTime

Write-Host "Tempo de execução: $($duration.TotalSeconds.ToString('F2')) segundos`n" -ForegroundColor $Colors.Info

Write-Host "Estatísticas:" -ForegroundColor $Colors.Header
Write-Host "  Diretórios criados : $($script:CreatedDirs)" -ForegroundColor $Colors.Success
Write-Host "  Arquivos criados   : $($script:CreatedFiles)" -ForegroundColor $Colors.Success
Write-Host "  Arquivos ignorados : $($script:SkippedFiles)" -ForegroundColor $Colors.Warning

Write-Host "`nEstrutura criada em: $RootPath" -ForegroundColor $Colors.Info
Write-Host "`nPróximos passos:" -ForegroundColor $Colors.Header
Write-Host "  1. Preencher os arquivos um de cada vez" -ForegroundColor $Colors.Info
Write-Host "  2. Começar pelos Core DAGs (framework/core/dags/)" -ForegroundColor $Colors.Info
Write-Host "  3. Implementar o parser em framework/execution/parser.py" -ForegroundColor $Colors.Info
Write-Host "  4. Criar os componentes da aplicação em application/components/" -ForegroundColor $Colors.Info

Write-Host "`n✅ Esqueleto criado com sucesso!`n" -ForegroundColor $Colors.Success