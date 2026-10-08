shader_type canvas_item;

// SPOTLIGHT: the tutorial's dimmer. Darkens the whole screen
// except up to two holes, each a circle/ellipse or a rounded rectangle, with a
// soft edge so it reads as a light rather than a cut-out. Draw it as a
// full-screen ColorRect on a CanvasLayer above the HUD; point the holes at
// what the current tutorial step talks about, and put the step's card on the
// opposite side of the screen.
//
// Uniforms
//   hole_a, hole_b      vec4(x, y, w, h) in screen px; w <= 0 means no hole
//   circle_a, circle_b  1 = circle/ellipse, 0 = rounded rectangle
//   dim                 darkness outside the holes, 0..1
//   size                the rect's size in px (the viewport size)
//
// Static - no phase. To pulse a hole, animate its rect from the CPU with a
// wrapped phase (phase = fposmod(phase + delta * speed, TAU)), not with TIME.

uniform vec4 hole_a = vec4(0.0);
uniform float circle_a = 0.0;
uniform vec4 hole_b = vec4(0.0);
uniform float circle_b = 0.0;
uniform float dim = 0.64;
uniform vec2 size = vec2(360.0, 640.0);

float box(vec2 p, vec2 half_size, float r) {
	vec2 q = abs(p) - half_size + r;
	return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

float hole(vec2 p, vec4 h, float circ) {
	if (h.z <= 0.0) {
		return 1.0e5;
	}
	vec2 half_size = h.zw * 0.5;
	vec2 c = h.xy + half_size;
	if (circ > 0.5) {
		float r = min(half_size.x, half_size.y);
		return length((p - c) / half_size) * r - r;
	}
	return box(p - c, half_size, 8.0);
}

void fragment() {
	vec2 p = UV * size;
	float d = min(hole(p, hole_a, circle_a), hole(p, hole_b, circle_b));
	COLOR = vec4(0.016, 0.03, 0.055, dim * smoothstep(-1.0, 4.0, d));
}
