shader_type canvas_item;

// NIGHT: darkness over the world with pools of light cut out of it -
// lanterns, fires, lit windows, a campfire's glow lying on the ground. Draw it
// as a world-sized ColorRect above the world and below the HUD. Things that
// should glow in the dark (fireflies, fireworks) go on a node ABOVE it.
//
// The light falls off in a few hard BANDS on a coarse pixel grid, not a smooth
// gradient: the retro way to draw firelight, and it keeps the dark looking like
// part of the pixel art rather than a filter laid over it.
//
// Uniforms
//   lights[32]   vec4(x, y, radius, depth) in world px. depth 1 = round;
//                below 1 = an ellipse lying on the ground (0.72 reads well)
//   light_count  how many of lights[] are live (32 is a hard cap - plan for it)
//   darkness     0 day .. ~0.9 deep night
//   night_color  the palette's night colour
//   rect_size    the rect's size in world px
//   grid         px per light step (2-3 reads as pixel art)
//   bands        falloff steps (4)
//   top_y        darkness fades in below this row (world px); < 0 = everywhere.
//                Above the fade the light loop is skipped - a free early-out.
//
// No time uniform: FLICKER IS COMPUTED ON THE CPU and arrives as radii, e.g.
//     var r := base_r * (1.0 + 0.06 * sin(flick_phase * 3.0) + 0.03 * sin(flick_phase * 7.0))
//     flick_phase = fposmod(flick_phase + delta, TAU)
//     lights.append(Vector4(x, y, r, 0.72)) ... then
//     mat.set_shader_parameter("lights", lights)   # PackedVector4Array / Array
//     mat.set_shader_parameter("light_count", lights.size())
// highp: world y reaches thousands of px in a tall map, past where mediump can
// hold a 3 px step (a 2160 px map is already past it). Never `return` inside
// fragment(): it is a compile error, the rect draws solid white, and only a
// windowed run's log says SHADER ERROR - branch instead, as below.
// Cost: this runs for every screen pixel at device resolution (canvas_items
// stretch). Hide the node by day (darkness 0) instead of drawing it transparent.

uniform vec4 lights[32];
uniform int light_count = 0;
uniform float darkness = 0.0;
uniform vec3 night_color = vec3(0.055, 0.063, 0.102);
uniform vec2 rect_size = vec2(960.0, 540.0);
uniform float grid = 3.0;
uniform float bands = 4.0;
uniform float top_y = -1.0;

void fragment() {
	highp vec2 p = floor(UV * rect_size / grid) * grid;
	float fade = top_y < 0.0 ? 1.0 : smoothstep(top_y - 30.0, top_y + 10.0, p.y);
	float lit = 0.0;
	if (fade > 0.0) {
		for (int i = 0; i < 32; i++) {
			if (i >= light_count) {
				break;
			}
			highp vec4 L = lights[i];
			highp vec2 dd = p - L.xy;
			dd.y /= max(L.w, 0.1);
			highp float d = length(dd);
			lit = max(lit, 1.0 - smoothstep(L.z * 0.45, L.z, d));
		}
	}
	lit = floor(lit * bands + 0.5) / bands;
	COLOR = vec4(night_color, darkness * (1.0 - lit) * fade);
}
