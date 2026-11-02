//! Tauri Commands for Synapse Configurator
//! 
//! All responses include protocol_version="1.0" and spec_version="3.1"

use serde::{Deserialize, Serialize};use std::collections::HashMap;
use chrono::{DateTime, Utc};

use crate::{PROTOCOL_VERSION, SPEC_VERSION};

// ============================================================================
// Response Wrappers
// ============================================================================

/// Base response with protocol versioning
#[derive(Serialize, Deserialize)]
pub struct BaseResponse {
    pub protocol_version: String,
    pub spec_version: String,
}

impl Default for BaseResponse {
    fn default() -> Self {
        Self {
            protocol_version: PROTOCOL_VERSION.to_string(),
            spec_version: SPEC_VERSION.to_string(),
        }
    }
}

/// Generic response wrapper
#[derive(Serialize, Deserialize)]
pub struct ApiResponse {
    #[serde(flatten)]
    pub base: BaseResponse,
    pub success: bool,
    pub data: Option<serde_json::Value>,
    pub error: Option<String>,
}

impl ApiResponse {
    pub fn success(data: serde_json::Value) -> Self {
        Self {
            base: BaseResponse::default(),
            success: true,
            data: Some(data),
            error: None,
        }
    }
    
    pub fn error(message: &str) -> Self {
        Self {
            base: BaseResponse::default(),
            success: false,
            data: None,
            error: Some(message.to_string()),
        }
    }
}

// ============================================================================
// Configuration Commands
// ============================================================================

/// LLM Provider configuration
#[derive(Serialize, Deserialize, Clone)]
pub struct LLMProviderConfig {
    pub name: String,
    pub provider_type: String,
    pub api_key: Option<String>,
    pub base_url: Option<String>,
    pub model: String,
    pub priority: u8,
    pub is_active: bool,
}

/// Full configuration
#[derive(Serialize, Deserialize, Clone)]
pub struct SynapseConfig {
    pub language: String,
    pub mode: String,
    pub llm_providers: Vec<LLMProviderConfig>,
    pub data_paths: HashMap<String, String>,
    pub security_settings: SecuritySettings,
}

/// Security settings
#[derive(Serialize, Deserialize, Clone)]
pub struct SecuritySettings {
    pub require_approval_for_risk: u8,
    pub isolation_policy: String,
    pub audit_enabled: bool,
    pub trusted_users: Vec<String>,
}

/// Get current configuration
#[tauri::command]
pub async fn get_config() -> Result<ApiResponse, String> {
    // In production, this would load from config file
    let config = SynapseConfig {
        language: "en".to_string(),
        mode: "supervised".to_string(),
        llm_providers: vec![
            LLMProviderConfig {
                name: "OpenAI GPT-4".to_string(),
                provider_type: "openai".to_string(),
                api_key: None,
                base_url: Some("https://api.openai.com/v1".to_string()),
                model: "gpt-4o".to_string(),
                priority: 1,
                is_active: true,
            },
        ],
        data_paths: {
            let mut paths = HashMap::new();
            paths.insert("config".to_string(), "~/.synapse/config".to_string());
            paths.insert("skills".to_string(), "~/.synapse/skills".to_string());
            paths.insert("memory".to_string(), "~/.synapse/memory".to_string());
            paths
        },
        security_settings: SecuritySettings {
            require_approval_for_risk: 3,
            isolation_policy: "container".to_string(),
            audit_enabled: true,
            trusted_users: vec![],
        },
    };
    
    Ok(ApiResponse::success(serde_json::to_value(config).unwrap()))
}

/// Save configuration
#[tauri::command]
pub async fn save_config(config: SynapseConfig) -> Result<ApiResponse, String> {
    // In production, this would save to config file
    // Validate protocol version
    
    Ok(ApiResponse::success(serde_json::json!({
        "saved": true,
        "message": "Configuration saved successfully"
    })))
}

/// Test LLM connection
#[tauri::command]
pub async fn test_llm_connection(
    provider_type: String,
    api_key: String,
    base_url: Option<String>,
    model: String,
) -> Result<ApiResponse, String> {
    // In production, this would make a test API call
    let success = !api_key.is_empty();
    
    Ok(ApiResponse::success(serde_json::json!({
        "connected": success,
        "provider": provider_type,
        "model": model,
        "message": if success { "Connection successful" } else { "Invalid API key" }
    })))
}

// ============================================================================
// Skill Management Commands
// ============================================================================

