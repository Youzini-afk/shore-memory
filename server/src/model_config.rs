use std::collections::{BTreeMap, HashSet};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use chrono::Utc;
use serde::{Deserialize, Serialize};

// Role-based LLM responsibility split.
//
// Each role is a distinct LLM use case (see ``worker/app/main.py``). Roles bind
// to named LLM presets; a role may either reference a specific preset id or
// leave the binding empty to inherit the currently-active default preset.
pub const ROLE_SCORER: &str = "scorer";
pub const ROLE_REFLECTOR: &str = "reflector";
pub const ROLE_QUERY_ANALYZER: &str = "query_analyzer";
pub const ROLE_QUERY_PLANNER: &str = "query_planner";

pub const KNOWN_ROLES: &[&str] = &[
    ROLE_SCORER,
    ROLE_REFLECTOR,
    ROLE_QUERY_ANALYZER,
    ROLE_QUERY_PLANNER,
];

pub fn default_role_temperature(role: &str) -> f32 {
    match role {
        ROLE_SCORER => 0.3,
        ROLE_REFLECTOR => 0.4,
        ROLE_QUERY_ANALYZER => 0.1,
        ROLE_QUERY_PLANNER => 0.1,
        _ => 0.3,
    }
}

fn is_known_role(role: &str) -> bool {
    KNOWN_ROLES.iter().any(|candidate| *candidate == role)
}

// ============================================================================
// Provider / preset kinds
// ============================================================================

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ProviderKind {
    Embedding,
    Llm,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PresetKind {
    Embedding,
    Llm,
}

impl From<PresetKind> for ProviderKind {
    fn from(kind: PresetKind) -> Self {
        match kind {
            PresetKind::Embedding => ProviderKind::Embedding,
            PresetKind::Llm => ProviderKind::Llm,
        }
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SecretMode {
    Inherit,
    Clear,
    Set,
}

impl Default for SecretMode {
    fn default() -> Self {
        Self::Inherit
    }
}

// ============================================================================
// Persistent storage shape
// ============================================================================

/// A named, self-contained provider configuration. Multiple presets can coexist
/// in a pool (embedding / LLM). For LLM, roles bind to a preset (or follow the
/// pool default); the embedding pool always uses its default preset to serve
/// the active embedding config for the rest of the system.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ModelPresetFile {
    pub id: String,
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub api_base: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    /// Embedding-only: vector dimension for this provider/model.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dimension: Option<usize>,
    /// LLM-only: suggested default temperature for this preset.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
}

/// Per-role binding to an LLM preset. ``preset_id = None`` means "follow the
/// currently-active default LLM preset"; ``temperature = None`` falls back to
/// the preset's temperature, and then to the role's built-in default.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct RoleBindingFile {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub preset_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    /// Optional per-role generation parameter overrides (top_p, max_tokens,
    /// penalties, seed). Fields left as ``None`` fall back to the provider /
    /// worker default (i.e. nothing is sent on the wire).
    #[serde(default, skip_serializing_if = "RoleGenerationParamsFile::is_empty")]
    pub generation_params: RoleGenerationParamsFile,
}

/// Per-role optional generation parameters. Any field set to ``Some`` is sent
/// on the wire to the upstream LLM; ``None`` means "do not override".
#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
pub struct RoleGenerationParamsFile {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub top_p: Option<f32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_tokens: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub frequency_penalty: Option<f32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub presence_penalty: Option<f32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub seed: Option<i64>,
}

impl RoleGenerationParamsFile {
    pub fn is_empty(&self) -> bool {
        self.top_p.is_none()
            && self.max_tokens.is_none()
            && self.frequency_penalty.is_none()
            && self.presence_penalty.is_none()
            && self.seed.is_none()
    }
}

/// On-disk representation of ``model-config.json``.
///
/// The authoritative data lives in the preset pools and role bindings. The
/// server *also* writes a fully-resolved snapshot under the legacy
/// ``embedding`` / ``llm`` / ``roles`` keys on every save so the Python worker
/// (which still reads those keys directly) keeps working without a schema
/// migration on its side. Older files that pre-date the preset redesign only
/// populate the legacy fields; those are migrated in-memory on first read and
/// rewritten in the new shape on first save.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ModelConfigFile {
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub embedding_presets: Vec<ModelPresetFile>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub llm_presets: Vec<ModelPresetFile>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub default_embedding_preset: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub default_llm_preset: Option<String>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub role_bindings: BTreeMap<String, RoleBindingFile>,
    /// Per-role system prompt overrides. An absent or empty entry means the
    /// role should use the worker's built-in default prompt. The worker reads
    /// this map directly via the ``prompts`` key.
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub prompts: BTreeMap<String, String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub updated_at: Option<String>,

    // --- Legacy / worker snapshot --------------------------------------------
    // Written by the server on every save as the fully-resolved snapshot the
    // worker already knows how to read. Also consumed on first read as the
    // input of the legacy-to-preset migration.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub embedding: Option<ProviderOverrideFile>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub llm: Option<ProviderOverrideFile>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub roles: BTreeMap<String, ProviderOverrideFile>,
}

