use std::env;
use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::path::PathBuf;
use std::time::Duration;

#[derive(Debug, Clone)]
pub struct ServiceConfig {
    pub bind_addr: SocketAddr,
    pub metadata_db_path: PathBuf,
    pub trivium_db_path: PathBuf,
    /// Separate Trivium DB file for the entity vector index.
    /// Keeps entity vectors isolated from memory vectors so scope-level
    /// filters and rebuilds don't cross-contaminate.
    pub entity_trivium_db_path: PathBuf,
    /// Optional path to the compiled Web UI (`web/dist`). If present and the
    /// directory contains an `index.html`, the server serves the SPA as the
    /// fallback route for unknown paths.
    pub web_dist_path: Option<PathBuf>,
    pub worker_base_url: String,
    /// Optional API key required for all `/v1/*` routes.
    ///
    /// The key can be passed via `x-api-key`, `Authorization: Bearer ...`,
    /// or `?api_key=` (used by browser WebSocket clients).
    pub api_key: Option<String>,
    pub embedding_timeout: Duration,
    pub worker_timeout: Duration,
    pub worker_timeout_embed: Duration,
    pub worker_timeout_embed_batch: Duration,
    pub worker_timeout_extract_entities: Duration,
    pub worker_timeout_score_turn: Duration,
    pub worker_timeout_reflect: Duration,
    pub recall_cache_ttl: Duration,
    pub embedding_cache_ttl: Duration,
    pub task_poll_interval: Duration,
    pub task_workers: usize,
    pub search_top_k: usize,
    pub search_expand_depth: usize,
    pub search_min_score: f32,
    /// Entity-vector cosine threshold below which an entity hit is ignored.
    pub entity_min_score: f32,
    /// Weight on the entity-boost signal in the additive scoring formula.
    pub entity_boost_weight: f32,
    /// Weight on the contiguity signal in the additive scoring formula.
    pub contiguity_boost_weight: f32,
    /// Fixed score contribution each contiguity-pulled memory receives.
    pub contiguity_boost_value: f32,
    /// How many memories before/after the reference to pull for contiguity.
    pub contiguity_before: usize,
    pub contiguity_after: usize,
}

impl ServiceConfig {
    pub fn from_env() -> Self {
        let host = env::var("PMS_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
        let port = parse_u16("PMS_PORT", 7811);
        let bind_addr = SocketAddr::new(
            host.parse().unwrap_or(IpAddr::V4(Ipv4Addr::LOCALHOST)),
            port,
        );

        let data_dir =
            PathBuf::from(env::var("PMS_DATA_DIR").unwrap_or_else(|_| "./data".to_string()));
        let metadata_db_path = env::var("PMS_METADATA_DB_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| data_dir.join("metadata.sqlite3"));
        let trivium_db_path = env::var("PMS_TRIVIUM_DB_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| data_dir.join("memory.tdb"));
        let entity_trivium_db_path = env::var("PMS_ENTITY_TRIVIUM_DB_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| data_dir.join("entities.tdb"));
        let web_dist_path = env::var("PMS_WEB_DIST")
            .ok()
            .map(PathBuf::from)
            .or_else(|| {
                // 默认相对 server 工作目录向上找 `../web/dist`；若不存在则返回 None。
                let candidate = PathBuf::from("../web/dist");
                if candidate.join("index.html").exists() {
                    Some(candidate)
                } else {
                    None
                }
            });

        Self {
            bind_addr,
            metadata_db_path,
            trivium_db_path,
            entity_trivium_db_path,
            web_dist_path,
            worker_base_url: env::var("PMS_WORKER_BASE_URL")
                .unwrap_or_else(|_| "http://127.0.0.1:7812".to_string()),
            api_key: env::var("PMS_API_KEY")
                .ok()
                .map(|v| v.trim().to_string())
                .filter(|v| !v.is_empty()),
            embedding_timeout: Duration::from_millis(parse_u64("PMS_EMBEDDING_TIMEOUT_MS", 1800)),
            worker_timeout: Duration::from_millis(parse_u64("PMS_WORKER_TIMEOUT_MS", 10_000)),
            worker_timeout_embed: Duration::from_millis(parse_u64(
                "PMS_WORKER_TIMEOUT_EMBED_MS",
                1_500,
            )),
            worker_timeout_embed_batch: Duration::from_millis(parse_u64(
                "PMS_WORKER_TIMEOUT_EMBED_BATCH_MS",
                3_000,
            )),
            worker_timeout_extract_entities: Duration::from_millis(parse_u64(
                "PMS_WORKER_TIMEOUT_EXTRACT_ENTITIES_MS",
                3_000,
            )),
            worker_timeout_score_turn: Duration::from_millis(parse_u64(
                "PMS_WORKER_TIMEOUT_SCORE_TURN_MS",
                8_000,
            )),
            worker_timeout_reflect: Duration::from_millis(parse_u64(
                "PMS_WORKER_TIMEOUT_REFLECT_MS",
                45_000,
            )),
            recall_cache_ttl: Duration::from_secs(parse_u64("PMS_RECALL_CACHE_TTL_SECS", 30)),
            embedding_cache_ttl: Duration::from_secs(parse_u64(
                "PMS_EMBEDDING_CACHE_TTL_SECS",
                600,
            )),
            task_poll_interval: Duration::from_millis(parse_u64("PMS_TASK_POLL_INTERVAL_MS", 1500)),
            task_workers: parse_usize("PMS_TASK_WORKERS", 4).max(1),
            search_top_k: parse_usize("PMS_SEARCH_TOP_K", 12),
            search_expand_depth: parse_usize("PMS_SEARCH_EXPAND_DEPTH", 2),
            search_min_score: parse_f32("PMS_SEARCH_MIN_SCORE", 0.03),
            entity_min_score: parse_f32("PMS_ENTITY_MIN_SCORE", 0.5),
            entity_boost_weight: parse_f32("PMS_ENTITY_BOOST_WEIGHT", 0.5),
            contiguity_boost_weight: parse_f32("PMS_CONTIGUITY_BOOST_WEIGHT", 0.3),
            contiguity_boost_value: parse_f32("PMS_CONTIGUITY_BOOST_VALUE", 0.4),
            contiguity_before: parse_usize("PMS_CONTIGUITY_BEFORE", 1),
            contiguity_after: parse_usize("PMS_CONTIGUITY_AFTER", 1),
        }
    }
}

fn parse_u16(key: &str, default: u16) -> u16 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn parse_u64(key: &str, default: u64) -> u64 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn parse_usize(key: &str, default: usize) -> usize {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn parse_f32(key: &str, default: f32) -> f32 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}