/// Skill status
#[derive(Serialize, Deserialize, Clone)]
pub struct SkillInfo {
    pub id: String,
    pub name: String,
    pub version: String,
    pub status: String,
    pub trust_level: String,
    pub risk_level: u8,
    pub isolation_type: String,
    pub required_capabilities: Vec<String>,
    pub created_at: DateTime<Utc>,
    pub last_used: Option<DateTime<Utc>>,
}

/// Get all skills
#[tauri::command]
pub async fn get_skills() -> Result<ApiResponse, String> {
    let skills: Vec<SkillInfo> = vec![
        SkillInfo {
            id: "skill-001".to_string(),
            name: "read_file".to_string(),
            version: "1.0.0".to_string(),
            status: "active".to_string(),
            trust_level: "trusted".to_string(),
            risk_level: 1,
            isolation_type: "subprocess".to_string(),
            required_capabilities: vec!["fs:read".to_string()],
            created_at: Utc::now(),
            last_used: Some(Utc::now()),
        },
        SkillInfo {
            id: "skill-002".to_string(),
            name: "write_file".to_string(),
            version: "1.0.0".to_string(),
            status: "active".to_string(),
            trust_level: "verified".to_string(),
            risk_level: 2,
            isolation_type: "container".to_string(),
            required_capabilities: vec!["fs:write".to_string()],
            created_at: Utc::now(),
            last_used: Some(Utc::now()),
        },
        SkillInfo {
            id: "skill-003".to_string(),
            name: "web_search".to_string(),
            version: "1.0.0".to_string(),
            status: "pending".to_string(),
            trust_level: "unverified".to_string(),
            risk_level: 3,
            isolation_type: "container".to_string(),
            required_capabilities: vec!["network:http".to_string()],
            created_at: Utc::now(),
            last_used: None,
        },
    ];
    
    Ok(ApiResponse::success(serde_json::to_value(skills).unwrap()))
}

/// Get skill details
#[tauri::command]
pub async fn get_skill_details(skill_id: String) -> Result<ApiResponse, String> {
    // In production, this would load from skill registry
    Ok(ApiResponse::success(serde_json::json!({
        "id": skill_id,
        "name": "example_skill",
        "version": "1.0.0",
        "description": "Example skill for demonstration",
        "author": "synapse_core",
        "inputs": {
            "query": {"type": "string", "required": true}
        },
        "outputs": {
            "result": {"type": "string"}
        },
        "required_capabilities": ["fs:read"],
        "risk_level": 2,
        "trust_level": "verified",
        "isolation_type": "container"
    })))
}

/// Approve a skill
#[tauri::command]
pub async fn approve_skill(skill_id: String, approved_by: String) -> Result<ApiResponse, String> {
    Ok(ApiResponse::success(serde_json::json!({
        "skill_id": skill_id,
        "approved": true,
        "approved_by": approved_by,
        "approved_at": Utc::now().to_rfc3339()
    })))
}

/// Reject a skill
#[tauri::command]
pub async fn reject_skill(skill_id: String, reason: String) -> Result<ApiResponse, String> {
    Ok(ApiResponse::success(serde_json::json!({
        "skill_id": skill_id,
        "rejected": true,
        "reason": reason,
        "rejected_at": Utc::now().to_rfc3339()
    })))
}

/// Archive a skill
#[tauri::command]
pub async fn archive_skill(skill_id: String) -> Result<ApiResponse, String> {
    Ok(ApiResponse::success(serde_json::json!({
        "skill_id": skill_id,
        "archived": true,
        "archived_at": Utc::now().to_rfc3339()
    })))
}

// ============================================================================
// Metrics Commands
// ============================================================================

/// System metrics
#[derive(Serialize, Deserialize)]
pub struct SystemMetrics {
    pub cpu_percent: f64,
    pub memory_percent: f64,
    pub memory_used_mb: u64,
    pub memory_total_mb: u64,
    pub disk_percent: f64,
    pub uptime_seconds: u64,
}

/// LLM usage metrics
#[derive(Serialize, Deserialize)]
pub struct LLMUsageMetrics {
    pub total_tokens: u64,
    pub prompt_tokens: u64,
    pub completion_tokens: u64,
    pub estimated_cost_usd: f64,
    pub provider_distribution: HashMap<String, u64>,
}

/// Skill execution metrics
#[derive(Serialize, Deserialize)]
pub struct SkillMetrics {
    pub skill_name: String,
    pub total_executions: u64,
    pub successful_executions: u64,
    pub failed_executions: u64,
    pub avg_latency_ms: f64,
    pub success_rate: f64,
}

