# Recording-only pacing helper.
#
# In your demo.sh, near the top, add:
#
#     source "${PACE_LIB:-/dev/null}" 2>/dev/null || true
#     type pace >/dev/null 2>&1 || pace() { :; }
#
# Then call `pace <weight>` between demo sections. `weight` is roughly the number
# of narration words spent on the section that JUST appeared on screen; render.sh
# sizes the holds so the on-screen action tracks the voice-over ("weighted sync").
#
# When your demo runs on its own (REC_PACE unset), pace does nothing and the demo
# runs at full speed — so your normal workflow is unaffected.
pace() {
  [ -z "${REC_PACE:-}" ] && return 0
  local secs
  secs=$(awk -v p="$REC_PACE" -v w="${1:-1}" 'BEGIN{printf "%.2f", p*w}')
  sleep "$secs" 2>/dev/null || true
}
