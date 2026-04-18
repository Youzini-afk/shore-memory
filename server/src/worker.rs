use anyhow::{Context, Result, anyhow};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::time::Duration;
use tokio::time::timeout;

use crate::config::ServiceConfig;
use crate::types::{
    EntityDraft, ReflectionMemoryInput, WorkerEmbedRequest, WorkerEmbedResponse, WorkerMemoryDraft,
    WorkerReflectionRequest, WorkerReflectionResponse, WorkerScoreTurnRequest,
    WorkerScoreTurnResponse,
};

#[derive(Debug, Clone, Serialize)]
struct WorkerEmbedBatchRequest {
    texts: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct WorkerEmbedBatchResponse {
    embeddings: Vec<Vec<f32>>,
}

#[derive(Debug, Clone, Serialize)]
struct WorkerExtractEntitiesRequest {
    query: String,
    observation_date: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
struct WorkerProviderProbeRequest {
    api_base: String,
    api_key: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    model: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct WorkerExtractEntitiesResponse {
    #[serde(default)]
    entities: Vec<EntityDraft>,
}

#[derive(Debug, Clone, Deserialize)]
struct WorkerProviderModelsResponse {
    #[serde(default)]
    models: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct WorkerEmbeddingDimensionResponse {
    model: String,
    dimension: usize,
}

#[derive(Clone)]
pub struct WorkerClient {
    client: Client,
    base_url: String,
    timeout_default: Duration,
    timeout_embed: Duration,
    timeout_embed_batch: Duration,
    timeout_extract_entities: Duration,
    timeout_score_turn: Duration,
    timeout_reflect: Duration,
}

impl WorkerClient {
    pub fn new(config: &ServiceConfig) -> Result<Self> {
        let max_timeout = [
            config.worker_timeout,
            config.worker_timeout_embed,
            config.worker_timeout_embed_batch,
            config.worker_timeout_extract_entities,
            config.worker_timeout_score_turn,
            config.worker_timeout_reflect,
        ]
        .into_iter()
        .max()
        .unwrap_or(config.worker_timeout);

        let client = Client::builder()
            .timeout(max_timeout)
            .build()
            .context("failed to build reqwest client")?;
        Ok(Self {
            client,
            base_url: config.worker_base_url.trim_end_matches('/').to_string(),
            timeout_default: config.worker_timeout,
            timeout_embed: config.worker_timeout_embed,
            timeout_embed_batch: config.worker_timeout_embed_batch,
            timeout_extract_entities: config.worker_timeout_extract_entities,
            timeout_score_turn: config.worker_timeout_score_turn,
            timeout_reflect: config.worker_timeout_reflect,
        })
    }

    async fn run_with_timeout<T, F>(op: &str, duration: Duration, fut: F) -> Result<T>
    where
        F: std::future::Future<Output = Result<T>>,
    {
        timeout(duration, fut)
            .await
            .with_context(|| format!("worker {} timeout after {} ms", op, duration.as_millis()))?
    }

    pub async fn health(&self) -> Result<()> {
        let url = format!("{}/health", self.base_url);
        Self::run_with_timeout("health", self.timeout_default, async {
            self.client
                .get(url)
                .send()
                .await
                .context("worker health request failed")?
                .error_for_status()
                .context("worker health returned error")?;
            Ok(())
        })
        .await
    }

    pub async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        let url = format!("{}/v1/embed", self.base_url);
        Self::run_with_timeout("embed", self.timeout_embed, async {
            let response = self
                .client
                .post(url)
                .json(&WorkerEmbedRequest {
                    text: text.to_string(),
                })
                .send()
                .await
                .context("worker embed request failed")?
                .error_for_status()
                .context("worker embed returned error")?
                .json::<WorkerEmbedResponse>()
                .await
                .context("worker embed response parse failed")?;

            if response.embedding.is_empty() {
                return Err(anyhow!("worker returned empty embedding"));
            }

            Ok(response.embedding)
        })
        .await
    }

    /// Batched embedding. Preserves input order. Empty input strings come back
    /// as empty vectors so callers can map indices 1:1.
    pub async fn embed_batch(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(Vec::new());
        }
        let url = format!("{}/v1/embed/batch", self.base_url);
        Self::run_with_timeout("embed_batch", self.timeout_embed_batch, async {
            let response = self
                .client
                .post(url)
                .json(&WorkerEmbedBatchRequest { texts })
                .send()
                .await
                .context("worker embed_batch request failed")?
                .error_for_status()
                .context("worker embed_batch returned error")?
                .json::<WorkerEmbedBatchResponse>()
                .await
                .context("worker embed_batch response parse failed")?;
            Ok(response.embeddings)
        })
        .await
    }

