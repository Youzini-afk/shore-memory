use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use chrono::Utc;
use serde::{Deserialize, Serialize};

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
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub updated_at: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelConfigResponse {
    pub embedding: ProviderConfigResponse,
    pub llm: ProviderConfigResponse,
    pub storage: ModelConfigStorageResponse,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelConfigTestResponse {
    pub embedding: ProviderTestResponse,
    pub llm: ProviderTestResponse,
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
    pub configured: bool,
    pub api_key_configured: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key_masked: Option<String>,
    pub source: String,
    pub api_key_source: String,
    pub override_active: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateModelConfigRequest {
    pub embedding: UpdateProviderConfigRequest,
    pub llm: UpdateProviderConfigRequest,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateProviderConfigRequest {
    pub api_base: String,
    pub model: String,
    #[serde(default)]
    pub dimension: Option<usize>,
    #[serde(default)]
    pub api_key: Option<String>,
    #[serde(default)]
    pub clear_api_key: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuntimeModelConfig {
    pub embedding: RuntimeProviderConfig,
    pub llm: RuntimeProviderConfig,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuntimeProviderConfig {
    pub api_base: String,
    pub model: String,
    pub dimension: Option<usize>,
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
    fn has_nonsecret_override(&self, include_dimension: bool) -> bool {
        self.api_base.is_some()
            || self.model.is_some()
            || (include_dimension && self.dimension.is_some())
    }
}

impl RuntimeModelConfig {
    pub fn to_response(&self, path: &Path, file: Option<&ModelConfigFile>) -> ModelConfigResponse {
        ModelConfigResponse {
            embedding: provider_to_response(&self.embedding),
            llm: provider_to_response(&self.llm),
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
    RuntimeModelConfig {
        embedding: resolve_provider(
            EnvProviderConfig::embedding(),
            file.map(|value| &value.embedding),
        ),
        llm: resolve_provider(EnvProviderConfig::llm(), file.map(|value| &value.llm)),
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
    next.updated_at = Some(Utc::now().to_rfc3339());
    Ok(next)
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

#[derive(Debug, Clone)]
struct EnvProviderConfig {
    api_base: String,
    model: String,
    dimension: Option<usize>,
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
            api_key: env_optional_string("PMW_EMBEDDING_API_KEY"),
        }
    }

    fn llm() -> Self {
        Self {
            api_base: env_string("PMW_LLM_API_BASE", "https://api.openai.com/v1"),
            model: env_string("PMW_LLM_MODEL", ""),
            dimension: None,
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
        api_key: env_api_key,
    } = env_value;
    let include_dimension = env_dimension.is_some();
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
            value.has_nonsecret_override(include_dimension)
                || value.api_key_mode != SecretMode::Inherit
        })
        .unwrap_or(false);
    let file_fields = usize::from(file.and_then(|value| value.api_base.as_ref()).is_some())
        + usize::from(file.and_then(|value| value.model.as_ref()).is_some())
        + usize::from(include_dimension && file.and_then(|value| value.dimension).is_some());
    let total_fields = if include_dimension { 3 } else { 2 };
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
