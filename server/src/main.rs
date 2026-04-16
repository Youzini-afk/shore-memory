mod app;
mod config;
mod db;
mod trivium;
mod types;
mod worker;

use std::sync::Arc;

use anyhow::Result;
use tracing::info;
use tracing_subscriber::EnvFilter;

use crate::app::AppState;
use crate::config::ServiceConfig;
use crate::db::MetadataStore;
use crate::trivium::TriviumStore;
use crate::worker::WorkerClient;

#[tokio::main]
async fn main() -> Result<()> {
    dotenvy::dotenv().ok();
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("shore_memory_server=info,info")),
        )
        .init();

    let config = ServiceConfig::from_env();
    let store = MetadataStore::new(config.metadata_db_path.clone());
    store.init()?;
    let trivium = TriviumStore::new(config.trivium_db_path.clone())?;
    let worker = WorkerClient::new(&config)?;

    let app_state = AppState::new(config.clone(), store, trivium, worker);
    let app = app_state.clone().router();
    Arc::new(app_state).spawn_background_loops();

    let listener = tokio::net::TcpListener::bind(config.bind_addr).await?;
    info!("shore-memory-server listening on {}", config.bind_addr);
    axum::serve(listener, app).await?;
    Ok(())
}
