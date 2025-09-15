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

# Simplified detailed health check using edge endpoints only
check_detailed_health() {
    log_header "Detailed Health Check"
    
    # Get configuration for system info
    local config_response
    if ! config_response=$(api_call "/config" "configuration check" "$HOST" "$PORT" "$TIMEOUT"); then
        log_warn "Configuration endpoint not available"
        return 0
    fi
    
    # Parse configuration data
    local software_version hostname total_spaces model_path
    software_version=$(parse_json "$config_response" ".version.software" "unknown")
    hostname=$(parse_json "$config_response" ".version.hostname" "unknown")
    total_spaces=$(parse_json "$config_response" ".device.totalSpaces" "0")
    model_path=$(parse_json "$config_response" ".device.modelPath" "unknown")
    
    log_info "Software version: $software_version"
    log_info "Hostname: $hostname"
    log_info "Total spaces: $total_spaces"
    log_info "Model path: $model_path"
    
    # Get current detection data
    local detection_response
    if detection_response=$(api_call "/detection" "current detection" "$HOST" "$PORT" "$TIMEOUT"); then
        local occupied_spaces occupancy_rate
        occupied_spaces=$(parse_json "$detection_response" ".occupiedSpaces" "0")
        
        if [[ "$total_spaces" != "0" ]]; then
            occupancy_rate=$(echo "scale=1; $occupied_spaces * 100 / $total_spaces" | bc -l 2>/dev/null || echo "0")
        else
            occupancy_rate="0"
        fi
        
        log_info "Occupied spaces: $occupied_spaces"
        log_info "Occupancy rate: ${occupancy_rate}%"
    else
        log_warn "Detection endpoint not responding"
    fi
    
    # Check camera status if available
    local camera_response
    if camera_response=$(api_call "/camera/status" "camera status" "$HOST" "$PORT" "$TIMEOUT"); then
        local camera_connected fps resolution
        camera_connected=$(parse_json "$camera_response" ".connected" "false")
        fps=$(parse_json "$camera_response" ".fps" "0")
        resolution=$(parse_json "$camera_response" ".resolution" "unknown")
        
        log_info "Camera connected: $camera_connected"
        log_info "Camera FPS: $fps"
        log_info "Camera resolution: $resolution"
        
        # Validate camera health
        if [[ "$camera_connected" != "true" ]]; then
            log_warn "Camera not connected"
        fi
        
        if (( $(echo "$fps < 15" | bc -l 2>/dev/null || echo "0") )); then
            log_warn "Low camera FPS: $fps"
        fi
    else
        log_warn "Camera status endpoint not available"
    fi
    
    log_success "Detailed edge health check completed"
    return 0
}

# Edge device performance check using available endpoints
check_performance() {
    log_header "Edge Performance Check"
    
    # Test core endpoint response times
    local start_time end_time response_time
    
    # Test /health endpoint response time
    start_time=$(date +%s%N | cut -c1-13)
    if api_call "/health" "health response time test" "$HOST" "$PORT" "$TIMEOUT" >/dev/null; then
        end_time=$(date +%s%N | cut -c1-13)
        response_time=$((end_time - start_time))
        log_info "Health endpoint response time: ${response_time}ms"
        
        if [[ $response_time -gt 1000 ]]; then
            log_warn "Slow health endpoint response: ${response_time}ms"
        fi
    else
        log_warn "Health endpoint not responding"
    fi
    
    # Test /detection endpoint response time
    start_time=$(date +%s%N | cut -c1-13)
    if api_call "/detection" "detection response time test" "$HOST" "$PORT" "$TIMEOUT" >/dev/null; then
        end_time=$(date +%s%N | cut -c1-13)
        response_time=$((end_time - start_time))
        log_info "Detection endpoint response time: ${response_time}ms"
        
        if [[ $response_time -gt 2000 ]]; then
            log_warn "Slow detection endpoint response: ${response_time}ms"
        fi
    else
        log_warn "Detection endpoint not responding"
    fi
    
    # Test /config endpoint response time
    start_time=$(date +%s%N | cut -c1-13)
    if api_call "/config" "config response time test" "$HOST" "$PORT" "$TIMEOUT" >/dev/null; then
        end_time=$(date +%s%N | cut -c1-13)
        response_time=$((end_time - start_time))
        log_info "Config endpoint response time: ${response_time}ms"
        
        if [[ $response_time -gt 1000 ]]; then
            log_warn "Slow config endpoint response: ${response_time}ms"
        fi
    else
        log_warn "Config endpoint not responding"
    fi
    
    log_success "Edge performance check completed"
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