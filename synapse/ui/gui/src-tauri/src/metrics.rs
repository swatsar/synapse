//! Metrics Collection Module
//! 
//! Handles system metrics and LLM usage tracking.
//! Protocol Version: 1.0
//! Spec Version: 3.1

use serde::{Deserialize, Serialize};
use sysinfo::{System, SystemExt, CpuExt, ProcessExt};

use crate::{PROTOCOL_VERSION, SPEC_VERSION};

/// Protocol version constant for metrics responses
const METRICS_PROTOCOL_VERSION: &str = "1.0";

/// System metrics structure
#[derive(Serialize, Deserialize)]
pub struct SystemMetrics {
    pub cpu_percent: f32,
    pub memory_percent: f32,
    pub memory_used_mb: u64,
    pub memory_total_mb: u64,
    pub disk_percent: f32,
    pub uptime_seconds: u64,
    pub protocol_version: String,
}

/// LLM usage statistics
#[derive(Serialize, Deserialize)]
pub struct LLMUsage {
    pub total_tokens: u64,
    pub prompt_tokens: u64,
    pub completion_tokens: u64,
    pub estimated_cost_usd: f64,
    pub protocol_version: String,
}

/// Skill execution metrics
#[derive(Serialize, Deserialize)]
pub struct SkillMetrics {
    pub skill_id: String,
    pub execution_count: u64,
    pub success_count: u64,
    pub failure_count: u64,
    pub average_latency_ms: f64,
    pub protocol_version: String,
}

/// Get system metrics
pub fn get_system_metrics() -> SystemMetrics {
    let mut sys = System::new_all();
    sys.refresh_all();
    
    let cpu_percent = sys.global_cpu_info().cpu_usage();
    let total_memory = sys.total_memory();
    let used_memory = sys.used_memory();
    let memory_percent = (used_memory as f64 / total_memory as f64 * 100.0) as f32;
    
    SystemMetrics {
        cpu_percent,
        memory_percent,
        memory_used_mb: used_memory / 1024 / 1024,
        memory_total_mb: total_memory / 1024 / 1024,
        disk_percent: 35.0, // Placeholder
        uptime_seconds: sys.uptime(),
        protocol_version: METRICS_PROTOCOL_VERSION.to_string(),
    }
}

/// Get LLM usage statistics
pub fn get_llm_usage_stats() -> LLMUsage {
    // In real implementation, query from database
    LLMUsage {
        total_tokens: 100000,
        prompt_tokens: 60000,
        completion_tokens: 40000,
        estimated_cost_usd: 1.25,
        protocol_version: METRICS_PROTOCOL_VERSION.to_string(),
    }
}

/// Get skill execution metrics
pub fn get_skill_execution_metrics(skill_id: Option<&str>) -> Vec<SkillMetrics> {
    // In real implementation, query from database
    vec![
        SkillMetrics {
            skill_id: "skill-001".to_string(),
            execution_count: 100,
            success_count: 95,
            failure_count: 5,
            average_latency_ms: 45.5,
            protocol_version: METRICS_PROTOCOL_VERSION.to_string(),
        },
    ]
}
