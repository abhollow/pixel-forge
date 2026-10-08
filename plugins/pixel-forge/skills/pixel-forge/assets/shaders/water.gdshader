shader_type canvas_item;

// WATER: moving water over a painted map, in code only. Draw it
// as a map-sized ColorRect (white) just above the ground and below everything
// built on it. Wherever the painted map is water - found by HUE, so it keeps
// working after a repaint changes the palette - the pixel is re-sampled a
// whole pixel or two away along slow sine waves, and now and then a glint
// passes. Off the water it draws nothing (discard). It replaces
// make_water_frames.py for water that is not a horizontal band.
//
// Uniforms
//   map        the painted map texture (the same one the ground draws)
//   map_size   its size in px
//   phase      radians, wrapped on the CPU at TAU * 6 (see below)
//   strength   0..1, how far it moves (0 = still)
//   hue_min, hue_max   the water's hue window, 0..1 (teal ~0.44-0.58).
//                      Measure it on the painting; don't guess.
//   min_value, min_sat darker or greyer pixels are never water
//   glint      the glint colour
//
// Drive phase from the CPU, never raw TIME. Every multiplier on phase below
// is a WHOLE number (1, 2, 3), so wrapping at a whole multiple of TAU is
// seamless:
//     phase = fposmod(phase + delta * speed, TAU * 6.0)
//     mat.set_shader_parameter("phase", phase)
//
// Check it moves with a pixel diff: thousands of water pixels should change
// over a second or so while land pixels stay put. Modulate (e.g. alpha to
// fade the effect) is respected through the vertex colour.

uniform sampler2D map : filter_nearest;
uniform vec2 map_size = vec2(960.0, 540.0);
uniform float phase = 0.0;
uniform float strength = 1.0;
uniform float hue_min = 0.44;
uniform float hue_max = 0.58;
uniform float min_value = 0.25;
uniform float min_sat = 0.25;
uniform vec3 glint = vec3(0.86, 0.95, 0.92);

varying vec4 modulate;

bool is_water(vec3 c) {
	float mx = max(c.r, max(c.g, c.b));
	float mn = min(c.r, min(c.g, c.b));
	float d = mx - mn;
	if (mx < min_value || d / mx < min_sat) {
		return false;
	}
	float h;
	if (mx == c.r) {
		h = mod((c.g - c.b) / d, 6.0);
	} else if (mx == c.g) {
		h = (c.b - c.r) / d + 2.0;
	} else {
		h = (c.r - c.g) / d + 4.0;
	}
	h /= 6.0;
	return h > hue_min && h < hue_max;
}

void vertex() {
	modulate = COLOR;
}

void fragment() {
	vec2 px = floor(UV * map_size);
	vec3 base = texture(map, (px + 0.5) / map_size).rgb;
	if (!is_water(base)) {
		discard;
	}
	// two slow waves: one rolling down the map, one across
	float w1 = sin(px.y * 0.16 - phase * 2.0 + sin(px.x * 0.05) * 2.0);
	float w2 = sin(px.x * 0.11 + px.y * 0.03 - phase);
	vec2 off = floor(vec2(w2 * 1.2, w1 * 1.4) * strength + 0.5);
	vec3 c = texture(map, (px + off + 0.5) / map_size).rgb;
	if (!is_water(c)) {
		c = base;   // never drag the bank into the water
	}
	// a glint where the two waves crest together, and a faint trough
	float g = sin(px.x * 0.07 + px.y * 0.19 - phase * 3.0) * sin(px.y * 0.09 - px.x * 0.02 + phase * 2.0);
	if (g > 0.9) {
		c = mix(c, glint, 0.28 * strength);
	} else if (g < -0.93) {
		c *= 0.94;
	}
	COLOR = vec4(c, 1.0) * modulate;
}
