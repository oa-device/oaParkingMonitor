#!/bin/bash
# oaParkingMonitor Health Check Script
# Quick service health validation with JSON parsing support

# Load shared utilities
# shellcheck source=helpers.sh
source "$(dirname "$0")/helpers.sh"

# Script-specific configuration
readonly SCRIPT_VERSION="2.0.0"

# Default settings
HOST="$DEFAULT_HOST"
PORT="$DEFAULT_PORT"
TIMEOUT=10
DETAILED=false

# Parse arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --host)
                HOST="$2"
                shift 2
                ;;
            --port)
                PORT="$2"
                shift 2
                ;;
            --timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            --detailed)
                DETAILED=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

show_usage() {
    cat << EOF
${SERVICE_NAME} Health Check Script v${SCRIPT_VERSION}

Usage: $0 [OPTIONS]

Options:
  --host HOST      Host to check (default: $DEFAULT_HOST)
  --port PORT      Port to check (default: $DEFAULT_PORT)
  --timeout SECS   Request timeout (default: 10)
  --detailed       Show detailed health information
  -h, --help       Show this help message

Examples:
  $0                           # Quick health check
  $0 --detailed                # Detailed health check
  $0 --host 192.168.1.100      # Check remote host
  $0 --timeout 30 --detailed   # Extended timeout with details

EOF
}

# Basic health check
check_basic_health() {
    log_header "Basic Health Check"
    
    log_info "Target: http://${HOST}:${PORT}"
    log_info "Timeout: ${TIMEOUT}s"
    
    # Check connectivity
    if ! check_connectivity "$HOST" "$PORT" "$TIMEOUT"; then
        return 1
    fi
    
    # Get health response
    local response
    if ! response=$(api_call "/health" "basic health check" "$HOST" "$PORT" "$TIMEOUT"); then
        return 1
    fi
    
    # Parse response
    local status uptime version
    status=$(parse_json "$response" ".status" "unknown")
    uptime=$(parse_json "$response" ".uptime" "0")
    version=$(parse_json "$response" ".version" "unknown")
    
    log_info "Status: $status"
    log_info "Version: $version"
    log_info "Uptime: $(format_duration "${uptime%.*}")"
    
    # Validate health status
    if [[ "$status" == "ok" ]]; then
        log_success "Service is healthy!"
        return 0
    else
        log_error "Service is not healthy (status: $status)"
        log_debug "Full response: $response"
        return 1
    fi
}

# Detailed health check
check_detailed_health() {
    log_header "Detailed Health Check"
    
    # Get detailed health information
    local detailed_response
    if ! detailed_response=$(api_call "/api/health/detailed" "detailed health check" "$HOST" "$PORT" "$TIMEOUT"); then
        log_warn "Detailed health endpoint not available"
        return 0
    fi
    
    # Parse detailed metrics
    local health_score cpu_percent memory_percent error_count
    local model_loaded device metal_available
    
    health_score=$(parse_json "$detailed_response" ".health_score" "0")
    cpu_percent=$(parse_json "$detailed_response" ".system.cpu_percent" "0")
    memory_percent=$(parse_json "$detailed_response" ".system.memory_percent" "0")
    error_count=$(parse_json "$detailed_response" ".system.error_count" "0")
    model_loaded=$(parse_json "$detailed_response" ".detector.model_loaded" "false")
    device=$(parse_json "$detailed_response" ".detector.device" "unknown")
    metal_available=$(parse_json "$detailed_response" ".detector.metal_available" "false")
    
    log_info "Health score: ${health_score}/100"
    log_info "CPU usage: ${cpu_percent}%"
    log_info "Memory usage: ${memory_percent}%"
    log_info "Error count: $error_count"
    log_info "Model loaded: $model_loaded"
    log_info "Device: $device"
    log_info "Metal available: $metal_available"
    
    # Validate thresholds
    local warnings=0
    
    if (( $(echo "$health_score < 70" | bc -l 2>/dev/null || echo "0") )); then
        log_warn "Health score below threshold: $health_score"
        ((warnings++))
    fi
    
    if (( $(echo "$cpu_percent > 80" | bc -l 2>/dev/null || echo "0") )); then
        log_warn "High CPU usage: ${cpu_percent}%"
        ((warnings++))
    fi
    
    if (( $(echo "$memory_percent > 85" | bc -l 2>/dev/null || echo "0") )); then
        log_warn "High memory usage: ${memory_percent}%"
        ((warnings++))
    fi
    
    if [[ "$model_loaded" != "true" ]]; then
        log_warn "AI model not loaded"
        ((warnings++))
    fi
    
    if [[ "$error_count" != "0" ]]; then
        log_warn "Service has recorded $error_count errors"
        ((warnings++))
    fi
    
    if [[ $warnings -eq 0 ]]; then
        log_success "All detailed checks passed!"
    else
        log_warn "Detailed checks completed with $warnings warning(s)"
    fi
    
    return $warnings
}

# Performance metrics check
check_performance() {
    log_header "Performance Metrics"
    
    # Get performance metrics
    local perf_response
    if ! perf_response=$(api_call "/api/performance" "performance metrics" "$HOST" "$PORT" "$TIMEOUT"); then
        log_warn "Performance endpoint not available"
        return 0
    fi
    
    # Parse performance data
    local avg_inference memory_gb temperature processing_fps
    
    avg_inference=$(parse_json "$perf_response" ".inference_stats.avg_ms" "0")
    memory_gb=$(parse_json "$perf_response" ".performance.memory_usage_gb" "0")
    temperature=$(parse_json "$perf_response" ".performance.temperature" "0")
    
    # Get detection stats
    local stats_response
    if stats_response=$(api_call "/api/stats" "detection statistics" "$HOST" "$PORT" "$TIMEOUT"); then
        processing_fps=$(parse_json "$stats_response" ".processing_fps" "0")
    else
        processing_fps="0"
    fi
    
    log_info "Average inference time: ${avg_inference}ms"
    log_info "Memory usage: ${memory_gb}GB"
    log_info "Processing FPS: $processing_fps"
    if [[ "$temperature" != "0" ]]; then
        log_info "Temperature: ${temperature}°C"
    fi
    
    # Performance warnings
    if (( $(echo "$avg_inference > 100" | bc -l 2>/dev/null || echo "0") )); then
        log_warn "High inference time: ${avg_inference}ms"
    fi
    
    if (( $(echo "$processing_fps < 10" | bc -l 2>/dev/null || echo "0") )); then
        log_warn "Low processing FPS: $processing_fps"
    fi
    
    return 0
}

# Main execution
main() {
    log_info "${SERVICE_NAME} Health Check v${SCRIPT_VERSION}"
    
    # Parse arguments
    parse_arguments "$@"
    
    local exit_code=0
    
    # Basic health check
    if ! check_basic_health; then
        exit_code=1
    fi
    
    # Detailed checks if requested
    if [[ "$DETAILED" == "true" ]]; then
        check_detailed_health || true  # Don't fail on warnings
        check_performance || true      # Don't fail on warnings
    fi
    
    # Final status
    echo
    if [[ $exit_code -eq 0 ]]; then
        log_success "Health check completed successfully"
    else
        log_error "Health check failed - service requires attention"
    fi
    
    exit $exit_code
}

# Execute main function
main "$@"