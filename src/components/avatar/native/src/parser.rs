use napi::bindgen_prelude::*;
use napi_derive::napi;
use serde::{Deserialize, Serialize};
use serde_json::Value;

// --- Internal Data Structures for Serde Parsing ---

#[derive(Deserialize)]
struct BedrockModel {
    #[serde(rename = "minecraft:geometry")]
    geometry: Vec<BedrockGeometry>,
}

#[derive(Deserialize)]
struct BedrockGeometry {
    description: Description,
    bones: Option<Vec<Bone>>,
}

#[derive(Deserialize)]
struct Description {
    texture_width: f64,
    texture_height: f64,
}

#[derive(Deserialize)]
struct Bone {
    name: String,
    parent: Option<String>,
    pivot: Option<Vec<f64>>,
    rotation: Option<Vec<f64>>,
    cubes: Option<Vec<Cube>>,
}

#[derive(Deserialize)]
struct Cube {
    origin: Option<Vec<f64>>,
    size: Option<Vec<f64>>,
    pivot: Option<Vec<f64>>,
    rotation: Option<Vec<f64>>,
    inflate: Option<f64>,
    mirror: Option<bool>,
    uv: Option<Value>, // Can be Array([u, v]) or Object({north: ..., south: ...})
}

// --- Public Data Structures for NAPI ---

#[napi(object)]
pub struct ParsedModelData {
    #[napi(js_name = "textureWidth")]
    pub texture_width: f64,
    #[napi(js_name = "textureHeight")]
    pub texture_height: f64,
    pub bones: Vec<ParsedBone>,
}

#[napi(object)]
pub struct ParsedBone {
    pub name: String,
    pub parent: Option<String>,
    pub pivot: Vec<f64>,
    pub rotation: Option<Vec<f64>>,
    // Generated Geometry Data
    #[napi(ts_type = "Float32Array")]
    pub vertices: Option<Float32Array>,
    #[napi(ts_type = "Float32Array")]
    pub uvs: Option<Float32Array>,
    #[napi(ts_type = "Uint16Array")]
    pub indices: Option<Uint16Array>,
}

// --- Geometry Generation Implementation ---

pub fn parse_model(data: &[u8]) -> Result<ParsedModelData> {
    // 1. Parse JSON
    let model: BedrockModel = serde_json::from_slice(data)
        .map_err(|e| Error::new(Status::InvalidArg, format!("Failed to parse JSON: {}", e)))?;

    // 2. Extract Geometry and Bones
    let mut parsed_bones = Vec::new();
    let mut texture_width = 64.0;
    let mut texture_height = 64.0;
    let mut description_found = false;

    for geometry in model.geometry {
        if !description_found {
            texture_width = geometry.description.texture_width;
            texture_height = geometry.description.texture_height;
            description_found = true;
        }

        if let Some(bones) = geometry.bones {
            for bone in bones {
                let mut vertices: Vec<f32> = Vec::new();
                let mut uvs: Vec<f32> = Vec::new();
                let mut indices: Vec<u16> = Vec::new();
                let mut vertex_offset = 0;

                let bone_pivot = bone.pivot.clone().unwrap_or_else(|| vec![0.0, 0.0, 0.0]);

                if let Some(cubes) = &bone.cubes {
                    for cube in cubes {
                        add_cube_to_bone(
                            cube,
                            &bone_pivot,
                            texture_width,
                            texture_height,
                            &mut vertices,
                            &mut uvs,
                            &mut indices,
                            &mut vertex_offset,
                        );
                    }
                }

                let (final_vertices, final_uvs, final_indices) = if !vertices.is_empty() {
                    (
                        Some(Float32Array::new(vertices)),
                        Some(Float32Array::new(uvs)),
                        Some(Uint16Array::new(indices)),
                    )
                } else {
                    (None, None, None)
                };

                parsed_bones.push(ParsedBone {
                    name: bone.name,
                    parent: bone.parent,
                    pivot: bone_pivot,
                    rotation: bone.rotation,
                    vertices: final_vertices,
                    uvs: final_uvs,
                    indices: final_indices,
                });
            }
        }
    }

    Ok(ParsedModelData {
        texture_width,
        texture_height,
        bones: parsed_bones,
    })
}

