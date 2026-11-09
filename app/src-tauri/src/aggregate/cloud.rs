use super::store::{self, PlaylistType};
use crate::{
    model::{AppResult, Track},
    storage::now_seconds,
    Backend,
};
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tauri::{Emitter, State};

pub const DEFAULT_SERVER_URL: &str = "";

#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct CloudSyncConfig {
    pub server_url: String,
    pub token: String,
    pub auto_sync: bool,
    pub last_sync_time: Option<i64>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct CloudSyncResult {
    pub success: bool,
    pub pulled: usize,
    pub pushed: usize,
    pub timestamp: i64,
    pub error: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct CloudPlaylistPayload {
    id: String,
    name: String,
    playlist_type: String,
    covers: Vec<String>,
    track_count: usize,
    updated_at: i64,
    tracks: Vec<Track>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct SyncBatchRequest {
    playlists: Vec<CloudPlaylistPayload>,
}

#[derive(Deserialize)]
#[allow(dead_code)]
#[serde(rename_all = "camelCase")]
struct SyncBatchResponse {
    success: bool,
    #[serde(default)]
    playlists: Vec<CloudPlaylistPayload>,
    #[serde(default)]
    timestamp: i64,
}

pub(crate) fn get_config(backend: &Backend) -> CloudSyncConfig {
    let server_url = backend
        .store
        .setting("cloudSyncServerUrl")
        .ok()
        .flatten()
        .unwrap_or_else(|| DEFAULT_SERVER_URL.to_string());
    let token = backend
        .store
        .setting("cloudSyncToken")
        .ok()
        .flatten()
        .unwrap_or_default();
    let auto_sync = backend
        .store
        .setting("cloudSyncAuto")
        .ok()
        .flatten()
        .as_deref()
        != Some("false");
    let last_sync_time = backend
        .store
        .setting("cloudSyncLastTime")
        .ok()
        .flatten()
        .and_then(|s| s.parse::<i64>().ok());

    CloudSyncConfig {
        server_url,
        token,
        auto_sync,
        last_sync_time,
    }
}

pub(crate) fn save_config(backend: &Backend, config: &CloudSyncConfig) -> AppResult<()> {
    backend
        .store
        .set_setting("cloudSyncServerUrl", &config.server_url)?;
    backend.store.set_setting("cloudSyncToken", &config.token)?;
    backend.store.set_setting(
        "cloudSyncAuto",
        if config.auto_sync { "true" } else { "false" },
    )?;
    Ok(())
}

pub(crate) async fn execute_sync(
    backend: &Backend,
    app: &tauri::AppHandle,
) -> AppResult<CloudSyncResult> {
    let config = get_config(backend);
    let server_url = config.server_url.trim().trim_end_matches('/');
    if server_url.is_empty() {
        return Err("未配置同步服务器地址".into());
    }

    let store = backend.store.clone();
    let now = now_seconds();

    // 1. 读取本地所有歌单及其全部歌曲
    let local_playlists = tauri::async_runtime::spawn_blocking({
        let s = store.clone();
        move || {
            let list = store::playlists(&s)?;
            let mut payloads = Vec::new();
            for p in list {
                let tracks = store::all_playlist_tracks(&s, &p.id)?;
                payloads.push(CloudPlaylistPayload {
                    id: p.id,
                    name: p.name,
                    playlist_type: match p.playlist_type {
                        PlaylistType::Local => "local".into(),
                        PlaylistType::Aggregate => "aggregate".into(),
                    },
                    covers: p.covers,
                    track_count: tracks.len(),
                    updated_at: now,
                    tracks,
                });
            }
            Ok::<_, String>(payloads)
        }
    })
    .await
    .map_err(|e| e.to_string())??;

    let pushed_count = local_playlists.len();

    // 2. 向路由器发起同步 POST /api/v1/sync
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(15))
        .build()
        .map_err(|e| e.to_string())?;

    let sync_url = format!("{}/api/v1/sync", server_url);
    let mut request_builder = client.post(&sync_url).json(&SyncBatchRequest {
        playlists: local_playlists,
    });

    if !config.token.is_empty() {
        request_builder = request_builder.header("Authorization", format!("Bearer {}", config.token));
    }

    let resp = request_builder
        .send()
        .await
        .map_err(|e| format!("无法连接到同步服务（{}）：{}", sync_url, e))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let text = resp.text().await.unwrap_or_default();
        return Err(format!("同步服务返回错误（HTTP {}）：{}", status, text));
    }

    let batch_resp: SyncBatchResponse = resp
        .json()
        .await
        .map_err(|e| format!("解析同步响应失败：{}", e))?;

    // 3. 将云端歌单合并入本地 SQLite
    let pulled_count = batch_resp.playlists.len();
    let updated_playlists = batch_resp.playlists;

    tauri::async_runtime::spawn_blocking({
        let s = store.clone();
        move || {
            for cp in updated_playlists {
                let _ = store::apply_cloud_playlist(&s, &cp.name, &cp.tracks)?;
            }
            s.set_setting("cloudSyncLastTime", &now.to_string())?;
            Ok::<_, String>(())
        }
    })
    .await
    .map_err(|e| e.to_string())??;

    // 通知前端界面刷新
    let _ = app.emit("aggregate-playlist-updated", ());
    let _ = app.emit("local-library-updated", ());

    Ok(CloudSyncResult {
        success: true,
        pulled: pulled_count,
        pushed: pushed_count,
        timestamp: now,
        error: None,
    })
}

#[tauri::command]
pub async fn cloud_sync(
    backend: State<'_, Backend>,
    app: tauri::AppHandle,
) -> AppResult<CloudSyncResult> {
    execute_sync(&backend, &app).await
}

#[tauri::command]
pub async fn cloud_sync_config(backend: State<'_, Backend>) -> AppResult<CloudSyncConfig> {
    Ok(get_config(&backend))
}

#[tauri::command]
pub async fn set_cloud_sync_config(
    config: CloudSyncConfig,
    backend: State<'_, Backend>,
) -> AppResult<()> {
    save_config(&backend, &config)
}
