//! Configuration Wizard Module
//! 
//! Handles the initial setup wizard for Synapse configuration.
//! Protocol Version: 1.0
//! Spec Version: 3.1

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::{PROTOCOL_VERSION, SPEC_VERSION};

/// Protocol version constant for wizard responses
const WIZARD_PROTOCOL_VERSION: &str = "1.0";

/// Wizard step definition
#[derive(Serialize, Deserialize, Clone)]
pub struct WizardStep {
    pub id: String,
    pub title: String,
    pub description: String,
    pub is_complete: bool,
    pub protocol_version: String,
}

/// Get wizard steps
pub fn get_wizard_steps() -> Vec<WizardStep> {
    vec![
        WizardStep {
            id: "welcome".to_string(),
            title: "Welcome".to_string(),
            description: "Welcome to Synapse Configurator".to_string(),
            is_complete: false,
            protocol_version: WIZARD_PROTOCOL_VERSION.to_string(),
        },
        WizardStep {
            id: "language".to_string(),
            title: "Language Selection".to_string(),
            description: "Choose your preferred language".to_string(),
            is_complete: false,
            protocol_version: WIZARD_PROTOCOL_VERSION.to_string(),
        },
        WizardStep {
            id: "llm".to_string(),
            title: "LLM Provider".to_string(),
            description: "Configure your LLM provider".to_string(),
            is_complete: false,
            protocol_version: WIZARD_PROTOCOL_VERSION.to_string(),
        },
        WizardStep {
            id: "storage".to_string(),
            title: "Storage Paths".to_string(),
            description: "Configure data storage locations".to_string(),
            is_complete: false,
            protocol_version: WIZARD_PROTOCOL_VERSION.to_string(),
        },
        WizardStep {
            id: "security".to_string(),
            title: "Security Mode".to_string(),
            description: "Configure security settings".to_string(),
            is_complete: false,
            protocol_version: WIZARD_PROTOCOL_VERSION.to_string(),
        },
        WizardStep {
            id: "review".to_string(),
            title: "Review".to_string(),
            description: "Review and apply configuration".to_string(),
            is_complete: false,
            protocol_version: WIZARD_PROTOCOL_VERSION.to_string(),
        },
    ]
}

/// Supported languages
pub fn get_supported_languages() -> Vec<HashMap<String, String>> {
    vec![
        HashMap::from([
            ("code".to_string(), "en".to_string()),
            ("name".to_string(), "English".to_string()),
            ("protocol_version".to_string(), WIZARD_PROTOCOL_VERSION.to_string()),
        ]),
        HashMap::from([
            ("code".to_string(), "ru".to_string()),
            ("name".to_string(), "Русский".to_string()),
            ("protocol_version".to_string(), WIZARD_PROTOCOL_VERSION.to_string()),
        ]),
    ]
}

/// Supported LLM providers
pub fn get_supported_llm_providers() -> Vec<HashMap<String, String>> {
    vec![
        HashMap::from([
            ("id".to_string(), "openai".to_string()),
            ("name".to_string(), "OpenAI".to_string()),
            ("models".to_string(), "gpt-4o,gpt-4-turbo,gpt-3.5-turbo".to_string()),
            ("protocol_version".to_string(), WIZARD_PROTOCOL_VERSION.to_string()),
        ]),
        HashMap::from([
            ("id".to_string(), "anthropic".to_string()),
            ("name".to_string(), "Anthropic".to_string()),
            ("models".to_string(), "claude-3.5-sonnet,claude-3-opus".to_string()),
            ("protocol_version".to_string(), WIZARD_PROTOCOL_VERSION.to_string()),
        ]),
        HashMap::from([
            ("id".to_string(), "ollama".to_string()),
            ("name".to_string(), "Ollama (Local)".to_string()),
            ("models".to_string(), "llama3,mistral,codellama".to_string()),
            ("protocol_version".to_string(), WIZARD_PROTOCOL_VERSION.to_string()),
        ]),
    ]
}
