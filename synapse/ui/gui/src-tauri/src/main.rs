//! Synapse Configurator - Tauri Backend
//! 
//! Cross-platform GUI configurator for Synapse autonomous agent platform.
//! Protocol Version: 1.0
//! Spec Version: 3.1

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

mod commands;
mod wizard;
mod skills;
mod metrics;
mod security;

use tauri::Manager;

/// Protocol version for all responses
pub const PROTOCOL_VERSION: &str = "1.0";
pub const SPEC_VERSION: &str = "3.1";

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            #[cfg(debug_assertions)]
            {
                let window = app.get_window("main").unwrap();
                window.open_devtools();
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // Configuration commands
            commands::get_config,
            commands::save_config,
            commands::test_llm_connection,
            
            // Skill management commands
            commands::get_skills,
            commands::get_skill_details,
            commands::approve_skill,
            commands::reject_skill,
            commands::archive_skill,
            
            // Metrics commands
            commands::get_system_metrics,
            commands::get_llm_usage,
            commands::get_skill_metrics,
            
            // Security commands
            commands::get_capabilities,
            commands::get_audit_log,
            commands::get_security_settings,
            commands::update_security_settings,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
