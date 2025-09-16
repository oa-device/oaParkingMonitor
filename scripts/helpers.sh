#!/bin/bash
# oaParkingMonitor - Shared Utilities Library
# Professional-grade helper functions for parking monitor operations
# Version: 2.0.0

set -euo pipefail

# ============================================================================
# Constants and Configuration
# ============================================================================

readonly SCRIPT_NAME="${0##*/}"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
readonly SERVICE_NAME="oaParkingMonitor"
readonly DEFAULT_PORT=9091
readonly DEFAULT_HOST="localhost"

# Colors for output (disable in non-interactive terminals)
if [[ -t 1 ]]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[1;33m'
    readonly BLUE='\033[0;34m'
    readonly PURPLE='\033[0;35m'
    readonly CYAN='\033[0;36m'
    readonly NC='\033[0m' # No Color
else
    readonly RED=''
    readonly GREEN=''
    readonly YELLOW=''
    readonly BLUE=''
    readonly PURPLE=''
    readonly CYAN=''
    readonly NC=''
fi

# ============================================================================
# Logging and Output Functions
# ============================================================================

# Base logging function with timestamp
_log_message() {
    local level="$1"
    local color="$2"
    local icon="$3"
    local message="$4"
    
    echo -e "${color}[$(date +'%Y-%m-%d %H:%M:%S')] ${icon} $message${NC}"
    
    # Also log to file if LOG_FILE is set
    if [[ -n "${LOG_FILE:-}" ]]; then
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] [$level] $message" >> "$LOG_FILE"
    fi
}

# Success messages
log_success() {
    _log_message "SUCCESS" "$GREEN" "[OK]" "$1"
}

# Information messages
log_info() {
    _log_message "INFO" "$BLUE" "[INFO]" "$1"
}

# Warning messages
log_warn() {
    _log_message "WARN" "$YELLOW" "[WARN]" "$1"
}

# Error messages
log_error() {
    _log_message "ERROR" "$RED" "[FAIL]" "$1"
}

# Debug messages (only shown if DEBUG=1)
log_debug() {
    if [[ "${DEBUG:-0}" == "1" ]]; then
        _log_message "DEBUG" "$PURPLE" "[DEBUG]" "$1"
    fi
}

# Progress messages
log_progress() {
    _log_message "PROGRESS" "$CYAN" "[PROGRESS]" "$1"
}

# Section headers
log_header() {
    echo ""
    echo -e "${BLUE}=== $1 ===${NC}"
}

# ============================================================================
# Environment and System Detection
# ============================================================================

# Detect the current environment
get_environment() {
    echo "${PARKING_MONITOR_ENV:-${ENVIRONMENT:-production}}"
}

# Check if running on macOS
is_macos() {
    [[ "$OSTYPE" == "darwin"* ]]
}

# Check if running on Apple Silicon
is_apple_silicon() {
    is_macos && [[ "$(uname -m)" == "arm64" ]]
}

