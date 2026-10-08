shader_type canvas_item;

// REPLACE COLOR, like Photoshop's: pixels near one HUE are turned to a target
// hue (keeping their own shading), with a full-strength radius and a fade
// radius around it, and saturation/value gates that protect outlines, shadows
// and near-greys. One sprite set gives a crowd in many colours, a jacket in a
// second colour, an enemy variant - with no second set of art to cut and keep
// in sync.
//
// Uniforms (hues in DEGREES, 0..360)
//   hue_center   the hue to replace - MEASURE it on the sprite (a hue
//                histogram, scripts/measure_hues.py), don't guess: a vest at
//                50-58 deg next to skin at 21-33 and a bag at 60-73 needs a
//                tight window; a 45-72 window turns the bag too
//   hue_full     within this distance of hue_center: fully replaced
//   hue_fade     ...fading to untouched by this distance
//   sat_min, sat_soft   saturation gate: below sat_min untouched, full above
//                sat_min + sat_soft (protects whites, greys, pale stripes)
//   val_min, val_soft   value gate (protects dark outlines and shadows)
//   target_hue   where matching pixels go; their offset from hue_center is
//                kept, so a shaded red stays shaded in blue
//   sat_scale, val_scale   multiply the replaced pixels' saturation / value
//   amount       0..1 overall strength (0 = off: share one material and
//                switch it per instance with amount, or hide it)
//   region       vec4(u0, v0, u1, v1): only replace inside this UV box (e.g.
//                skip the head: keep the top third out when flushed faces
//                share the clothing's red)
//
// Static recolour - no phase. If you animate target_hue, drive it from the
// CPU: hue = fposmod(hue + delta * speed, 360.0).
// Starts from COLOR (texture x modulate already): never texture(TEXTURE) * COLOR,
// which squares every channel (a tint then turns skin deep red).
// Region UVs are the texture's UVs - in an atlas, the atlas's.

uniform float hue_center = 330.0;
uniform float hue_full = 15.0;
uniform float hue_fade = 22.0;
uniform float sat_min = 0.25;
uniform float sat_soft = 0.15;
uniform float val_min = 0.2;
uniform float val_soft = 0.12;
uniform float target_hue = 200.0;
uniform float sat_scale = 1.0;
uniform float val_scale = 1.0;
uniform float amount : hint_range(0.0, 1.0) = 1.0;
uniform vec4 region = vec4(0.0, 0.0, 1.0, 1.0);

vec3 rgb2hsv(vec3 c) {
	vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
	vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
	vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
	float d = q.x - min(q.w, q.y);
	float e = 1.0e-10;
	return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c) {
	vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
	vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
	return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

float hue_dist(float a, float b) {
	return abs(mod(a - b + 180.0, 360.0) - 180.0);
}

void fragment() {
	vec4 c = COLOR;
	bool inside = UV.x >= region.x && UV.y >= region.y && UV.x <= region.z && UV.y <= region.w;
	if (c.a > 0.0 && amount > 0.0 && inside) {
		vec3 hsv = rgb2hsv(c.rgb);
		float h = hsv.x * 360.0;
		float gate = smoothstep(sat_min, sat_min + sat_soft, hsv.y) * smoothstep(val_min, val_min + val_soft, hsv.z);
		float w = (1.0 - smoothstep(hue_full, max(hue_fade, hue_full + 0.001), hue_dist(h, hue_center))) * gate * amount;
		if (w > 0.0) {
			float nh = fract((target_hue + (h - hue_center)) / 360.0);
			vec3 to = hsv2rgb(vec3(nh, clamp(hsv.y * sat_scale, 0.0, 1.0), clamp(hsv.z * val_scale, 0.0, 1.0)));
			c.rgb = mix(c.rgb, to, w);
		}
	}
	COLOR = c;
}