/// Get system metrics
#[tauri::command]
pub async fn get_system_metrics() -> Result<ApiResponse, String> {
    let metrics = SystemMetrics {
        cpu_percent: 25.5,
        memory_percent: 45.2,
        memory_used_mb: 1843,
        memory_total_mb: 4096,
        disk_percent: 35.0,
        uptime_seconds: 86400,
    };
    
    Ok(ApiResponse::success(serde_json::to_value(metrics).unwrap()))
}

/// Get LLM usage
#[tauri::command]
pub async fn get_llm_usage() -> Result<ApiResponse, String> {
    let mut provider_dist = HashMap::new();
    provider_dist.insert("openai".to_string(), 75000u64);
    provider_dist.insert("anthropic".to_string(), 25000u64);
    
    let metrics = LLMUsageMetrics {
        total_tokens: 100000,
        prompt_tokens: 60000,
        completion_tokens: 40000,
        estimated_cost_usd: 1.25,
        provider_distribution: provider_dist,
    };
    
    Ok(ApiResponse::success(serde_json::to_value(metrics).unwrap()))
}

/// Get skill metrics
#[tauri::command]
pub async fn get_skill_metrics(skill_name: Option<String>) -> Result<ApiResponse, String> {
    let metrics = vec![
        SkillMetrics {
            skill_name: "read_file".to_string(),
            total_executions: 150,
            successful_executions: 148,
            failed_executions: 2,
            avg_latency_ms: 45.5,
            success_rate: 98.67,
        },
        SkillMetrics {
            skill_name: "write_file".to_string(),
            total_executions: 75,
            successful_executions: 73,
            failed_executions: 2,
            avg_latency_ms: 62.3,
            success_rate: 97.33,
        },
    ];
    
    if let Some(name) = skill_name {
        let filtered: Vec<_> = metrics.into_iter().filter(|m| m.skill_name == name).collect();
        Ok(ApiResponse::success(serde_json::to_value(filtered).unwrap()))
    } else {
        Ok(ApiResponse::success(serde_json::to_value(metrics).unwrap()))
    }
}

// ============================================================================
// Security Commands
// ============================================================================

/// Capability token info
#[derive(Serialize, Deserialize)]
pub struct CapabilityInfo {
    pub token_id: String,
    pub user_id: String,
    pub capabilities: Vec<String>,
    pub issued_at: DateTime<Utc>,
    pub expires_at: Option<DateTime<Utc>>,
    pub is_valid: bool,
}

/// Audit log entry
#[derive(Serialize, Deserialize)]
pub struct AuditLogEntry {
    pub id: String,
    pub timestamp: DateTime<Utc>,
    pub action: String,
    pub user_id: String,
    pub result: String,
    pub details: Option<String>,
}

/// Get capabilities
#[tauri::command]
pub async fn get_capabilities(user_id: Option<String>) -> Result<ApiResponse, String> {
    let capabilities = vec![
        CapabilityInfo {
            token_id: "cap-001".to_string(),
            user_id: "admin".to_string(),
            capabilities: vec!["fs:read".to_string(), "fs:write".to_string(), "network:http".to_string()],
            issued_at: Utc::now(),
            expires_at: None,
            is_valid: true,
        },
    ];
    
    Ok(ApiResponse::success(serde_json::to_value(capabilities).unwrap()))
}

/// Get audit log
#[tauri::command]
pub async fn get_audit_log(
    limit: Option<u32>,
    action_filter: Option<String>,
    user_filter: Option<String>,
) -> Result<ApiResponse, String> {
    let entries = vec![
        AuditLogEntry {
            id: "audit-001".to_string(),
            timestamp: Utc::now(),
            action: "skill_execute".to_string(),
            user_id: "admin".to_string(),
            result: "success".to_string(),
            details: Some("Executed read_file skill".to_string()),
        },
        AuditLogEntry {
            id: "audit-002".to_string(),
            timestamp: Utc::now(),
            action: "config_update".to_string(),
            user_id: "admin".to_string(),
            result: "success".to_string(),
            details: Some("Updated LLM provider settings".to_string()),
        },
    ];
    
    Ok(ApiResponse::success(serde_json::to_value(entries).unwrap()))
}

/// Get security settings
#[tauri::command]
pub async fn get_security_settings() -> Result<ApiResponse, String> {
    Ok(ApiResponse::success(serde_json::json!({
        "require_approval_for_risk": 3,
        "isolation_policy": "container",
        "audit_enabled": true,
        "trusted_users": [],
        "rate_limit_per_minute": 60,
        "session_timeout_minutes": 30
    })))
}

/// Update security settings
#[tauri::command]
pub async fn update_security_settings(settings: SecuritySettings) -> Result<ApiResponse, String> {
    Ok(ApiResponse::success(serde_json::json!({
        "updated": true,
        "settings": settings
    })))
}
