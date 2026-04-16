use anyhow::{Context, Result, anyhow};
use reqwest::Client;
use serde_json::json;

use crate::config::ServiceConfig;
use crate::types::{
    ReflectionMemoryInput, WorkerEmbedRequest, WorkerEmbedResponse, WorkerMemoryDraft,
    WorkerReflectionRequest, WorkerReflectionResponse, WorkerScoreTurnRequest,
    WorkerScoreTurnResponse,
};

#[derive(Clone)]
pub struct WorkerClient {
    client: Client,
    base_url: String,
}

impl WorkerClient {
    pub fn new(config: &ServiceConfig) -> Result<Self> {
        let client = Client::builder()
            .timeout(config.worker_timeout)
            .build()
            .context("failed to build reqwest client")?;
        Ok(Self {
            client,
            base_url: config.worker_base_url.trim_end_matches('/').to_string(),
        })
    }

    pub async fn health(&self) -> Result<()> {
        let url = format!("{}/health", self.base_url);
        self.client
            .get(url)
            .send()
            .await
            .context("worker health request failed")?
            .error_for_status()
            .context("worker health returned error")?;
        Ok(())
    }

    pub async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        let url = format!("{}/v1/embed", self.base_url);
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
    }

    pub async fn score_turn(&self, request: &WorkerScoreTurnRequest) -> Result<WorkerScoreTurnResponse> {
        let url = format!("{}/v1/tasks/score-turn", self.base_url);
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
    }

    pub async fn reflect(
        &self,
        agent_id: &str,
        memories: Vec<ReflectionMemoryInput>,
    ) -> Result<WorkerReflectionResponse> {
        let url = format!("{}/v1/tasks/reflect", self.base_url);
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
    }
}

pub fn reflection_inputs_from_memories(memories: &[crate::types::MemoryRecord]) -> Vec<ReflectionMemoryInput> {
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

pub fn memory_draft_metadata_with_task(task_id: i64, draft: &WorkerMemoryDraft) -> serde_json::Value {
    let mut metadata = draft.metadata.clone();
    if let Some(obj) = metadata.as_object_mut() {
        obj.insert("task_id".to_string(), json!(task_id));
    }
    metadata
}
