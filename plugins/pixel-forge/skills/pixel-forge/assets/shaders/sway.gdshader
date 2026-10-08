shader_type canvas_item;

// SWAY (masked): makes painted trees, flags and kites on ONE background image
// move in the wind. They are part of the painting, so they cannot be animated
// as sprites; instead the pixels marked in sway_mask are shifted sideways - a
// steady LEAN downwind plus a wobble, both growing with the current gust.
// Make the mask with scripts/make_sway_mask.py. For separate sprites (grass
// tufts, trees, plants) use sway_sprite.gdshader instead.
//
// Uniforms
//   sway_mask  white where pixels may move (soft edges fine), black elsewhere
//   phase      radians, kept in 0..TAU on the CPU (see below)
//   gust       0 calm .. 1 peak of a gust
//   lean       steady downwind lean, texels
//   amp        wobble, texels
//
// Drive phase from the CPU - never raw TIME for long-running motion. Phone
// GPUs run fragment shaders at reduced precision: a growing time can only
// change in coarse jumps and the sway stutters to a halt a few minutes in;
// and changing speed with a large time jumps the phase, turning gusts into
// flicker. Accumulate and wrap instead:
//     phase = fposmod(phase + delta * speed, TAU)
//     mat.set_shader_parameter("phase", phase)
// (Wrap at TAU * N if you add multipliers on phase; keep them whole numbers.)
// Mirror every uniform you set in a script variable: reading back a uniform
// that was never written returns null.
//
// Modulate is respected: COLOR arrives as texture x modulate, so the moved
// pixels are re-sampled and multiplied by the vertex modulate only - never
// texture(TEXTURE) * COLOR, which squares the texture (and darkens the
// sprite). Displacement is whole texels with nearest sampling, so the
// motion comes in pixel steps, not a video smear.

uniform sampler2D sway_mask : filter_linear;
uniform float phase = 0.0;
uniform float gust = 0.0;
uniform float lean = 1.0;
uniform float amp = 1.4;

varying vec4 modulate;

void vertex() {
	modulate = COLOR;
}

void fragment() {
	float m = texture(sway_mask, UV).r;
	if (m > 0.02) {
		// The offset varies across and down the image, so neighbouring trees
		// and the branches within one tree never move in lockstep.
		float wob = sin(phase + UV.x * 38.0 + UV.y * 22.0);
		float d = floor(m * (lean * (1.0 + 1.6 * gust) + amp * (0.8 + 1.0 * gust) * wob) + 0.5);
		// Sample from the LEFT to move content right - downwind.
		COLOR = texture(TEXTURE, UV - vec2(d * TEXTURE_PIXEL_SIZE.x, 0.0)) * modulate;
	}
}