/// Legacy per-provider override / snapshot shape. Kept for backwards
/// compatibility with older config files and as the worker-facing snapshot.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ProviderOverrideFile {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub api_base: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dimension: Option<usize>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(default)]
    pub api_key_mode: SecretMode,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
    // --- Role-only generation params (skipped for embedding/llm) ---------
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub top_p: Option<f32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_tokens: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub frequency_penalty: Option<f32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub presence_penalty: Option<f32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub seed: Option<i64>,
}

// ============================================================================
// Request shapes
// ============================================================================

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct UpdateModelConfigRequest {
    #[serde(default)]
    pub embedding_presets: Vec<UpdatePresetRequest>,
    #[serde(default)]
    pub llm_presets: Vec<UpdatePresetRequest>,
    #[serde(default)]
    pub default_embedding_preset: Option<String>,
    #[serde(default)]
    pub default_llm_preset: Option<String>,
    #[serde(default)]
    pub role_bindings: BTreeMap<String, UpdateRoleBindingRequest>,
    /// Per-role system prompt overrides. ``Some("")`` / whitespace-only / ``None``
    /// all clear the override so the worker falls back to its built-in default.
    #[serde(default)]
    pub prompts: BTreeMap<String, Option<String>>,
    #[serde(default)]
    pub auto_detect_embedding_dimension: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdatePresetRequest {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub api_base: Option<String>,
    #[serde(default)]
    pub model: Option<String>,
    #[serde(default)]
    pub dimension: Option<usize>,
    #[serde(default)]
    pub temperature: Option<f32>,
    /// New api key to persist. Ignored when ``clear_api_key`` or
    /// ``api_key_unchanged`` is set.
    #[serde(default)]
    pub api_key: Option<String>,
    /// Explicitly drop the stored api key.
    #[serde(default)]
    pub clear_api_key: bool,
    /// Tell the server to preserve the previously stored api key.
    #[serde(default)]
    pub api_key_unchanged: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct UpdateRoleBindingRequest {
    /// When ``None``, the role follows the currently-active default LLM preset.
    #[serde(default)]
    pub preset_id: Option<String>,
    /// Per-role temperature override. When ``None`` the preset's temperature
    /// (or the role's built-in default) is used.
    #[serde(default)]
    pub temperature: Option<f32>,
    /// Per-role optional generation parameter overrides.
    #[serde(default)]
    pub generation_params: RoleGenerationParamsFile,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListProviderModelsRequest {
    pub provider: ProviderKind,
    pub api_base: String,
    /// Pick up stored credentials from the referenced preset.
    #[serde(default)]
    pub preset_id: Option<String>,
    /// Legacy: when no ``preset_id`` is provided and ``provider`` is LLM,
    /// a role identifier selects the preset that role currently resolves to.
    #[serde(default)]
    pub role: Option<String>,
    #[serde(default)]
    pub api_key: Option<String>,
    #[serde(default)]
    pub clear_api_key: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetectEmbeddingDimensionRequest {
    pub api_base: String,
    pub model: String,
    #[serde(default)]
    pub preset_id: Option<String>,
    #[serde(default)]
    pub api_key: Option<String>,
    #[serde(default)]
    pub clear_api_key: bool,
}

// ============================================================================
// Response shapes
// ============================================================================

#[derive(Debug, Clone, Serialize)]
pub struct ModelConfigResponse {
    pub embedding: ProviderConfigResponse,
    pub llm: ProviderConfigResponse,
    pub roles: BTreeMap<String, ProviderConfigResponse>,
    pub embedding_presets: Vec<ModelPresetResponse>,
    pub llm_presets: Vec<ModelPresetResponse>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_embedding_preset: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_llm_preset: Option<String>,
    pub role_bindings: BTreeMap<String, RoleBindingResponse>,
    /// Currently-active per-role prompt overrides. Only roles with a non-empty
    /// override appear here; anything else falls back to the worker default.
    pub prompts: BTreeMap<String, String>,
    pub storage: ModelConfigStorageResponse,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelPresetResponse {
    pub id: String,
    pub name: String,
    pub kind: PresetKind,
    pub api_base: String,
    pub model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dimension: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    pub configured: bool,
    pub api_key_configured: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key_masked: Option<String>,
    pub source: String,
    pub api_key_source: String,
    pub is_default: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct RoleBindingResponse {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub preset_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub effective_preset_id: Option<String>,
    pub follows_default: bool,
    pub resolved: ProviderConfigResponse,
    /// Per-role generation parameter overrides exactly as persisted on disk.
    /// Missing fields fall back to the upstream LLM provider's defaults.
    #[serde(default)]
    pub generation_params: RoleGenerationParamsFile,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelConfigTestResponse {
    pub embedding: ProviderTestResponse,
    pub llm: ProviderTestResponse,
    pub roles: BTreeMap<String, ProviderTestResponse>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProviderTestResponse {
    pub ok: bool,
    pub configured: bool,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dimension: Option<usize>,
    pub source: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct UpdateModelConfigResponse {
    pub config: ModelConfigResponse,
    pub embedding_changed: bool,
    pub embedding_dimension_changed: bool,
    pub embedding_cache_cleared: bool,
    pub memory_embeddings_refreshed: usize,
    pub reindexed_memories: usize,
    pub reindexed_entities: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelConfigStorageResponse {
    pub path: String,
    pub override_active: bool,
    pub updated_at: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProviderConfigResponse {
    pub api_base: String,
    pub model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dimension: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    pub configured: bool,
    pub api_key_configured: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key_masked: Option<String>,
    pub source: String,
    pub api_key_source: String,
    pub override_active: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ListProviderModelsResponse {
    pub provider: ProviderKind,
    pub models: Vec<String>,
    pub count: usize,
    pub source: String,
    pub api_key_source: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct DetectEmbeddingDimensionResponse {
    pub model: String,
    pub dimension: usize,
    pub source: String,
    pub api_key_source: String,
}

#[derive(Debug, Clone)]
pub struct ResolvedProviderProbe {
    pub api_base: String,
    pub model: String,
    pub api_key: Option<String>,
    pub source: String,
    pub api_key_source: String,
}

// ============================================================================
// Runtime shape
// ============================================================================

#[derive(Debug, Clone, PartialEq)]
pub struct RuntimeModelConfig {
    pub embedding: RuntimeProviderConfig,
    pub llm: RuntimeProviderConfig,
    pub roles: BTreeMap<String, RuntimeProviderConfig>,
    pub embedding_presets: Vec<RuntimePreset>,
    pub llm_presets: Vec<RuntimePreset>,
    pub default_embedding_preset: Option<String>,
    pub default_llm_preset: Option<String>,
    pub role_bindings: BTreeMap<String, RuntimeRoleBinding>,
    pub prompts: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RuntimePreset {
    pub id: String,
    pub name: String,
    pub kind: PresetKind,
    pub provider: RuntimeProviderConfig,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RuntimeRoleBinding {
    pub preset_id: Option<String>,
    pub temperature: Option<f32>,
    pub effective_preset_id: Option<String>,
    pub generation_params: RoleGenerationParamsFile,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RuntimeProviderConfig {
    pub api_base: String,
    pub model: String,
    pub dimension: Option<usize>,
    pub temperature: Option<f32>,
    pub api_key: Option<String>,
    pub source: String,
    pub api_key_source: String,
    pub override_active: bool,
}

impl RuntimeProviderConfig {
    pub fn configured(&self) -> bool {
        self.api_key
            .as_ref()
            .is_some_and(|value| !value.trim().is_empty())
            && !self.model.trim().is_empty()
            && self.dimension.unwrap_or(1) > 0
    }
}

impl RuntimeModelConfig {
    pub fn to_response(&self, path: &Path, file: Option<&ModelConfigFile>) -> ModelConfigResponse {
        let embedding_presets = self
            .embedding_presets
            .iter()
            .map(|preset| preset_to_response(preset, self.default_embedding_preset.as_deref()))
            .collect();
        let llm_presets = self
            .llm_presets
            .iter()
            .map(|preset| preset_to_response(preset, self.default_llm_preset.as_deref()))
            .collect();

        let role_bindings = self
            .role_bindings
            .iter()
            .map(|(role, binding)| {
                let resolved = self
                    .roles
                    .get(role)
                    .cloned()
                    .unwrap_or_else(|| self.llm.clone());
                (
                    role.clone(),
                    RoleBindingResponse {
                        preset_id: binding.preset_id.clone(),
                        temperature: binding.temperature,
                        effective_preset_id: binding.effective_preset_id.clone(),
                        follows_default: binding.preset_id.is_none(),
                        resolved: provider_to_response(&resolved),
                        generation_params: binding.generation_params.clone(),
                    },
                )
            })
            .collect();

        ModelConfigResponse {
            embedding: provider_to_response(&self.embedding),
            llm: provider_to_response(&self.llm),
            roles: self
                .roles
                .iter()
                .map(|(role, provider)| (role.clone(), provider_to_response(provider)))
                .collect(),
            embedding_presets,
            llm_presets,
            default_embedding_preset: self.default_embedding_preset.clone(),
            default_llm_preset: self.default_llm_preset.clone(),
            role_bindings,
            prompts: self.prompts.clone(),
            storage: ModelConfigStorageResponse {
                path: path.display().to_string(),
                override_active: file.is_some(),
                updated_at: file.and_then(|value| value.updated_at.clone()),
            },
        }
    }
}

// ============================================================================
// File IO
// ============================================================================

pub fn model_config_path(data_dir: &Path) -> PathBuf {
    data_dir.join("model-config.json")
}

pub fn read_model_config_file(path: &Path) -> Result<Option<ModelConfigFile>> {
    if !path.exists() {
        return Ok(None);
    }
    let raw = fs::read_to_string(path)
        .with_context(|| format!("failed to read model config file: {}", path.display()))?;
    let parsed = serde_json::from_str::<ModelConfigFile>(&raw)
        .with_context(|| format!("failed to parse model config file: {}", path.display()))?;
    Ok(Some(migrate_legacy_in_memory(parsed)))
}

pub fn write_model_config_file(path: &Path, config: &ModelConfigFile) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("failed to create model config dir: {}", parent.display()))?;
    }
    let raw = serde_json::to_string_pretty(config)?;
    fs::write(path, raw)
        .with_context(|| format!("failed to write model config file: {}", path.display()))?;
    Ok(())
}

pub fn delete_model_config_file(path: &Path) -> Result<()> {
    if path.exists() {
        fs::remove_file(path)
            .with_context(|| format!("failed to remove model config file: {}", path.display()))?;
    }
    Ok(())
}

pub fn load_runtime_model_config(
    path: &Path,
) -> Result<(RuntimeModelConfig, Option<ModelConfigFile>)> {
    let file = read_model_config_file(path)?;
    let runtime = resolve_runtime_model_config(file.as_ref());
    Ok((runtime, file))
}

pub fn embedding_dim_from_env_or_file(path: &Path) -> Result<usize> {
    let (runtime, _) = load_runtime_model_config(path)?;
    Ok(runtime.embedding.dimension.unwrap_or(1536).max(1))
}

// ============================================================================
// Legacy migration
// ============================================================================

/// Migrate a parsed ``ModelConfigFile`` whose only populated fields are the
/// legacy flat shape (``embedding`` / ``llm`` / ``roles``) into the preset
/// pool shape. Files that already expose presets are returned as-is.
pub fn migrate_legacy_in_memory(mut file: ModelConfigFile) -> ModelConfigFile {
    if !file.embedding_presets.is_empty() || !file.llm_presets.is_empty() {
        return file;
    }

    let legacy_embedding = file.embedding.take().unwrap_or_default();
    let legacy_llm = file.llm.take().unwrap_or_default();
    let legacy_roles = std::mem::take(&mut file.roles);

    let embedding_preset = ModelPresetFile {
        id: "embedding-default".to_string(),
        name: "默认".to_string(),
        api_base: legacy_embedding.api_base,
        model: legacy_embedding.model,
        dimension: legacy_embedding.dimension,
        temperature: None,
        api_key: legacy_embedding.api_key,
    };

    let llm_default = ModelPresetFile {
        id: "llm-default".to_string(),
        name: "默认".to_string(),
        api_base: legacy_llm.api_base,
        model: legacy_llm.model,
        dimension: None,
        temperature: legacy_llm.temperature,
        api_key: legacy_llm.api_key,
    };

    let mut llm_presets = vec![llm_default];
    let mut role_bindings: BTreeMap<String, RoleBindingFile> = BTreeMap::new();

    for (role, legacy_role) in legacy_roles {
        if !is_known_role(&role) {
            continue;
        }
        let has_provider_override = legacy_role.api_base.is_some()
            || legacy_role.model.is_some()
            || legacy_role.api_key.is_some();

        if has_provider_override {
            let preset_id = format!("llm-role-{role}");
            llm_presets.push(ModelPresetFile {
                id: preset_id.clone(),
                name: format!("{role} 旧定制"),
                api_base: legacy_role.api_base,
                model: legacy_role.model,
                dimension: None,
                temperature: None,
                api_key: legacy_role.api_key,
            });
            role_bindings.insert(
                role,
                RoleBindingFile {
                    preset_id: Some(preset_id),
                    temperature: legacy_role.temperature,
                    generation_params: RoleGenerationParamsFile::default(),
                },
            );
        } else if legacy_role.temperature.is_some() {
            role_bindings.insert(
                role,
                RoleBindingFile {
                    preset_id: None,
                    temperature: legacy_role.temperature,
                    generation_params: RoleGenerationParamsFile::default(),
                },
            );
        }
    }

    file.embedding_presets = vec![embedding_preset];
    file.llm_presets = llm_presets;
    file.default_embedding_preset = Some("embedding-default".to_string());
    file.default_llm_preset = Some("llm-default".to_string());
    file.role_bindings = role_bindings;
    file
}

// ============================================================================
// Runtime resolution
// ============================================================================

pub fn resolve_runtime_model_config(file: Option<&ModelConfigFile>) -> RuntimeModelConfig {
    let migrated_owned;
    let file_ref: Option<&ModelConfigFile> = match file {
        Some(f) if f.embedding_presets.is_empty() && f.llm_presets.is_empty() => {
            migrated_owned = Some(migrate_legacy_in_memory(f.clone()));
            migrated_owned.as_ref()
        }
        Some(f) => {
            migrated_owned = None;
            let _ = &migrated_owned;
            Some(f)
        }
        None => {
            migrated_owned = None;
            let _ = &migrated_owned;
            None
        }
    };

    let embedding_env = EnvProviderConfig::embedding();
    let llm_env = EnvProviderConfig::llm();

    let embedding_presets: Vec<RuntimePreset> = match file_ref {
        Some(f) => f
            .embedding_presets
            .iter()
            .map(|preset| RuntimePreset {
                id: preset.id.clone(),
                name: preset.name.clone(),
                kind: PresetKind::Embedding,
                provider: resolve_preset_as_provider(
                    PresetKind::Embedding,
                    Some(preset),
                    &embedding_env,
                ),
            })
            .collect(),
        None => vec![RuntimePreset {
            id: "embedding-default".to_string(),
            name: "默认".to_string(),
            kind: PresetKind::Embedding,
            provider: resolve_preset_as_provider(PresetKind::Embedding, None, &embedding_env),
        }],
    };

    let llm_presets: Vec<RuntimePreset> = match file_ref {
        Some(f) => f
            .llm_presets
            .iter()
            .map(|preset| RuntimePreset {
                id: preset.id.clone(),
                name: preset.name.clone(),
                kind: PresetKind::Llm,
                provider: resolve_preset_as_provider(PresetKind::Llm, Some(preset), &llm_env),
            })
            .collect(),
        None => vec![RuntimePreset {
            id: "llm-default".to_string(),
            name: "默认".to_string(),
            kind: PresetKind::Llm,
            provider: resolve_preset_as_provider(PresetKind::Llm, None, &llm_env),
        }],
    };

    let default_embedding = file_ref
        .and_then(|f| f.default_embedding_preset.clone())
        .filter(|id| embedding_presets.iter().any(|p| &p.id == id))
        .or_else(|| embedding_presets.first().map(|p| p.id.clone()));
    let default_llm = file_ref
        .and_then(|f| f.default_llm_preset.clone())
        .filter(|id| llm_presets.iter().any(|p| &p.id == id))
        .or_else(|| llm_presets.first().map(|p| p.id.clone()));

    let embedding = default_embedding
        .as_ref()
        .and_then(|id| embedding_presets.iter().find(|p| &p.id == id))
        .or_else(|| embedding_presets.first())
        .map(|p| p.provider.clone())
        .unwrap_or_else(|| resolve_preset_as_provider(PresetKind::Embedding, None, &embedding_env));

    let llm = default_llm
        .as_ref()
        .and_then(|id| llm_presets.iter().find(|p| &p.id == id))
        .or_else(|| llm_presets.first())
        .map(|p| p.provider.clone())
        .unwrap_or_else(|| resolve_preset_as_provider(PresetKind::Llm, None, &llm_env));

    let mut roles = BTreeMap::new();
    let mut role_bindings_runtime: BTreeMap<String, RuntimeRoleBinding> = BTreeMap::new();

    for role in KNOWN_ROLES {
        let binding_file = file_ref
            .and_then(|f| f.role_bindings.get(*role))
            .cloned()
            .unwrap_or_default();

        let target_preset_id = binding_file
            .preset_id
            .clone()
            .filter(|id| llm_presets.iter().any(|p| &p.id == id))
            .or_else(|| default_llm.clone());

        let base_provider = target_preset_id
            .as_ref()
            .and_then(|id| llm_presets.iter().find(|p| &p.id == id))
            .map(|p| p.provider.clone())
            .unwrap_or_else(|| llm.clone());

        let temperature = binding_file
            .temperature
            .or(base_provider.temperature)
            .or(Some(default_role_temperature(role)));

        let mut role_provider = base_provider;
        role_provider.temperature = temperature;
        role_provider.dimension = None;

        roles.insert((*role).to_string(), role_provider);
        role_bindings_runtime.insert(
            (*role).to_string(),
            RuntimeRoleBinding {
                preset_id: binding_file.preset_id.clone(),
                temperature: binding_file.temperature,
                effective_preset_id: target_preset_id,
                generation_params: binding_file.generation_params.clone(),
            },
        );
    }

    let prompts = file_ref
        .map(|f| {
            f.prompts
                .iter()
                .filter_map(|(role, value)| {
                    if !is_known_role(role) {
                        return None;
                    }
                    let trimmed = value.trim();
                    if trimmed.is_empty() {
                        None
                    } else {
                        Some((role.clone(), value.clone()))
                    }
                })
                .collect::<BTreeMap<_, _>>()
        })
        .unwrap_or_default();

    RuntimeModelConfig {
        embedding,
        llm,
        roles,
        embedding_presets,
        llm_presets,
        default_embedding_preset: default_embedding,
        default_llm_preset: default_llm,
        role_bindings: role_bindings_runtime,
        prompts,
    }
}

fn resolve_preset_as_provider(
    kind: PresetKind,
    preset: Option<&ModelPresetFile>,
    env: &EnvProviderConfig,
) -> RuntimeProviderConfig {
    let include_dimension = matches!(kind, PresetKind::Embedding);
    let include_temperature = matches!(kind, PresetKind::Llm);

    let api_base = preset
        .and_then(|p| normalize_optional_string(p.api_base.as_deref()))
        .unwrap_or_else(|| env.api_base.clone());
    let model = preset
        .and_then(|p| normalize_optional_string(p.model.as_deref()))
        .unwrap_or_else(|| env.model.clone());
    let dimension = if include_dimension {
        preset
            .and_then(|p| p.dimension)
            .or(env.dimension)
            .map(|v| v.max(1))
    } else {
        None
    };
    let temperature = if include_temperature {
        preset.and_then(|p| p.temperature).or(env.temperature)
    } else {
        None
    };

    let api_key_from_preset = preset
        .and_then(|p| p.api_key.as_ref())
        .map(|value| value.trim())
        .filter(|v| !v.is_empty())
        .map(ToOwned::to_owned);

    let (api_key, api_key_source) = match api_key_from_preset {
        Some(key) => (Some(key), "file".to_string()),
        None => match env.api_key.clone() {
            Some(key) => (Some(key), "env".to_string()),
            None => (None, "unset".to_string()),
        },
    };

    let file_fields = preset
        .map(|p| {
            usize::from(p.api_base.is_some())
                + usize::from(p.model.is_some())
                + usize::from(include_dimension && p.dimension.is_some())
                + usize::from(include_temperature && p.temperature.is_some())
                + usize::from(p.api_key.is_some())
        })
        .unwrap_or(0);
    let total_fields = 2 + usize::from(include_dimension) + usize::from(include_temperature) + 1; // api_key
    let override_active = file_fields > 0;
    let source = if file_fields == 0 {
        "env".to_string()
    } else if file_fields >= total_fields {
        "file".to_string()
    } else {
        "mixed".to_string()
    };

    RuntimeProviderConfig {
        api_base,
        model,
        dimension,
        temperature,
        api_key,
        source,
        api_key_source,
        override_active,
    }
}

// ============================================================================
// Update pipeline
// ============================================================================

pub fn apply_update(
    existing: Option<ModelConfigFile>,
    request: UpdateModelConfigRequest,
) -> Result<ModelConfigFile> {
    let previous = existing.map(migrate_legacy_in_memory).unwrap_or_default();

    let embedding_presets = merge_presets(
        PresetKind::Embedding,
        request.embedding_presets,
        &previous.embedding_presets,
    )?;
    let llm_presets = merge_presets(PresetKind::Llm, request.llm_presets, &previous.llm_presets)?;

    if embedding_presets.is_empty() {
        bail!("at least one embedding preset is required");
    }
    if llm_presets.is_empty() {
        bail!("at least one llm preset is required");
    }

    let default_embedding = match request
        .default_embedding_preset
        .as_deref()
        .map(str::trim)
        .filter(|v| !v.is_empty())
    {
        Some(id) => {
            if !embedding_presets.iter().any(|p| p.id == id) {
                bail!("default_embedding_preset refers to unknown preset: {id}");
            }
            Some(id.to_string())
        }
        None => Some(embedding_presets[0].id.clone()),
    };

    let default_llm = match request
        .default_llm_preset
        .as_deref()
        .map(str::trim)
        .filter(|v| !v.is_empty())
    {
        Some(id) => {
            if !llm_presets.iter().any(|p| p.id == id) {
                bail!("default_llm_preset refers to unknown preset: {id}");
            }
            Some(id.to_string())
        }
        None => Some(llm_presets[0].id.clone()),
    };

    let mut role_bindings = BTreeMap::new();
    for (role, binding) in request.role_bindings {
        if !is_known_role(&role) {
            bail!("unknown role: {role}");
        }
        let preset_id = match binding.preset_id.as_deref().map(str::trim) {
            Some(id) if !id.is_empty() => {
                if !llm_presets.iter().any(|p| p.id == id) {
                    bail!("role {role} binds to unknown preset: {id}");
                }
                Some(id.to_string())
            }
            _ => None,
        };
        let generation_params = normalize_generation_params(binding.generation_params)?;
        role_bindings.insert(
            role,
            RoleBindingFile {
                preset_id,
                temperature: normalize_temperature(binding.temperature)?,
                generation_params,
            },
        );
    }

    let mut prompts = BTreeMap::new();
    for (role, raw) in request.prompts {
        if !is_known_role(&role) {
            bail!("unknown role in prompts: {role}");
        }
        if let Some(value) = raw {
            let trimmed = value.trim();
            if !trimmed.is_empty() {
                prompts.insert(role, value);
            }
        }
        // None or empty/whitespace-only → drop so worker falls back to default
    }

    let mut next = ModelConfigFile {
        embedding_presets,
        llm_presets,
        default_embedding_preset: default_embedding,
        default_llm_preset: default_llm,
        role_bindings,
        prompts,
        updated_at: Some(Utc::now().to_rfc3339()),
        embedding: None,
        llm: None,
        roles: BTreeMap::new(),
    };

    populate_worker_snapshot(&mut next);
    Ok(next)
}

fn merge_presets(
    kind: PresetKind,
    updates: Vec<UpdatePresetRequest>,
    previous: &[ModelPresetFile],
) -> Result<Vec<ModelPresetFile>> {
    let mut seen_ids: HashSet<String> = HashSet::new();
    let mut out = Vec::with_capacity(updates.len());
    for update in updates {
        let id = update.id.trim();
        if id.is_empty() {
            bail!("preset id is required");
        }
        if !seen_ids.insert(id.to_string()) {
            bail!("duplicate preset id: {id}");
        }
        let name = update.name.trim();
        if name.is_empty() {
            bail!("preset name is required");
        }
        let previous_entry = previous.iter().find(|p| p.id == id);
        let api_key = if update.clear_api_key {
            None
        } else if update.api_key_unchanged {
            previous_entry.and_then(|p| p.api_key.clone())
        } else {
            normalize_optional_string(update.api_key.as_deref())
                .or_else(|| previous_entry.and_then(|p| p.api_key.clone()))
        };

        let (dimension, temperature) = match kind {
            PresetKind::Embedding => (update.dimension.filter(|&d| d > 0), None),
            PresetKind::Llm => (None, normalize_temperature(update.temperature)?),
        };

        out.push(ModelPresetFile {
            id: id.to_string(),
            name: name.to_string(),
            api_base: normalize_optional_string(update.api_base.as_deref()),
            model: normalize_optional_string(update.model.as_deref()),
            dimension,
            temperature,
            api_key,
        });
    }
    Ok(out)
}

/// Rebuild the worker-facing snapshot inside ``file``. Call this after any
/// mutation of the preset pools or role bindings so the legacy keys the worker
/// reads stay in sync with the authoritative preset data.
pub fn refresh_worker_snapshot(file: &mut ModelConfigFile) {
    populate_worker_snapshot(file);
}

fn populate_worker_snapshot(file: &mut ModelConfigFile) {
    let runtime = resolve_runtime_model_config(Some(file));
    file.embedding = Some(runtime_to_legacy_file(&runtime.embedding, true));
    file.llm = Some(runtime_to_legacy_file(&runtime.llm, false));
    file.roles = runtime
        .roles
        .iter()
        .map(|(role, provider)| {
            let binding = runtime.role_bindings.get(role);
            (
                role.clone(),
                runtime_role_to_legacy_file(provider, binding),
            )
        })
        .collect();
}

fn runtime_to_legacy_file(
    provider: &RuntimeProviderConfig,
    is_embedding: bool,
) -> ProviderOverrideFile {
    ProviderOverrideFile {
        api_base: Some(provider.api_base.clone()),
        model: Some(provider.model.clone()),
        dimension: if is_embedding {
            provider.dimension
        } else {
            None
        },
        temperature: if is_embedding {
            None
        } else {
            provider.temperature
        },
        api_key_mode: if provider.api_key.is_some() {
            SecretMode::Set
        } else {
            SecretMode::Clear
        },
        api_key: provider.api_key.clone(),
        top_p: None,
        max_tokens: None,
        frequency_penalty: None,
        presence_penalty: None,
        seed: None,
    }
}

/// Role-aware version of :func:`runtime_to_legacy_file` that additionally
/// persists the per-role generation parameter overrides so the worker can
/// read them directly from the resolved snapshot.
fn runtime_role_to_legacy_file(
    provider: &RuntimeProviderConfig,
    binding: Option<&RuntimeRoleBinding>,
) -> ProviderOverrideFile {
    let mut out = runtime_to_legacy_file(provider, false);
    if let Some(binding) = binding {
        out.top_p = binding.generation_params.top_p;
        out.max_tokens = binding.generation_params.max_tokens;
        out.frequency_penalty = binding.generation_params.frequency_penalty;
        out.presence_penalty = binding.generation_params.presence_penalty;
        out.seed = binding.generation_params.seed;
    }
    out
}

// ============================================================================
// Probe helpers (used by /v1/model-config/models + /embedding/dimension)
// ============================================================================

pub fn resolve_provider_probe(
    current: &RuntimeProviderConfig,
    api_base: &str,
    model: Option<&str>,
    api_key: Option<&str>,
    clear_api_key: bool,
) -> ResolvedProviderProbe {
    let api_base_override = api_base.trim();
    let model_override = model.map(str::trim).filter(|value| !value.is_empty());
    let api_key_override = api_key.map(str::trim).filter(|value| !value.is_empty());

    let resolved_api_base = if api_base_override.is_empty() {
        current.api_base.clone()
    } else {
        api_base_override.to_string()
    };
    let resolved_model = model_override
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| current.model.clone());
    let (resolved_api_key, api_key_source) = if clear_api_key {
        (None, "cleared".to_string())
    } else if let Some(api_key) = api_key_override {
        (Some(api_key.to_string()), "request".to_string())
    } else {
        (current.api_key.clone(), current.api_key_source.clone())
    };
    let source = if !api_base_override.is_empty() || model_override.is_some() {
        "request".to_string()
    } else {
        current.source.clone()
    };

    ResolvedProviderProbe {
        api_base: resolved_api_base,
        model: resolved_model,
        api_key: resolved_api_key,
        source,
        api_key_source,
    }
}

// ============================================================================
// Env defaults
// ============================================================================

#[derive(Debug, Clone)]
pub(crate) struct EnvProviderConfig {
    pub api_base: String,
    pub model: String,
    pub dimension: Option<usize>,
    pub temperature: Option<f32>,
    pub api_key: Option<String>,
}

impl EnvProviderConfig {
    pub(crate) fn embedding() -> Self {
        Self {
            api_base: env_string("PMW_EMBEDDING_API_BASE", "https://api.openai.com/v1"),
            model: env_string("PMW_EMBEDDING_MODEL", ""),
            dimension: Some(env_usize_multi(
                &["PMS_EMBEDDING_DIM", "PMW_EMBEDDING_DIM"],
                1536,
            )),
            temperature: None,
            api_key: env_optional_string("PMW_EMBEDDING_API_KEY"),
        }
    }

    pub(crate) fn llm() -> Self {
        Self {
            api_base: env_string("PMW_LLM_API_BASE", "https://api.openai.com/v1"),
            model: env_string("PMW_LLM_MODEL", ""),
            dimension: None,
            temperature: None,
            api_key: env_optional_string("PMW_LLM_API_KEY"),
        }
    }
}

// ============================================================================
// Response builders
// ============================================================================

fn provider_to_response(provider: &RuntimeProviderConfig) -> ProviderConfigResponse {
    ProviderConfigResponse {
        api_base: provider.api_base.clone(),
        model: provider.model.clone(),
        dimension: provider.dimension,
        temperature: provider.temperature,
        configured: provider.configured(),
        api_key_configured: provider
            .api_key
            .as_ref()
            .is_some_and(|value| !value.trim().is_empty()),
        api_key_masked: provider.api_key.as_deref().map(mask_secret),
        source: provider.source.clone(),
        api_key_source: provider.api_key_source.clone(),
        override_active: provider.override_active,
    }
}

fn preset_to_response(preset: &RuntimePreset, default_id: Option<&str>) -> ModelPresetResponse {
    let RuntimeProviderConfig {
        api_base,
        model,
        dimension,
        temperature,
        api_key,
        source,
        api_key_source,
        ..
    } = &preset.provider;

    ModelPresetResponse {
        id: preset.id.clone(),
        name: preset.name.clone(),
        kind: preset.kind,
        api_base: api_base.clone(),
        model: model.clone(),
        dimension: *dimension,
        temperature: *temperature,
        configured: preset.provider.configured(),
        api_key_configured: api_key
            .as_ref()
            .is_some_and(|value| !value.trim().is_empty()),
        api_key_masked: api_key.as_deref().map(mask_secret),
        source: source.clone(),
        api_key_source: api_key_source.clone(),
        is_default: default_id == Some(preset.id.as_str()),
    }
}

// ============================================================================
// Helpers
// ============================================================================

fn mask_secret(value: &str) -> String {
    let chars: Vec<char> = value.chars().collect();
    if chars.len() <= 8 {
        return "********".to_string();
    }
    let prefix: String = chars.iter().take(4).collect();
    let suffix: String = chars
        .iter()
        .rev()
        .take(4)
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .collect();
    format!("{prefix}****{suffix}")
}

fn normalize_optional_string(value: Option<&str>) -> Option<String> {
    value
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

fn normalize_temperature(value: Option<f32>) -> Result<Option<f32>> {
    match value {
        Some(raw) if !raw.is_finite() => bail!("temperature must be finite"),
        Some(raw) => Ok(Some(raw)),
        None => Ok(None),
    }
}

fn normalize_generation_params(
    mut params: RoleGenerationParamsFile,
) -> Result<RoleGenerationParamsFile> {
    fn check_finite(name: &str, value: Option<f32>) -> Result<Option<f32>> {
        match value {
            Some(raw) if !raw.is_finite() => bail!("{name} must be finite"),
            Some(raw) => Ok(Some(raw)),
            None => Ok(None),
        }
    }
    params.top_p = check_finite("top_p", params.top_p)?;
    params.frequency_penalty = check_finite("frequency_penalty", params.frequency_penalty)?;
    params.presence_penalty = check_finite("presence_penalty", params.presence_penalty)?;
    if let Some(tokens) = params.max_tokens
        && tokens == 0
    {
        params.max_tokens = None;
    }
    Ok(params)
}

fn env_string(key: &str, default: &str) -> String {
    env::var(key)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| default.to_string())
}

fn env_optional_string(key: &str) -> Option<String> {
    env::var(key)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn env_usize_multi(keys: &[&str], default: usize) -> usize {
    for key in keys {
        if let Ok(raw) = env::var(key)
            && let Ok(parsed) = raw.trim().parse::<usize>()
            && parsed > 0
        {
            return parsed;
        }
    }
    default
}