    /// Extract named entities from a query string. Returns an empty list when
    /// the worker is not configured with an LLM — recall falls back to
    /// semantic + BM25 in that case.
    pub async fn extract_entities(
        &self,
        query: &str,
        observation_date: Option<&str>,
    ) -> Result<Vec<EntityDraft>> {
        let url = format!("{}/v1/tasks/extract-entities", self.base_url);
        Self::run_with_timeout("extract_entities", self.timeout_extract_entities, async {
            let response = self
                .client
                .post(url)
                .json(&WorkerExtractEntitiesRequest {
                    query: query.to_string(),
                    observation_date: observation_date.map(str::to_string),
                })
                .send()
                .await
                .context("worker extract_entities request failed")?
                .error_for_status()
                .context("worker extract_entities returned error")?
                .json::<WorkerExtractEntitiesResponse>()
                .await
                .context("worker extract_entities response parse failed")?;
            Ok(response.entities)
        })
        .await
    }

    pub async fn list_provider_models(&self, api_base: &str, api_key: &str) -> Result<Vec<String>> {
        let url = format!("{}/v1/provider/models", self.base_url);
        Self::run_with_timeout("provider_models", self.timeout_default, async {
            let response = self
                .client
                .post(url)
                .json(&WorkerProviderProbeRequest {
                    api_base: api_base.to_string(),
                    api_key: api_key.to_string(),
                    model: None,
                })
                .send()
                .await
                .context("worker provider models request failed")?
                .error_for_status()
                .context("worker provider models returned error")?
                .json::<WorkerProviderModelsResponse>()
                .await
                .context("worker provider models response parse failed")?;
            Ok(response.models)
        })
        .await
    }

    pub async fn detect_embedding_dimension(
        &self,
        api_base: &str,
        api_key: &str,
        model: &str,
    ) -> Result<usize> {
        let url = format!("{}/v1/provider/embedding/dimension", self.base_url);
        Self::run_with_timeout("embedding_dimension", self.timeout_embed, async {
            let response = self
                .client
                .post(url)
                .json(&WorkerProviderProbeRequest {
                    api_base: api_base.to_string(),
                    api_key: api_key.to_string(),
                    model: Some(model.to_string()),
                })
                .send()
                .await
                .context("worker embedding dimension request failed")?
                .error_for_status()
                .context("worker embedding dimension returned error")?
                .json::<WorkerEmbeddingDimensionResponse>()
                .await
                .context("worker embedding dimension response parse failed")?;
            if response.model.trim().is_empty() || response.dimension == 0 {
                return Err(anyhow!(
                    "worker returned invalid embedding dimension payload"
                ));
            }
            Ok(response.dimension)
        })
        .await
    }

    pub async fn score_turn(
        &self,
        request: &WorkerScoreTurnRequest,
    ) -> Result<WorkerScoreTurnResponse> {
        let url = format!("{}/v1/tasks/score-turn", self.base_url);
        Self::run_with_timeout("score_turn", self.timeout_score_turn, async {
            self.client
                .post(url)
                .json(request)
                .send()
                .await
                .context("worker score_turn request failed")?
                .error_for_status()
                .context("worker score_turn returned error")?
                .json::<WorkerScoreTurnResponse>()
                .await
                .context("worker score_turn response parse failed")
        })
        .await
    }

    pub async fn reflect(
        &self,
        agent_id: &str,
        memories: Vec<ReflectionMemoryInput>,
    ) -> Result<WorkerReflectionResponse> {
        let url = format!("{}/v1/tasks/reflect", self.base_url);
        Self::run_with_timeout("reflect", self.timeout_reflect, async {
            self.client
                .post(url)
                .json(&WorkerReflectionRequest {
                    agent_id: agent_id.to_string(),
                    memories,
                })
                .send()
                .await
                .context("worker reflection request failed")?
                .error_for_status()
                .context("worker reflection returned error")?
                .json::<WorkerReflectionResponse>()
                .await
                .context("worker reflection response parse failed")
        })
        .await
    }
}

pub fn reflection_inputs_from_memories(
    memories: &[crate::types::MemoryRecord],
) -> Vec<ReflectionMemoryInput> {
    memories
        .iter()
        .map(|memory| ReflectionMemoryInput {
            id: memory.id,
            content: memory.content.clone(),
            importance: memory.importance,
            scope: memory.scope.clone(),
            created_at: memory.created_at.clone(),
        })
        .collect()
}

pub fn memory_draft_metadata_with_task(
    task_id: i64,
    draft: &WorkerMemoryDraft,
) -> serde_json::Value {
    let mut metadata = draft.metadata.clone();
    if let Some(obj) = metadata.as_object_mut() {
        obj.insert("task_id".to_string(), json!(task_id));
    }
    metadata
}
