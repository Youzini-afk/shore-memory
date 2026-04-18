use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use chrono::Utc;
use serde::{Deserialize, Serialize};

// Role-based LLM responsibility split.
//
// Each role is a distinct LLM use case (see ``worker/app/main.py``). The
// server only needs to know which roles exist so it can validate incoming
// payloads and surface them in the model-config response; the actual prompts
// and upstream calls live in the worker.
pub const ROLE_SCORER: &str = "scorer";
pub const ROLE_REFLECTOR: &str = "reflector";
pub const ROLE_QUERY_ANALYZER: &str = "query_analyzer";

pub const KNOWN_ROLES: &[&str] = &[ROLE_SCORER, ROLE_REFLECTOR, ROLE_QUERY_ANALYZER];

pub fn default_role_temperature(role: &str) -> f32 {
    match role {
        ROLE_SCORER => 0.3,
        ROLE_REFLECTOR => 0.4,
        ROLE_QUERY_ANALYZER => 0.1,
        _ => 0.3,
    }
}

fn is_known_role(role: &str) -> bool {
    KNOWN_ROLES.iter().any(|candidate| *candidate == role)
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
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ModelConfigFile {
    #[serde(default)]
    pub embedding: ProviderOverrideFile,
    #[serde(default)]
    pub llm: ProviderOverrideFile,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub roles: BTreeMap<String, ProviderOverrideFile>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub updated_at: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelConfigResponse {
    pub embedding: ProviderConfigResponse,
    pub llm: ProviderConfigResponse,
    pub roles: BTreeMap<String, ProviderConfigResponse>,
    pub overrides: ModelConfigOverridesResponse,
    pub storage: ModelConfigStorageResponse,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelConfigTestResponse {
    pub embedding: ProviderTestResponse,
    pub llm: ProviderTestResponse,
    pub roles: BTreeMap<String, ProviderTestResponse>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelConfigOverridesResponse {
    pub embedding: ProviderOverrideResponse,
    pub llm: ProviderOverrideResponse,
    pub roles: BTreeMap<String, ProviderOverrideResponse>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProviderOverrideResponse {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_base: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dimension: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    pub api_key_mode: SecretMode,
    pub api_key_configured: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key_masked: Option<String>,
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

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ProviderKind {
    Embedding,
    Llm,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListProviderModelsRequest {
    pub provider: ProviderKind,
    pub api_base: String,
    #[serde(default)]
    pub role: Option<String>,
    #[serde(default)]
    pub api_key: Option<String>,
    #[serde(default)]
    pub clear_api_key: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ListProviderModelsResponse {
    pub provider: ProviderKind,
    pub models: Vec<String>,
    pub count: usize,
    pub source: String,
    pub api_key_source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetectEmbeddingDimensionRequest {
    pub api_base: String,
    pub model: String,
    #[serde(default)]
    pub api_key: Option<String>,
    #[serde(default)]
    pub clear_api_key: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct DetectEmbeddingDimensionResponse {
    pub model: String,
    pub dimension: usize,
    pub source: String,
    pub api_key_source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateModelConfigRequest {
    pub embedding: UpdateProviderConfigRequest,
    pub llm: UpdateProviderConfigRequest,
    #[serde(default)]
    pub roles: Option<BTreeMap<String, UpdateRoleConfigRequest>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateProviderConfigRequest {
    pub api_base: String,
    pub model: String,
    #[serde(default)]
    pub dimension: Option<usize>,
    #[serde(default)]
    pub temperature: Option<f32>,
    #[serde(default)]
    pub api_key: Option<String>,
    #[serde(default)]
    pub clear_api_key: bool,
    #[serde(default)]
    pub auto_detect_dimension: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct UpdateRoleConfigRequest {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub api_base: Option<String>,
    #[serde(default)]
    pub model: Option<String>,
    #[serde(default)]
    pub temperature: Option<f32>,
    #[serde(default)]
    pub api_key_mode: Option<SecretMode>,
    #[serde(default)]
    pub api_key: Option<String>,
    #[serde(default)]
    pub clear_api_key: bool,
}

#[derive(Debug, Clone)]
pub struct ResolvedProviderProbe {
    pub api_base: String,
    pub model: String,
    pub api_key: Option<String>,
    pub source: String,
    pub api_key_source: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RuntimeModelConfig {
    pub embedding: RuntimeProviderConfig,
    pub llm: RuntimeProviderConfig,
    pub roles: BTreeMap<String, RuntimeProviderConfig>,
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

impl ProviderOverrideFile {
    fn has_nonsecret_override(&self, include_dimension: bool, include_temperature: bool) -> bool {
        self.api_base.is_some()
            || self.model.is_some()
            || (include_dimension && self.dimension.is_some())
            || (include_temperature && self.temperature.is_some())
    }
}

impl RuntimeModelConfig {
    pub fn to_response(&self, path: &Path, file: Option<&ModelConfigFile>) -> ModelConfigResponse {
        let overrides = ModelConfigOverridesResponse {
            embedding: provider_override_to_response(file.map(|value| &value.embedding)),
            llm: provider_override_to_response(file.map(|value| &value.llm)),
            roles: KNOWN_ROLES
                .iter()
                .map(|role| {
                    (
                        (*role).to_string(),
                        provider_override_to_response(file.and_then(|value| value.roles.get(*role))),
                    )
                })
                .collect(),
        };
        ModelConfigResponse {
            embedding: provider_to_response(&self.embedding),
            llm: provider_to_response(&self.llm),
            roles: self
                .roles
                .iter()
                .map(|(role, provider)| (role.clone(), provider_to_response(provider)))
                .collect(),
            overrides,
            storage: ModelConfigStorageResponse {
                path: path.display().to_string(),
                override_active: file.is_some(),
                updated_at: file.and_then(|value| value.updated_at.clone()),
            },
        }
    }
}

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
    Ok(Some(parsed))
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

pub fn resolve_runtime_model_config(file: Option<&ModelConfigFile>) -> RuntimeModelConfig {
    let llm = resolve_provider(EnvProviderConfig::llm(), file.map(|value| &value.llm));
    RuntimeModelConfig {
        embedding: resolve_provider(
            EnvProviderConfig::embedding(),
            file.map(|value| &value.embedding),
        ),
        llm: llm.clone(),
        roles: KNOWN_ROLES
            .iter()
            .map(|role| {
                (
                    (*role).to_string(),
                    resolve_role_provider(*role, &llm, file.and_then(|value| value.roles.get(*role))),
                )
            })
            .collect(),
    }
}

pub fn embedding_dim_from_env_or_file(path: &Path) -> Result<usize> {
    let (runtime, _) = load_runtime_model_config(path)?;
    Ok(runtime.embedding.dimension.unwrap_or(1536).max(1))
}

pub fn apply_update(
    existing: Option<ModelConfigFile>,
    request: UpdateModelConfigRequest,
) -> Result<ModelConfigFile> {
    let mut next = existing.unwrap_or_default();
    next.embedding = apply_provider_update(next.embedding, request.embedding, true)?;
    next.llm = apply_provider_update(next.llm, request.llm, false)?;
    if let Some(role_updates) = request.roles {
        for (role, role_request) in role_updates {
            if !is_known_role(&role) {
                bail!("unknown role: {role}");
            }
            let current = next.roles.remove(&role);
            if let Some(updated) = apply_role_update(current, role_request)? {
                next.roles.insert(role, updated);
            }
        }
    }
    next.updated_at = Some(Utc::now().to_rfc3339());
    Ok(next)
}

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

fn apply_provider_update(
    mut existing: ProviderOverrideFile,
    request: UpdateProviderConfigRequest,
    is_embedding: bool,
) -> Result<ProviderOverrideFile> {
    let api_base = request.api_base.trim();
    if api_base.is_empty() {
        bail!("api_base is required");
    }
    let model = request.model.trim();
    if model.is_empty() {
        bail!("model is required");
    }
    existing.api_base = Some(api_base.to_string());
    existing.model = Some(model.to_string());

    if is_embedding {
        let dim = request.dimension.unwrap_or(1536);
        if dim == 0 {
            bail!("embedding dimension must be greater than 0");
        }
        existing.dimension = Some(dim);
        existing.temperature = None;
    } else {
        existing.dimension = None;
        existing.temperature = normalize_temperature(request.temperature)?;
    }

    if request.clear_api_key {
        existing.api_key_mode = SecretMode::Clear;
        existing.api_key = None;
    } else if let Some(api_key) = request
        .api_key
        .as_ref()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
    {
        existing.api_key_mode = SecretMode::Set;
        existing.api_key = Some(api_key.to_string());
    }

    Ok(existing)
}

fn apply_role_update(
    existing: Option<ProviderOverrideFile>,
    request: UpdateRoleConfigRequest,
) -> Result<Option<ProviderOverrideFile>> {
    if !request.enabled {
        return Ok(None);
    }

    let mut next = existing.unwrap_or_default();
    next.api_base = normalize_optional_string(request.api_base.as_deref());
    next.model = normalize_optional_string(request.model.as_deref());
    next.dimension = None;
    next.temperature = normalize_temperature(request.temperature)?;

    let requested_api_key = normalize_optional_string(request.api_key.as_deref());
    if let Some(api_key_mode) = request.api_key_mode {
        match api_key_mode {
            SecretMode::Inherit => {
                next.api_key_mode = SecretMode::Inherit;
                next.api_key = None;
            }
            SecretMode::Clear => {
                next.api_key_mode = SecretMode::Clear;
                next.api_key = None;
            }
            SecretMode::Set => {
                next.api_key_mode = SecretMode::Set;
                if let Some(api_key) = requested_api_key {
                    next.api_key = Some(api_key);
                }
            }
        }
    } else if request.clear_api_key {
        next.api_key_mode = SecretMode::Clear;
        next.api_key = None;
    } else if let Some(api_key) = requested_api_key {
        next.api_key_mode = SecretMode::Set;
        next.api_key = Some(api_key);
    }

    if next.has_nonsecret_override(false, true) || next.api_key_mode != SecretMode::Inherit {
        Ok(Some(next))
    } else {
        Ok(None)
    }
}

#[derive(Debug, Clone)]
struct EnvProviderConfig {
    api_base: String,
    model: String,
    dimension: Option<usize>,
    temperature: Option<f32>,
    api_key: Option<String>,
}

impl EnvProviderConfig {
    fn embedding() -> Self {
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

    fn llm() -> Self {
        Self {
            api_base: env_string("PMW_LLM_API_BASE", "https://api.openai.com/v1"),
            model: env_string("PMW_LLM_MODEL", ""),
            dimension: None,
            temperature: None,
            api_key: env_optional_string("PMW_LLM_API_KEY"),
        }
    }
}

fn resolve_provider(
    env_value: EnvProviderConfig,
    file: Option<&ProviderOverrideFile>,
) -> RuntimeProviderConfig {
    let EnvProviderConfig {
        api_base: env_api_base,
        model: env_model,
        dimension: env_dimension,
        temperature: env_temperature,
        api_key: env_api_key,
    } = env_value;
    let include_dimension = env_dimension.is_some();
    let include_temperature = env_dimension.is_none();
    let api_base = file
        .and_then(|value| value.api_base.as_ref())
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
        .unwrap_or(env_api_base);
    let model = file
        .and_then(|value| value.model.as_ref())
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
        .unwrap_or(env_model);
    let dimension = file
        .and_then(|value| value.dimension)
        .or(env_dimension)
        .map(|value| value.max(1));
    let temperature = if include_temperature {
        file.and_then(|value| value.temperature).or(env_temperature)
    } else {
        None
    };

    let (api_key, api_key_source) = match file
        .map(|value| value.api_key_mode)
        .unwrap_or(SecretMode::Inherit)
    {
        SecretMode::Inherit => match env_api_key {
            Some(value) => (Some(value), "env".to_string()),
            None => (None, "unset".to_string()),
        },
        SecretMode::Clear => (None, "cleared".to_string()),
        SecretMode::Set => {
            let key = file
                .and_then(|value| value.api_key.as_ref())
                .map(|value| value.trim())
                .filter(|value| !value.is_empty())
                .map(ToOwned::to_owned);
            let source = if key.is_some() { "file" } else { "unset" };
            (key, source.to_string())
        }
    };

    let override_active = file
        .map(|value| {
            value.has_nonsecret_override(include_dimension, include_temperature)
                || value.api_key_mode != SecretMode::Inherit
        })
        .unwrap_or(false);
    let file_fields = usize::from(file.and_then(|value| value.api_base.as_ref()).is_some())
        + usize::from(file.and_then(|value| value.model.as_ref()).is_some())
        + usize::from(include_dimension && file.and_then(|value| value.dimension).is_some())
        + usize::from(include_temperature && file.and_then(|value| value.temperature).is_some());
    let total_fields = 2 + usize::from(include_dimension) + usize::from(include_temperature);
    let source = if !override_active || file_fields == 0 {
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

fn resolve_role_provider(
    role: &str,
    llm: &RuntimeProviderConfig,
    file: Option<&ProviderOverrideFile>,
) -> RuntimeProviderConfig {
    let api_base = file
        .and_then(|value| value.api_base.as_ref())
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| llm.api_base.clone());
    let model = file
        .and_then(|value| value.model.as_ref())
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| llm.model.clone());
    let temperature = file
        .and_then(|value| value.temperature)
        .or(llm.temperature)
        .or(Some(default_role_temperature(role)));

    let (api_key, api_key_source) = match file
        .map(|value| value.api_key_mode)
        .unwrap_or(SecretMode::Inherit)
    {
        SecretMode::Inherit => (llm.api_key.clone(), "inherit".to_string()),
        SecretMode::Clear => (None, "cleared".to_string()),
        SecretMode::Set => {
            let key = file
                .and_then(|value| value.api_key.as_ref())
                .map(|value| value.trim())
                .filter(|value| !value.is_empty())
                .map(ToOwned::to_owned);
            let source = if key.is_some() { "file" } else { "unset" };
            (key, source.to_string())
        }
    };

    let override_active = file
        .map(|value| value.has_nonsecret_override(false, true) || value.api_key_mode != SecretMode::Inherit)
        .unwrap_or(false);
    let file_fields = usize::from(file.and_then(|value| value.api_base.as_ref()).is_some())
        + usize::from(file.and_then(|value| value.model.as_ref()).is_some())
        + usize::from(file.and_then(|value| value.temperature).is_some());
    let source = if file_fields == 0 {
        "inherit".to_string()
    } else if file_fields >= 3 {
        "file".to_string()
    } else {
        "mixed".to_string()
    };

    RuntimeProviderConfig {
        api_base,
        model,
        dimension: None,
        temperature,
        api_key,
        source,
        api_key_source,
        override_active,
    }
}

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

fn provider_override_to_response(provider: Option<&ProviderOverrideFile>) -> ProviderOverrideResponse {
    let api_key = provider
        .and_then(|value| value.api_key.as_ref())
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned);
    ProviderOverrideResponse {
        api_base: provider
            .and_then(|value| normalize_optional_string(value.api_base.as_deref())),
        model: provider.and_then(|value| normalize_optional_string(value.model.as_deref())),
        dimension: provider.and_then(|value| value.dimension),
        temperature: provider.and_then(|value| value.temperature),
        api_key_mode: provider.map(|value| value.api_key_mode).unwrap_or_default(),
        api_key_configured: api_key.is_some(),
        api_key_masked: api_key.as_deref().map(mask_secret),
    }
}

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
    value.map(str::trim).filter(|value| !value.is_empty()).map(ToOwned::to_owned)
}

fn normalize_temperature(value: Option<f32>) -> Result<Option<f32>> {
    match value {
        Some(raw) if !raw.is_finite() => bail!("temperature must be finite"),
        Some(raw) => Ok(Some(raw)),
        None => Ok(None),
    }
}

fn default_true() -> bool {
    true
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
