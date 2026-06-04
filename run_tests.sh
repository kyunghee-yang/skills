#!/usr/bin/env bash
# 저장소 내 모든 스킬의 테스트 스위트를 한 번에 실행한다.
# CI(.github/workflows/ci.yml)와 동일한 잡들을 로컬에서 재현하기 위한 편의 스크립트.
#
# 사용법:
#   ./run_tests.sh            # 전체 실행
#   ./run_tests.sh -q         # pytest 옵션 그대로 전달
set -euo pipefail

cd "$(dirname "$0")"

PYTEST_ARGS=("$@")
declare -a SUITES=("expense-report" "task-check" "autoresearch" "daily-report")
failed=0

# 린트(ruff)를 먼저 돌린다 — 규칙은 ruff.toml(로컬/CI 동일). 미설치 시 건너뛴다.
if command -v ruff >/dev/null 2>&1; then
  echo "==================== lint (ruff) ===================="
  if ruff check .; then echo "[lint] PASS"; else echo "[lint] FAIL"; failed=1; fi
  echo
fi

for suite in "${SUITES[@]}"; do
  echo "==================== $suite ===================="
  if [ -f "$suite/requirements.txt" ]; then
    pip install -q -r "$suite/requirements.txt"
  fi
  if ( cd "$suite" && python3 -m pytest "${PYTEST_ARGS[@]}" ); then
    echo "[$suite] PASS"
  else
    echo "[$suite] FAIL"
    failed=1
  fi
  echo
done

if [ "$failed" -ne 0 ]; then
  echo "일부 스위트가 실패했습니다." >&2
  exit 1
fi
echo "모든 스위트 통과 ✅"
