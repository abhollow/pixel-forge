#!/bin/sh
# Import, then run the headless smoke test. Exit code: the smoke test's own
# (0 = every check passed), or 1 if the log shows a SCRIPT ERROR / SHADER
# ERROR / parse error even though the checks passed, or 124 on a timeout.
#
#   sh tools/run_tests.sh              (from the game folder; Git Bash on Windows)
#   GODOT=/path/to/godot_console sh tools/run_tests.sh
#   TEST_TIMEOUT=900 sh tools/run_tests.sh
#
# GODOT must be the CONSOLE build on Windows (Godot_v4.x-stable_win64_console.exe):
# the plain exe prints nothing. scripts/doctor.py finds it and CLAUDE.local.md
# records it. The full log is kept in .godot/smoke_test.log.
cd "$(dirname "$0")/.." || exit 1
G="${GODOT:-godot}"
SECS="${TEST_TIMEOUT:-600}"
if command -v timeout >/dev/null 2>&1; then T="timeout $SECS"
elif command -v gtimeout >/dev/null 2>&1; then T="gtimeout $SECS"
else T=""; echo "note: no timeout command; a hung run will not be stopped"; fi
if ! command -v "$G" >/dev/null 2>&1 && [ ! -x "$G" ]; then
  echo "Godot not found: set GODOT to the console executable (scripts/doctor.py finds it)"; exit 1
fi
mkdir -p .godot
LOG=.godot/smoke_test.log

# Import first: new art does not draw and a new class_name is "not found"
# until the import cache is refreshed.
$T "$G" --headless --path . --import >.godot/import.log 2>&1 || echo "note: import exited non-zero (see .godot/import.log)"

$T "$G" --headless --path . --script res://tools/smoke_test.gd >"$LOG" 2>&1
RC=$?
cat "$LOG"
[ "$RC" -eq 124 ] && echo "TIMEOUT after ${SECS}s"
ERRS=$(grep -c -E "SCRIPT ERROR|SHADER ERROR|Parse Error|Failed to load script" "$LOG")
if [ "$ERRS" -gt 0 ]; then
  echo "$ERRS script/shader error line(s) in the log:"
  grep -E "SCRIPT ERROR|SHADER ERROR|Parse Error|Failed to load script" "$LOG" | head -n 10
  [ "$RC" -eq 0 ] && RC=1
fi
WARN=$(grep -c "^ERROR:" "$LOG")
[ "$WARN" -gt 0 ] && echo "note: $WARN engine ERROR: line(s) (leaks at exit and the like) - read them"
exit $RC
