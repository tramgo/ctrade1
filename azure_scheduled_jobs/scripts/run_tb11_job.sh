#!/usr/bin/env bash
set -euo pipefail

JOB_KIND="${1:-phase1}"
APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-${APP_DIR}/results/log_runs}"
PYTHON_EXE="${PYTHON_EXE:-python}"
GITHUB_OUTPUT_PUSH_ENABLED="${GITHUB_OUTPUT_PUSH_ENABLED:-0}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"
GITHUB_REPO_URL="${GITHUB_REPO_URL:-https://github.com/tramgo/ctrade1.git}"
GITHUB_COMMIT_NAME="${GITHUB_COMMIT_NAME:-ctrade1-azure-jobs}"
GITHUB_COMMIT_EMAIL="${GITHUB_COMMIT_EMAIL:-ctrade1-azure-jobs@users.noreply.github.com}"
GENERATED_OUTPUT_PATHS="${GENERATED_OUTPUT_PATHS:-results data}"
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-3}"
LOG_RETENTION_MIN_FILES="${LOG_RETENTION_MIN_FILES:-6}"

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

prune_old_logs() {
    if [[ ! -d "${LOG_DIR}" ]]; then
        return 0
    fi

    local days="${LOG_RETENTION_DAYS}"
    local min_files="${LOG_RETENTION_MIN_FILES}"
    if ! [[ "${days}" =~ ^[0-9]+$ ]]; then
        days="3"
    fi
    if ! [[ "${min_files}" =~ ^[0-9]+$ ]]; then
        min_files="6"
    fi
    if (( days < 1 )); then
        days="1"
    fi
    if (( min_files < 1 )); then
        min_files="1"
    fi

    echo "[AzureJob] pruning logs older than ${days} day(s), preserving at least ${min_files} per pattern" | tee -a "${LOG_FILE}"
    find "${LOG_DIR}" -mindepth 1 -maxdepth 1 -type d -name 'run_*' -mtime +"${days}" -printf '%T@ %p\0' \
        | sort -znr \
        | tail -zn +"$((min_files + 1))" \
        | cut -z -d' ' -f2- \
        | xargs -0 -r rm -rf
    find "${LOG_DIR}" -maxdepth 1 -type f -name 'tb11_*_azure.log' -mtime +"${days}" -printf '%T@ %p\0' \
        | sort -znr \
        | tail -zn +"$((min_files + 1))" \
        | cut -z -d' ' -f2- \
        | xargs -0 -r rm -f
}

push_generated_outputs() {
    if [[ "${GITHUB_OUTPUT_PUSH_ENABLED}" != "1" ]]; then
        echo "[AzureJob] github output push disabled" | tee -a "${LOG_FILE}"
        return 0
    fi

    local token="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
    if [[ -z "${token}" ]]; then
        echo "[AzureJob] github output push requested but GITHUB_TOKEN/GH_TOKEN is not set" | tee -a "${LOG_FILE}"
        return 65
    fi
    local git_auth
    git_auth="$(printf 'x-access-token:%s' "${token}" | base64 | tr -d '\n')"
    export GIT_TERMINAL_PROMPT=0

    local work_dir="/tmp/ctrade1-output-push"
    rm -rf "${work_dir}"
    git -c http.extraheader="AUTHORIZATION: basic ${git_auth}" \
        clone --depth 1 --branch "${GITHUB_BRANCH}" "${GITHUB_REPO_URL}" "${work_dir}" 2>&1 | tee -a "${LOG_FILE}"

    for relative_path in ${GENERATED_OUTPUT_PATHS}; do
        if [[ -e "${APP_DIR}/${relative_path}" ]]; then
            if [[ -d "${APP_DIR}/${relative_path}" ]]; then
                mkdir -p "${work_dir}/${relative_path}"
                cp -a "${APP_DIR}/${relative_path}/." "${work_dir}/${relative_path}/"
            else
                mkdir -p "${work_dir}/$(dirname "${relative_path}")"
                cp -a "${APP_DIR}/${relative_path}" "${work_dir}/${relative_path}"
            fi
            echo "[AzureJob] staged generated path ${relative_path}" | tee -a "${LOG_FILE}"
        else
            echo "[AzureJob] generated path missing, skipped ${relative_path}" | tee -a "${LOG_FILE}"
        fi
    done

    cd "${work_dir}"
    git config user.name "${GITHUB_COMMIT_NAME}"
    git config user.email "${GITHUB_COMMIT_EMAIL}"
    git config core.fileMode false
    git add -f ${GENERATED_OUTPUT_PATHS}

    if git diff --cached --quiet; then
        echo "[AzureJob] no generated output changes to commit" | tee -a "${LOG_FILE}"
        cd "${APP_DIR}"
        return 0
    fi

    git commit -m "Record Azure scheduled job outputs" \
        -m "Job kind: ${JOB_KIND}" \
        -m "Run timestamp UTC: ${RUN_TS}" 2>&1 | tee -a "${LOG_FILE}"
    git -c http.extraheader="AUTHORIZATION: basic ${git_auth}" \
        push origin "${GITHUB_BRANCH}" 2>&1 | tee -a "${LOG_FILE}"
    cd "${APP_DIR}"
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

prune_old_logs
push_generated_outputs

echo "[AzureJob] completed_utc=$(date -u +%Y%m%d_%H%M%S)" | tee -a "${LOG_FILE}"
