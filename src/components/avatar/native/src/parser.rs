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
    cubes: Option<Value>, // Keep as raw JSON value to be stringified
                          // other fields are ignored as they are not used for basic rendering structure
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
    /// Raw JSON string of cubes data.
    /// This allows the TS side to handle the actual geometry construction
    /// using its existing logic (AvatarRenderer.ts addCubeToBone).
    #[napi(js_name = "cubesJson")]
    pub cubes_json: Option<String>,
}

// --- Implementation ---

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
        // Use description from the first geometry that has one
        if !description_found {
            texture_width = geometry.description.texture_width;
            texture_height = geometry.description.texture_height;
            description_found = true;
        }

        if let Some(bones) = geometry.bones {
            for bone in bones {
                let cubes_json = if let Some(cubes) = &bone.cubes {
                    // Serialize the cubes array to a JSON string
                    match serde_json::to_string(cubes) {
                        Ok(s) => Some(s),
                        Err(_) => None, // Should not happen for valid Value
                    }
                } else {
                    None
                };

                parsed_bones.push(ParsedBone {
                    name: bone.name,
                    parent: bone.parent,
                    pivot: bone.pivot.unwrap_or_else(|| vec![0.0, 0.0, 0.0]),
                    rotation: bone.rotation,
                    cubes_json,
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
