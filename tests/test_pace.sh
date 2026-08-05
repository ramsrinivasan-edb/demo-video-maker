set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
check() { if [ "$2" = "$3" ]; then echo "ok - $1"; else echo "FAIL - $1: expected [$2] got [$3]"; fail=1; fi; }

# Shim sleep to print its argument instead of sleeping. Command-substitution
# subshells inherit this function, and pace.sh (sourced inside) calls it.
sleep() { printf '%s\n' "$1"; }

out="$( REC_PACE_LIST="1 2 3"; unset PACE_IDX REC_PACE 2>/dev/null; . "$ROOT/lib/pace.sh"; pace; pace; pace )"
check "list mode order" "$(printf '1\n2\n3')" "$out"

out="$( REC_PACE="0.5"; unset REC_PACE_LIST PACE_IDX 2>/dev/null; . "$ROOT/lib/pace.sh"; pace 4 )"
check "weighted mode" "2.00" "$out"

out="$( unset REC_PACE REC_PACE_LIST PACE_IDX 2>/dev/null; . "$ROOT/lib/pace.sh"; pace 5 )"
check "off mode silent" "" "$out"

exit $fail
