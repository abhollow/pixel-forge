shader_type canvas_item;

// SWAY (per sprite): every sprite drawn with this material leans on its own,
// foot fixed - grass tufts, plants, trees. The companion of
// sway.gdshader, which moves masked pixels of ONE painted background.
//
// The sprite's top edge is pushed sideways in the vertex shader and the quad
// shears, so with nearest sampling the motion comes in whole-pixel stair
// steps down the sprite: it sways like pixel art, not like video. The phase
// offset comes from the sprite's own top-left corner in the world, so
// neighbours never move in lockstep and a sprite never stretches.
//
// Uniforms
//   phase   radians, kept in 0..TAU on the CPU
//   gust    0 calm .. 1 a gust passing (adds a lean)
//   amp     sway in px at a sprite's top on a calm day
//
// Drive phase from the CPU, never raw TIME (phones run shaders at reduced
// precision; a growing time stutters to a halt):
//     phase = fposmod(phase + delta * speed, TAU)
//     mat.set_shader_parameter("phase", phase)
//
// Works for whole textures drawn unscaled (draw_texture / Sprite2D at scale 1):
// UV / TEXTURE_PIXEL_SIZE finds the corner. Region or atlas draws need the
// corner passed differently. For many depth-sorted sprites drawn by one node's
// _draw(), shear each sprite with draw_set_transform_matrix from its foot
// instead. Fragment is untouched, so modulate works as usual.

uniform float phase = 0.0;
uniform float gust = 0.0;
uniform float amp = 1.3;

void vertex() {
	vec2 world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
	vec2 corner = world - UV / TEXTURE_PIXEL_SIZE;      // the same for all four corners
	float top = 1.0 - UV.y;                              // 1 at the top edge, 0 at the foot
	float w = sin(phase + corner.x * 0.043 + corner.y * 0.029);
	VERTEX.x += round(top * (amp * (0.7 + 1.5 * gust) * w + gust * 3.0));
}