# Get macOS version
get_macos_version() {
    if is_macos; then
        sw_vers -productVersion
    else
        echo "N/A"
    fi
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python version compatibility
check_python_version() {
    local required_version="${1:-3.12}"
    
    if ! command_exists python3; then
        log_error "Python 3 not found"
        return 1
    fi
    
    local python_version
    python_version=$(python3 --version | cut -d' ' -f2)
    
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
        log_error "Python ${required_version}+ required, found $python_version"
        return 1
    fi
    
    log_success "Python version: $python_version"
    return 0
}

# ============================================================================
# Project and Configuration Management
# ============================================================================

# Change to project root directory
cd_project_root() {
    cd "$PROJECT_ROOT"
    log_debug "Changed to project root: $PROJECT_ROOT"
}

# Get configuration file path for current environment
get_config_file() {
    local env
    env=$(get_environment)
    echo "$PROJECT_ROOT/config/$env.yaml"
}

# Check if configuration file exists
check_config_file() {
    local config_file
    config_file=$(get_config_file)
    
    if [[ -f "$config_file" ]]; then
        log_success "Configuration found: $config_file"
        return 0
    else
        log_error "Configuration not found: $config_file"
        return 1
    fi
}

# Validate YAML syntax
validate_yaml() {
    local yaml_file="$1"
    
    if ! command_exists python3; then
        log_warn "Python not available for YAML validation"
        return 0
    fi
    
    if python3 -c "
import yaml
try:
    with open('$yaml_file', 'r') as f:
        yaml.safe_load(f)
    print('YAML syntax valid')
except yaml.YAMLError as e:
    print(f'YAML error: {e}')
    exit(1)
" 2>/dev/null; then
        log_success "YAML syntax valid: $yaml_file"
        return 0
    else
        log_error "YAML syntax invalid: $yaml_file"
        return 1
    fi
}

# ============================================================================
# Virtual Environment and Dependencies
# ============================================================================

# Check if uv is available
check_uv() {
    if command_exists uv; then
        local uv_version
        uv_version=$(uv --version)
        log_success "uv available: $uv_version"
        return 0
    else
        log_error "uv not found - required for dependency management"
        log_info "Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
        return 1
    fi
}

# Setup virtual environment
setup_venv() {
    cd_project_root
    
    if [[ ! -d ".venv" ]] || [[ ! -f "uv.lock" ]]; then
        log_progress "Setting up virtual environment..."
        uv sync --frozen
    else
        log_success "Virtual environment ready"
    fi
}

# Activate virtual environment
activate_venv() {
    cd_project_root
    
    if [[ -f ".venv/bin/activate" ]]; then
        # shellcheck source=/dev/null
        source .venv/bin/activate
        log_debug "Virtual environment activated"
        return 0
    else
        log_error "Virtual environment not found"
        return 1
    fi
}

# Check critical Python dependencies
check_dependencies() {
    log_progress "Checking critical dependencies..."
    
    activate_venv || return 1
    
    # Define dependencies with their import names
    local packages=("torch" "ultralytics" "fastapi" "opencv-python" "numpy" "psutil")
    local imports=("torch" "ultralytics" "fastapi" "cv2" "numpy" "psutil")
    
    # Check each dependency
    for i in "${!packages[@]}"; do
        local package="${packages[$i]}"
        local import_name="${imports[$i]}"
        
        if python3 -c "import $import_name" 2>/dev/null; then
            local version
            # Get version with fallback strategies
            if [[ "$package" == "opencv-python" ]]; then
                version=$(python3 -c "import cv2; print(cv2.__version__)" 2>/dev/null || echo "unknown")
            else
                # Try multiple version detection strategies
                version=$(python3 -c "
import $import_name
try:
    # Try importlib.metadata first (Python 3.8+)
    from importlib.metadata import version as get_version
    print(get_version('$package'))
except ImportError:
    try:
        # Fallback to pkg_resources
        import pkg_resources
        print(pkg_resources.get_distribution('$package').version)
    except:
        try:
            # Try __version__ attribute
            print(getattr($import_name, '__version__', 'unknown'))
        except:
            print('unknown')
except:
    try:
        # Final fallback to __version__ attribute
        print(getattr($import_name, '__version__', 'unknown'))
    except:
        print('unknown')
" 2>/dev/null || echo "unknown")
            fi
            log_success "$package: $version"
        else
            log_error "Missing dependency: $package"
            return 1
        fi
    done
    
    # Check PyTorch MPS support
    if python3 -c "
import torch
if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
    exit(0)
else:
    exit(1)
" 2>/dev/null; then
        log_success "PyTorch Metal Performance Shaders: Available"
    else
        log_warn "PyTorch MPS not available - CPU/CUDA fallback will be used"
    fi
    
    return 0
}

# ============================================================================
# Service Management
# ============================================================================

# Check if service is running
is_service_running() {
    pgrep -f "parking-monitor" >/dev/null 2>&1
}

# Get service process info
get_service_pid() {
    pgrep -f "parking-monitor" 2>/dev/null || echo ""
}

# Stop service gracefully
stop_service() {
    local pid
    pid=$(get_service_pid)
    
    if [[ -n "$pid" ]]; then
        log_progress "Stopping service (PID: $pid)..."
        kill -TERM "$pid"
        
        # Wait up to 10 seconds for graceful shutdown
        local count=0
        while is_service_running && [[ $count -lt 10 ]]; do
            sleep 1
            ((count++))
        done
        
        if is_service_running; then
            log_warn "Graceful shutdown failed, force killing..."
            kill -KILL "$pid" 2>/dev/null || true
        fi
        
        log_success "Service stopped"
    else
        log_info "Service not running"
    fi
}

# ============================================================================
# API and Health Check Functions
# ============================================================================

# Make API call with timeout and error handling
api_call() {
    local endpoint="$1"
    local description="${2:-API call}"
    local host="${3:-$DEFAULT_HOST}"
    local port="${4:-$DEFAULT_PORT}"
    local timeout="${5:-10}"
    
    local url="http://${host}:${port}${endpoint}"
    
    log_debug "API call: $url"
    
    if ! response=$(curl -s --max-time "$timeout" --fail "$url" 2>/dev/null); then
        log_error "$description failed - endpoint not responding: $url"
        return 1
    fi
    
    if [[ -z "$response" ]]; then
        log_error "$description failed - empty response"
        return 1
    fi
    
    echo "$response"
    return 0
}

# Parse JSON response (requires jq)
parse_json() {
    local json="$1"
    local path="$2"
    local default="${3:-null}"
    
    if command_exists jq; then
        echo "$json" | jq -r "$path // \"$default\"" 2>/dev/null || echo "$default"
    else
        echo "$default"
    fi
}

# Basic connectivity check
check_connectivity() {
    local host="${1:-$DEFAULT_HOST}"
    local port="${2:-$DEFAULT_PORT}"
    local timeout="${3:-5}"
    
    if api_call "/health" "connectivity check" "$host" "$port" "$timeout" >/dev/null; then
        log_success "Service is responding at $host:$port"
        return 0
    else
        log_error "Service not responding at $host:$port"
        return 1
    fi
}

# ============================================================================
# File and Directory Management
# ============================================================================

# Create runtime directories
create_runtime_dirs() {
    local base_dir="$HOME/orangead/parking-monitor"
    local dirs=(
        "$base_dir"
        "$base_dir/logs"
        "$base_dir/models"
        "$base_dir/cache"
    )
    
    for dir in "${dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            log_debug "Runtime directory exists: $dir"
        else
            log_progress "Creating runtime directory: $dir"
            mkdir -p "$dir"
            log_success "Created: $dir"
        fi
    done
}

# Check disk space
check_disk_space() {
    local path="${1:-$HOME}"
    local min_gb="${2:-1}"
    
    if command_exists df; then
        local available_gb
        available_gb=$(df -BG "$path" | awk 'NR==2 {print $4}' | sed 's/G//')
        
        if [[ "$available_gb" -ge "$min_gb" ]]; then
            log_success "Disk space: ${available_gb}GB available"
            return 0
        else
            log_warn "Low disk space: ${available_gb}GB available (minimum: ${min_gb}GB)"
            return 1
        fi
    else
        log_warn "Cannot check disk space (df not available)"
        return 0
    fi
}

# ============================================================================
# Validation and Safety Checks
# ============================================================================

# Validate project structure
validate_project_structure() {
    cd_project_root
    
    local required_files=(
        "pyproject.toml"
        "uv.lock"
        "src/main.py"
        "src/detector.py"
        "src/config.py"
    )
    
    local missing_files=()
    for file in "${required_files[@]}"; do
        if [[ -f "$file" ]]; then
            log_debug "Found: $file"
        else
            missing_files+=("$file")
        fi
    done
    
    if [[ ${#missing_files[@]} -eq 0 ]]; then
        log_success "Project structure valid"
        return 0
    else
        log_error "Missing required files: ${missing_files[*]}"
        return 1
    fi
}

# Check system resources
check_system_resources() {
    # Check available memory
    if command_exists python3; then
        local memory_gb
        memory_gb=$(python3 -c "
import psutil
mem = psutil.virtual_memory()
print(f'{mem.total / (1024**3):.1f}')
" 2>/dev/null || echo "0")
        
        if (( $(echo "$memory_gb >= 8" | bc -l 2>/dev/null || echo "0") )); then
            log_success "Available memory: ${memory_gb}GB"
        else
            log_warn "Low memory detected: ${memory_gb}GB (recommend 8GB+)"
        fi
    fi
    
    # Check CPU usage
    if command_exists top; then
        local cpu_usage
        cpu_usage=$(top -l 1 -n 0 | grep "CPU usage" | awk '{print $3}' | sed 's/%//' 2>/dev/null || echo "0")
        log_info "Current CPU usage: ${cpu_usage}%"
    fi
}

# ============================================================================
# Utility Functions
# ============================================================================

# Convert seconds to human readable format
format_duration() {
    local seconds="$1"
    local hours=$((seconds / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))
    
    if [[ $hours -gt 0 ]]; then
        echo "${hours}h ${minutes}m ${secs}s"
    elif [[ $minutes -gt 0 ]]; then
        echo "${minutes}m ${secs}s"
    else
        echo "${secs}s"
    fi
}

# Get current timestamp
timestamp() {
    date +'%Y%m%d_%H%M%S'
}

# Clean up temporary files
cleanup_temp_files() {
    local temp_files=(
        "/tmp/health_response.json"
        "/tmp/detailed_health.json"
        "/tmp/performance.json"
        "/tmp/stats.json"
        "/tmp/system_info.json"
    )
    
    for file in "${temp_files[@]}"; do
        [[ -f "$file" ]] && rm -f "$file"
    done
    
    log_debug "Temporary files cleaned up"
}

# ============================================================================
# Error Handling and Cleanup
# ============================================================================

# Trap function for cleanup on exit
cleanup_on_exit() {
    local exit_code=$?
    cleanup_temp_files
    
    if [[ $exit_code -ne 0 ]]; then
        log_error "Script exited with error code: $exit_code"
    fi
    
    exit $exit_code
}

# Set up trap for cleanup
trap cleanup_on_exit EXIT

# ============================================================================
# Help and Usage Functions
# ============================================================================

# Print helper library version and info
print_helpers_info() {
    cat << EOF
${SERVICE_NAME} Helper Library v2.0.0

This library provides shared utilities for all ${SERVICE_NAME} scripts:
  - Logging and output formatting
  - Environment detection and management  
  - Virtual environment and dependency handling
  - Service management and health checks
  - API communication and JSON parsing
  - Validation and safety checks

Usage: Source this file in other scripts:
  source "\$(dirname "\$0")/helpers.sh"

Environment Variables:
  PARKING_MONITOR_ENV  - Override environment detection
  DEBUG               - Enable debug logging (0/1)
  LOG_FILE           - Log to file in addition to stdout

EOF
}

# Show usage if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    print_helpers_info
fi