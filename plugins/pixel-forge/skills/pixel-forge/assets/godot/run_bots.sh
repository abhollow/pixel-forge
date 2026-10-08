#!/bin/sh
# Runs the playtest bot (tools/playtest_bot.gd) several times IN PARALLEL, one
# Godot process per run, and prints a summary. Copy to tools/run_bots.sh.
#
#   sh tools/run_bots.sh OUTDIR [SEEDS] [RUN_ARGS...]
#   sh tools/run_bots.sh out/bots 3 "level=1" "level=2" "level=3 limit=900"
#
# Each RUN_ARGS string is passed to the bot after ++ (default: "level=1").
# Per run: OUTDIR/runN.jsonl (one JSON line per attempt) and OUTDIR/runN.log.
# Env: GODOT (console exe on Windows), BOT_TIMEOUT seconds per run (default 1800).
#
# What it guards against:
# * --max-fps 0: the game caps at 60 fps (run/max_fps), and at a raised time
#   scale that crams several physics steps into each frame the bot steers on -
#   the bot wedges on corners and clear rates collapse.
# * The player's save: override.cfg points user:// at a separate folder for the
#   whole run (removed on exit), and each run gets its own save file
#   (++ save=user://bot_runN.dat), so parallel runs never share one.
# * Two runners at once: override.cfg is the lock. If it exists, another run is
#   active (or crashed: delete it by hand). Never commit override.cfg.
# * Hangs: every Godot call is wrapped in timeout.
# * Silent script errors: the summary counts SCRIPT ERROR lines per run.
cd "$(dirname "$0")/.." || exit 1
OUT="${1:?usage: sh tools/run_bots.sh OUTDIR [SEEDS] [RUN_ARGS...]}"
SEEDS="${2:-3}"
[ $# -ge 2 ] && shift 2 || shift $#
[ $# -eq 0 ] && set -- "level=1"
G="${GODOT:-godot}"
SECS="${BOT_TIMEOUT:-1800}"
if command -v timeout >/dev/null 2>&1; then T="timeout $SECS"
elif command -v gtimeout >/dev/null 2>&1; then T="gtimeout $SECS"
else T=""; echo "note: no timeout command; a hung run will not be stopped"; fi
if ! command -v "$G" >/dev/null 2>&1 && [ ! -x "$G" ]; then
  echo "Godot not found: set GODOT to the console executable (scripts/doctor.py finds it)"; exit 1
fi
if [ -e override.cfg ]; then
  echo "override.cfg exists: another bot run is active, or one crashed (then delete it)"; exit 1
fi
NAME=$(basename "$(pwd)" | tr -c 'A-Za-z0-9\n' '-')
printf '[application]\nconfig/use_custom_user_dir=true\nconfig/custom_user_dir_name="%s-bots"\n' "$NAME" > override.cfg
trap 'rm -f override.cfg' EXIT INT TERM
mkdir -p "$OUT"

i=0
PIDS=""
for ARGS in "$@"; do
  i=$((i + 1))
  rm -f "$OUT/run$i.jsonl"
  echo "run$i: $ARGS"
  # shellcheck disable=SC2086
  $T "$G" --headless --max-fps 0 --path . --script res://tools/playtest_bot.gd ++ \
      seeds="$SEEDS" save="user://bot_run$i.dat" settings="user://bot_run$i.cfg" out="$OUT/run$i.jsonl" $ARGS \
      > "$OUT/run$i.log" 2>&1 &
  PIDS="$PIDS $!"
done
FAILED=0
for P in $PIDS; do
  wait "$P" || FAILED=$((FAILED + 1))
done

echo
echo "=== bot summary ($OUT) ==="
TOTAL_ERR=0
j=0
for ARGS in "$@"; do
  j=$((j + 1))
  N=$(grep -c '"kind":"attempt"' "$OUT/run$j.jsonl" 2>/dev/null || true)
  C=$(grep -c '"result":"clear"' "$OUT/run$j.jsonl" 2>/dev/null || true)
  E=$(grep -c "SCRIPT ERROR" "$OUT/run$j.log" 2>/dev/null || true)
  TOTAL_ERR=$((TOTAL_ERR + ${E:-0}))
  echo "run$j  ${C:-0}/${N:-0} cleared  SCRIPT ERROR x${E:-0}  ($ARGS)"
done
echo "runs with a non-zero exit: $FAILED   SCRIPT ERROR lines in all logs: $TOTAL_ERR"
[ "$TOTAL_ERR" -gt 0 ] && echo "read them first: grep -n 'SCRIPT ERROR' $OUT/*.log"
[ "$FAILED" -eq 0 ] && [ "$TOTAL_ERR" -eq 0 ]
