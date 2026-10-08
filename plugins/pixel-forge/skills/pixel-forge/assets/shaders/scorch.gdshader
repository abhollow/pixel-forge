shader_type canvas_item;

// SCORCH (optional): a "corrupted land / restored land" overlay (e.g. burnt
// land that heals outward from the player's buildings). Draw it as
// a map-sized ColorRect over the ground, fields and paths, under everything
// that stands up. Everywhere OUTSIDE the healed ellipses, what is under it is
// drawn burnt: drained of colour, darkened toward ash, with embers winking. At
// the edge of the healed ground it breaks up in a dithered grid, so healing
// spreads in ragged chunks rather than a smooth circle.
//
// Uniforms
//   heals[8]     vec4(centre x, centre y, radius x, radius y) in rect px
//   heal_count   how many are live
//   rect_size    the rect's size in px
//   phase        radians, wrapped on the CPU at TAU (multipliers are whole numbers)
//   cell         dither cell size in px
//   burnt_tint   the colour the land drains toward
//   ember        the colour of the glowing embers
//
//     phase = fposmod(phase + delta * speed, TAU)
//     mat.set_shader_parameter("phase", phase)
//
// Cost: it reads the screen texture (hint_screen_texture), the most expensive
// thing a 2D frame can do on a phone, at device resolution. Hide the node when
// nothing is scorched instead of leaving it drawing.

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform vec4 heals[8];
uniform int heal_count = 0;
uniform vec2 rect_size = vec2(960.0, 540.0);
uniform float phase = 0.0;
uniform float cell = 3.0;
uniform vec3 burnt_tint = vec3(0.62, 0.30, 0.24);
uniform vec3 ember = vec3(0.95, 0.45, 0.12);

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
	vec2 px = UV * rect_size;
	vec2 c = floor(px / cell);
	float n = hash(c);
	float healed = 0.0;
	for (int i = 0; i < 8; i++) {
		if (i >= heal_count) {
			break;
		}
		float q = length((px - heals[i].xy) / max(heals[i].zw, vec2(0.001)));
		healed = max(healed, 1.0 - smoothstep(0.7, 1.0, q));
	}
	if (n < healed) {
		discard;   // restored: the ground underneath shows through
	}
	vec3 col = texture(screen_tex, SCREEN_UV).rgb;
	float lum = dot(col, vec3(0.3, 0.59, 0.11));
	vec3 burnt = mix(vec3(lum), burnt_tint * (0.45 + lum), 0.6) * 0.85;
	float e = hash(c + vec2(17.0, 3.0));
	if (e > 0.996 && sin(phase * 3.0 + n * 40.0) > 0.4) {
		burnt = mix(burnt, ember, 0.8);
	}
	COLOR = vec4(burnt, 1.0);
}