fn add_cube_to_bone(
    cube: &Cube,
    bone_pivot: &[f64],
    texture_width: f64,
    texture_height: f64,
    vertices: &mut Vec<f32>,
    uvs: &mut Vec<f32>,
    indices: &mut Vec<u16>,
    vertex_offset: &mut u16,
) {
    let size = cube.size.clone().unwrap_or_else(|| vec![0.0, 0.0, 0.0]);
    let origin = cube.origin.clone().unwrap_or_else(|| vec![0.0, 0.0, 0.0]);
    let inflate = cube.inflate.unwrap_or(0.0);
    let mirror = cube.mirror.unwrap_or(false);

    // Box Geometry Dimensions (inflated)
    let w = size[0] + inflate * 2.0;
    let h = size[1] + inflate * 2.0;
    let d = size[2] + inflate * 2.0;

    // Three.js BoxGeometry Vertices (Standard Cube centered at 0,0,0)
    // 8 corners
    let x = w / 2.0;
    let y = h / 2.0;
    let z = d / 2.0;

    // Base positions relative to cube center
    // Standard BoxGeometry vertex order for faces:
    // +x (Right), -x (Left), +y (Top), -y (Bottom), +z (Front), -z (Back)
    // BUT we are building raw vertices for each face to support per-face UVs

    // Face definitions: Normal, 4 corners (relative to center)
    // Order: Right, Left, Top, Bottom, Front, Back
    // Three.js BoxGeometry uses:
    // 0: +x (Right)
    // 1: -x (Left)
    // 2: +y (Top)
    // 3: -y (Bottom)
    // 4: +z (Front)
    // 5: -z (Back)

    struct Face {
        corners: [[f64; 3]; 4], // TopLeft, TopRight, BottomLeft, BottomRight
        index: usize,
    }

    // Coordinates:
    // +x: Right, -x: Left
    // +y: Top, -y: Bottom
    // +z: Front, -z: Back

    // Vertices for each face (looking at the face)
    // 0: TopLeft, 1: TopRight, 2: BottomLeft, 3: BottomRight
    // Note: Three.js PlaneGeometry/BoxGeometry winding is Counter-Clockwise (CCW)
    // 0(TL) -> 2(BL) -> 1(TR) (Triangle 1)
    // 2(BL) -> 3(BR) -> 1(TR) (Triangle 2)

    let faces = [
        // 0: Right (+x)
        Face {
            corners: [
                [x, y, z],   // TL: +x, +y, +z
                [x, y, -z],  // TR: +x, +y, -z
                [x, -y, z],  // BL: +x, -y, +z
                [x, -y, -z], // BR: +x, -y, -z
            ],
            index: 0,
        },
        // 1: Left (-x)
        Face {
            corners: [
                [-x, y, -z],  // TL: -x, +y, -z
                [-x, y, z],   // TR: -x, +y, +z
                [-x, -y, -z], // BL: -x, -y, -z
                [-x, -y, z],  // BR: -x, -y, +z
            ],
            index: 1,
        },
        // 2: Top (+y)
        Face {
            corners: [
                [-x, y, -z], // TL: -x, +y, -z
                [x, y, -z],  // TR: +x, +y, -z
                [-x, y, z],  // BL: -x, +y, +z
                [x, y, z],   // BR: +x, +y, +z
            ],
            index: 2,
        },
        // 3: Bottom (-y)
        Face {
            corners: [
                [-x, -y, z],  // TL: -x, -y, +z
                [x, -y, z],   // TR: +x, -y, +z
                [-x, -y, -z], // BL: -x, -y, -z
                [x, -y, -z],  // BR: +x, -y, -z
            ],
            index: 3,
        },
        // 4: Front (+z)
        Face {
            corners: [
                [-x, y, z],  // TL: -x, +y, +z
                [x, y, z],   // TR: +x, +y, +z
                [-x, -y, z], // BL: -x, -y, +z
                [x, -y, z],  // BR: +x, -y, +z
            ],
            index: 4,
        },
        // 5: Back (-z)
        Face {
            corners: [
                [x, y, -z],   // TL: +x, +y, -z
                [-x, y, -z],  // TR: -x, +y, -z
                [x, -y, -z],  // BL: +x, -y, -z
                [-x, -y, -z], // BR: -x, -y, -z
            ],
            index: 5,
        },
    ];

    // Transformation Logic (Unified)
    // We treat all cubes as having a pivot (defaulting to bone pivot) and rotation (defaulting to 0)
    // This ensures consistent behavior with the TypeScript implementation

    let has_rotation = cube.rotation.is_some();
    let default_rot = vec![0.0, 0.0, 0.0];
    let cube_rotation = cube.rotation.as_ref().unwrap_or(&default_rot);

    // Pre-calculate rotation matrices
    // TS uses Euler order 'ZXY' with angles (-x, -y, z)
    let (sin_x, cos_x, sin_y, cos_y, sin_z, cos_z) = if has_rotation {
        (
            (-cube_rotation[0].to_radians()).sin(),
            (-cube_rotation[0].to_radians()).cos(),
            (-cube_rotation[1].to_radians()).sin(),
            (-cube_rotation[1].to_radians()).cos(),
            (cube_rotation[2].to_radians()).sin(),
            (cube_rotation[2].to_radians()).cos(),
        )
    } else {
        (0.0, 1.0, 0.0, 1.0, 0.0, 1.0)
    };

    // Calculate offsets
    // 1. Mesh Center in World Space (Absolute)
    let center_x = origin[0] + size[0] / 2.0;
    let center_y = origin[1] + size[1] / 2.0;
    let center_z = origin[2] + size[2] / 2.0;

    // 2. Determine Cube Pivot (Absolute)
    // If cube has no pivot, use bone pivot.
    let temp_bone_pivot = bone_pivot.to_vec();
    let cube_pivot = cube.pivot.as_ref().unwrap_or(&temp_bone_pivot);

    // 3. Vector from CubePivot to MeshCenter
    let off_x = center_x - cube_pivot[0];
    let off_y = center_y - cube_pivot[1];
    let off_z = center_z - cube_pivot[2];

    // 4. Group position (Pivot relative to Bone)
    // TS: pivotGroup.position.set(-(cp[0]-bp[0]), cp[1]-bp[1], cp[2]-bp[2])
    let group_pos_x = -(cube_pivot[0] - bone_pivot[0]);
    let group_pos_y = cube_pivot[1] - bone_pivot[1];
    let group_pos_z = cube_pivot[2] - bone_pivot[2];

    // 5. Effective Offset for the vector to be rotated
    // TS: mesh.position.x = -(center.x - cp.x)
    // So we want: -off_x
    let eff_offset_x = -off_x;
    let eff_offset_y = off_y;
    let eff_offset_z = off_z;

    for face in faces.iter() {
        // Calculate UVs for this face
        let (u0, v0, u1, v1) = calculate_face_uv(
            face.index,
            &cube.uv,
            &size,
            texture_width,
            texture_height,
            mirror,
        );

        // Add 4 vertices for this face
        for (i, corner) in face.corners.iter().enumerate() {
            // Start with corner relative to cube center (V_local)
            // Revert previous experimental fix: TS BoxGeometry is standard, so p_x should be corner[0].
            // The mirroring happens via eff_offset_x = -off_x.
            let p_x = corner[0];
            let p_y = corner[1];
            let p_z = corner[2];

            // Construct vector to be rotated (relative to Rotation Group Origin)
            let mut v_x = eff_offset_x + p_x;
            let mut v_y = eff_offset_y + p_y;
            let mut v_z = eff_offset_z + p_z;

            // Apply Cube Rotation
            // Three.js rotation.order = 'ZXY' means Matrix = Rz * Rx * Ry.
            // Applied to vector v: v' = Rz * (Rx * (Ry * v)).
            // So we must apply Y first, then X, then Z.
            if has_rotation {
                // 1. Rotate Y (first)
                let x = v_x;
                let z = v_z;
                v_x = x * cos_y + z * sin_y;
                v_z = -x * sin_y + z * cos_y;

                // 2. Rotate X
                let y = v_y;
                let z = v_z;
                v_y = y * cos_x - z * sin_x;
                v_z = y * sin_x + z * cos_x;

                // 3. Rotate Z (last)
                let x = v_x;
                let y = v_y;
                v_x = x * cos_z - y * sin_z;
                v_y = x * sin_z + y * cos_z;
            }

            // Calculate final position relative to Bone Pivot
            let final_x = group_pos_x + v_x; // group_pos_x is -(CP.x - BP.x)
            let final_y = group_pos_y + v_y;
            let final_z = group_pos_z + v_z;

            vertices.push(final_x as f32);
            vertices.push(final_y as f32);
            vertices.push(final_z as f32);

            // UVs
            match i {
                0 => {
                    uvs.push(u0 as f32);
                    uvs.push(v1 as f32);
                } // TL: 0, 1
                1 => {
                    uvs.push(u1 as f32);
                    uvs.push(v1 as f32);
                } // TR: 1, 1
                2 => {
                    uvs.push(u0 as f32);
                    uvs.push(v0 as f32);
                } // BL: 0, 0
                3 => {
                    uvs.push(u1 as f32);
                    uvs.push(v0 as f32);
                } // BR: 1, 0
                _ => {}
            }
        }

        // Indices (CCW)
        // 0(TL), 2(BL), 1(TR)
        // 2(BL), 3(BR), 1(TR)
        let base = *vertex_offset;
        indices.push(base + 0);
        indices.push(base + 2);
        indices.push(base + 1);
        indices.push(base + 2);
        indices.push(base + 3);
        indices.push(base + 1);

        *vertex_offset += 4;
    }
}

