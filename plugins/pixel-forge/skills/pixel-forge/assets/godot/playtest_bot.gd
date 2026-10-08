extends SceneTree
## Headless playtest bot: plays the REAL game at human pace through the same
## public functions a player's taps reach, and writes one JSON line per
## attempt. It is the balance instrument: it measures, you change one knob at
## a time. Copy to tools/playtest_bot.gd, then fill in _choose() and _act().
##     godot --headless --max-fps 0 --path . --script res://tools/playtest_bot.gd ++ seeds=3 level=1
## Many runs in parallel: sh tools/run_bots.sh (save redirect, timeouts, summary).
##
## Options after ++ :
##     seeds=N      attempts, seeded 1..N (default 3)
##     level=N      the unit to start on (default 1); _arrive() grants what a
##                  campaign would own by then
##     limit=S      game seconds before an attempt counts as stuck (default 1800)
##     out=PATH     append JSON lines here (relative = the project folder)
##     debug=1      a state line every game second
##     ts=K         run in scaled REAL time (Engine.time_scale = K) instead of
##                  driving tick() by hand. Use it when the game uses physics
##                  bodies; physics ticks scale with it so the step stays 1/60 of
##                  a game second.
##     strict=0     exit 0 even when an attempt fails
## Exit code: 0 when every attempt clears (or strict=0), 1 otherwise.
##
## How to read it:
## * The bot is a fast, tireless, decent player - not a new one. It sees
##   everything, never gets discouraged, buys optimally. A human takes about
##   1.5x its time. A bot clear means a decent player can clear it; a bot fail
##   means "play it yourself", not "impossible".
## * Feel, fun, readability and onboarding are human-only questions.
## * Small samples are coin flips: 4 runs can give 2/4 by variance alone.
##   Baseline BEFORE changing anything, then compare.
## * Bot bugs masquerade as game bugs (lost in a maze, wedged on a corner).
##   Debug the bot before "fixing" the game, and report bot-tooling fixes apart
##   from game fixes.
## * After every run: grep -c "SCRIPT ERROR" the logs. An upgrade can be dead
##   on several levels, throwing thousands of errors, and only the bot logs
##   show it.
## * The game must take input through something the bot can call: public
##   functions (tap(pos), use_item(...)) or a public input object
##   (joystick.direction = dir). Design for it from the first grey-box.
## * The bot never writes the player's save (Session test paths + the live
##   guard), and run_bots.sh also redirects user:// for the whole run.

const STEP := 0.1          # game seconds per tick when driving time by hand
const REACT := 1.0         # seconds between acts: a person has to look, decide, reach
const REACT_JITTER := 0.4  # +- seconds, from the bot's own RNG
const TRACE_EVERY := 20.0  # seconds between trace samples

var game
var seeds := 3
var level := 1
var limit := 1800.0
var out_path := ""
var debug := false
var time_scale := 0.0      # 0 = drive tick() by hand
var strict := true
var bot_rng := RandomNumberGenerator.new()
var st := {}               # the current attempt's numbers


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := String(a).split("=", true, 1)
		if kv.size() != 2:
			continue
		match kv[0]:
			"seeds": seeds = maxi(1, int(kv[1]))
			"level": level = maxi(1, int(kv[1]))
			"limit": limit = float(kv[1])
			"out": out_path = kv[1]
			"debug": debug = kv[1] == "1"
			"ts": time_scale = float(kv[1])
			"strict": strict = kv[1] != "0"
	if out_path != "" and not (out_path.begins_with("res://") or out_path.begins_with("user://") or out_path.is_absolute_path()):
		out_path = ProjectSettings.globalize_path("res://" + out_path)
	if out_path != "":
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_path).get_base_dir())
	_run.call_deferred()


func _run() -> void:
	# Never the player's save. run_bots.sh gives each parallel run its own file
	# (++ save=...), which Session.setup() applies over this.
	Session.use_test_paths("bot")
	if time_scale > 0.0:
		Engine.time_scale = time_scale
		Engine.physics_ticks_per_second = int(60.0 * time_scale)
		Engine.max_physics_steps_per_frame = 64
	var cleared := 0
	for s in seeds:
		if await _attempt(s + 1):
			cleared += 1
	print("\nBOT_SUMMARY %d/%d attempts cleared (level %d)" % [cleared, seeds, level])
	Session.delete_test_files()
	quit(0 if cleared == seeds or not strict else 1)


## One attempt from the start of `level`. True if it cleared.
func _attempt(attempt_seed: int) -> bool:
	seed(attempt_seed)
	bot_rng.seed = attempt_seed * 7919
	game = load("res://scenes/main.tscn").instantiate()
	root.add_child(game)
	await process_frame
	if time_scale <= 0.0:
		game.running = false   # we drive time ourselves, far faster than real time
	game.rng.seed = attempt_seed
	_arrive(level)
	st = {"kind": "attempt", "seed": attempt_seed, "level": level, "result": "", "time_s": 0.0,
			"acts": 0, "hits": 0, "traces": {"score": [], "time_left": []}}
	var t := 0.0
	var next_act := 0.0
	var next_trace := 0.0
	var next_debug := 0.0
	while t < limit:
		var dt := STEP
		if time_scale > 0.0:
			await process_frame
			dt = root.get_process_delta_time()
		else:
			game.tick(dt)
		t += dt
		if _over():
			break
		if t >= next_trace:
			next_trace += TRACE_EVERY
			_sample()
		if debug and t >= next_debug:
			next_debug += 1.0
			print("  %6.1fs  %s" % [t, _state_line()])
		if t < next_act:
			continue
		var act = _choose()
		if act != null:
			_act(act)
			st["acts"] += 1
			next_act = t + REACT + bot_rng.randf_range(-REACT_JITTER, REACT_JITTER)
	_sample()
	st["result"] = _result() if _over() else "stuck"
	st["time_s"] = snappedf(t, 0.1)
	st["hits"] = int(game.stats.get("hits", 0))
	st["stats"] = game.stats.duplicate()
	_emit(st)
	var ok: bool = st["result"] == "clear"
	game.queue_free()
	await process_frame
	return ok


# --- the game-specific part: replace these ------------------------------------------

## Arrive at `lv` as a campaign would: grant what a player owns by then (e.g.
## one kept upgrade per finished level, in a fixed order).
func _arrive(lv: int) -> void:
	game.begin_unit(lv, false)


## True when the attempt is decided.
func _over() -> bool:
	return game.state != game.State.PLAYING


## "clear" or "fail" (anything else counts as not cleared).
func _result() -> String:
	return "clear" if game.state == game.State.CLEARED else "fail"


## The most useful act right now, or null to wait. A priority list works: score
## every option, take the best.
func _choose():
	return {"tap": game.box_rect().get_center()}


## Do it through the player's own path.
func _act(act) -> void:
	game.tap(act.tap)


## Numbers worth a trace line every TRACE_EVERY seconds.
func _sample() -> void:
	st["traces"]["score"].append(game.score)
	st["traces"]["time_left"].append(snappedf(game.time_left, 0.1))


func _state_line() -> String:
	return "unit %d  score %d/%d  left %.1f" % [game.unit, game.score, game.goal(), game.time_left]


# --- output ---------------------------------------------------------------------------

func _emit(d: Dictionary) -> void:
	var line := JSON.stringify(d)
	print("BOT|" + line)
	if out_path == "":
		return
	var f := FileAccess.open(out_path, FileAccess.READ_WRITE if FileAccess.file_exists(out_path) else FileAccess.WRITE)
	if f != null:
		f.seek_end()
		f.store_line(line)
		f.close()
