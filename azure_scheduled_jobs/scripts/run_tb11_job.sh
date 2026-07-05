#!/usr/bin/env bash
set -euo pipefail

JOB_KIND="${1:-phase1}"
APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-${APP_DIR}/results/log_runs}"
PYTHON_EXE="${PYTHON_EXE:-python}"

PHASE1_MODE="signal_baseline_tb11_options_phase1_auto_quote_observation"
COLLECTOR_MODE="signal_baseline_tb11_options_nifty_chain_band_quote_collector"
GATE_MODE="signal_baseline_tb11_options_t28_freshness_gate"
READINESS_MODE="signal_baseline_tb11_options_phase2_paper_price_reconciliation_readiness"
TRANSITION_MODE="signal_baseline_tb11_options_phase2_transition_controller"

mkdir -p "${LOG_DIR}"
cd "${APP_DIR}"

RUN_TS="$(date -u +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/tb11_${JOB_KIND}_${RUN_TS}_azure.log"
echo "${LOG_FILE}" > "${LOG_DIR}/latest_mode_log.txt"

run_mode() {
    local mode="$1"
    echo "[AzureJob] running mode=${mode}" | tee -a "${LOG_FILE}"
    "${PYTHON_EXE}" -u -B ssell1.py --mode "${mode}" 2>&1 | tee -a "${LOG_FILE}"
    local exit_code="${PIPESTATUS[0]}"
    echo "[AzureJob] mode=${mode} exit=${exit_code}" | tee -a "${LOG_FILE}"
    return "${exit_code}"
}

echo "[AzureJob] started_utc=${RUN_TS}" | tee -a "${LOG_FILE}"
echo "[AzureJob] job_kind=${JOB_KIND}" | tee -a "${LOG_FILE}"
echo "[AzureJob] app_dir=${APP_DIR}" | tee -a "${LOG_FILE}"
"${PYTHON_EXE}" --version 2>&1 | tee -a "${LOG_FILE}"

case "${JOB_KIND}" in
    phase1)
        run_mode "${PHASE1_MODE}"
        run_mode "${READINESS_MODE}"
        run_mode "${TRANSITION_MODE}"
        ;;
    t28)
        run_mode "${COLLECTOR_MODE}"
        run_mode "${GATE_MODE}"
        run_mode "${READINESS_MODE}"
        run_mode "${TRANSITION_MODE}"
        ;;
    readiness)
        run_mode "${READINESS_MODE}"
        run_mode "${TRANSITION_MODE}"
        ;;
    *)
        echo "[AzureJob] unknown job kind: ${JOB_KIND}" | tee -a "${LOG_FILE}"
        echo "[AzureJob] expected one of: phase1, t28, readiness" | tee -a "${LOG_FILE}"
        exit 64
        ;;
esac

echo "[AzureJob] completed_utc=$(date -u +%Y%m%d_%H%M%S)" | tee -a "${LOG_FILE}"