fn calculate_face_uv(
    face_index: usize,
    uv_data: &Option<Value>,
    size: &[f64],
    tex_w: f64,
    tex_h: f64,
    mirror: bool,
) -> (f64, f64, f64, f64) {
    let mut u = 0.0;
    let mut v = 0.0;
    let mut w = 0.0;
    let mut h = 0.0;

    if let Some(val) = uv_data {
        if val.is_array() {
            // Box UV
            let arr = val.as_array().unwrap();
            let origin_u = arr[0].as_f64().unwrap_or(0.0);
            let origin_v = arr[1].as_f64().unwrap_or(0.0);

            let size_x = size[0].ceil();
            let size_y = size[1].ceil();
            let size_z = size[2].ceil();

            // Mapping logic from TS applyBedrockUV
            match face_index {
                2 => {
                    // Top (+y)
                    u = origin_u + size_z;
                    v = origin_v;
                    w = size_x;
                    h = size_z;
                }
                3 => {
                    // Bottom (-y)
                    u = origin_u + size_z + size_x;
                    v = origin_v;
                    w = size_x;
                    h = size_z;
                }
                1 => {
                    // Left (-x) -> TS Face 1 (West)
                    u = origin_u;
                    v = origin_v + size_z;
                    w = size_z;
                    h = size_y;
                }
                5 => {
                    // Back (-z) -> TS Face 5 (North)
                    u = origin_u + size_z;
                    v = origin_v + size_z;
                    w = size_x;
                    h = size_y;
                }
                0 => {
                    // Right (+x) -> TS Face 0 (East)
                    u = origin_u + size_z + size_x;
                    v = origin_v + size_z;
                    w = size_z;
                    h = size_y;
                }
                4 => {
                    // Front (+z) -> TS Face 4 (South)
                    u = origin_u + size_z + size_x + size_z;
                    v = origin_v + size_z;
                    w = size_x;
                    h = size_y;
                }
                _ => {}
            }
        } else if val.is_object() {
            // Per-face UV
            let obj = val.as_object().unwrap();
            let map = match face_index {
                0 => "east",  // +x
                1 => "west",  // -x
                2 => "up",    // +y
                3 => "down",  // -y
                4 => "south", // +z
                5 => "north", // -z
                _ => "",
            };

            if let Some(face_data) = obj.get(map) {
                if let (Some(uv), Some(uv_size)) = (face_data.get("uv"), face_data.get("uv_size")) {
                    let uv_arr = uv.as_array().unwrap();
                    let size_arr = uv_size.as_array().unwrap();
                    u = uv_arr[0].as_f64().unwrap_or(0.0);
                    v = uv_arr[1].as_f64().unwrap_or(0.0);
                    w = size_arr[0].as_f64().unwrap_or(0.0);
                    h = size_arr[1].as_f64().unwrap_or(0.0);
                }
            }
        }
    }

    // Normalize
    let mut u0 = u / tex_w;
    let mut u1 = (u + w) / tex_w;

    // Invert V (Texture coordinates origin is top-left in Bedrock, bottom-left in GL)
    // TS: v0 = (H - v - h) / H, v1 = (H - v) / H
    // However, if u/v are 0, we might get incorrect results if not handled carefully
    // But float division is fine.

    // FIX: Standard UV mapping for Three.js usually expects:
    // (0,0) Bottom-Left, (1,1) Top-Right
    // Bedrock: (0,0) Top-Left
    // So v = 1.0 - (y / height)

    // v0 (bottom of face in texture) = v + h (higher pixel coordinate)
    // v1 (top of face in texture) = v (lower pixel coordinate)

    // In GL (0 at bottom):
    // v0_gl = 1.0 - (v + h) / tex_h
    // v1_gl = 1.0 - v / tex_h

    let v0 = 1.0 - (v + h) / tex_h;
    let v1 = 1.0 - v / tex_h;

    if mirror {
        (u1, v0, u0, v1) // Swap U
    } else {
        (u0, v0, u1, v1)
    }
}
