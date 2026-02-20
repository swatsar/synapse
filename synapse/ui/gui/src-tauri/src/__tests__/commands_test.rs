//! Tests for Tauri Commands
//! 
//! All tests verify protocol_version="1.0" compliance

#[cfg(test)]
mod tests {
    use crate::commands::*;
    use crate::{PROTOCOL_VERSION, SPEC_VERSION};

    #[tokio::test]
    async fn test_get_config_returns_protocol_version() {
        let result = get_config().await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert_eq!(result.base.spec_version, SPEC_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_save_config_returns_protocol_version() {
        let config = SynapseConfig {
            language: "en".to_string(),
            mode: "supervised".to_string(),
            llm_providers: vec![],
            data_paths: std::collections::HashMap::new(),
            security_settings: SecuritySettings {
                require_approval_for_risk: 3,
                isolation_policy: "container".to_string(),
                audit_enabled: true,
                trusted_users: vec![],
            },
        };
        
        let result = save_config(config).await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_test_llm_connection_returns_protocol_version() {
        let result = test_llm_connection(
            "openai".to_string(),
            "test-key".to_string(),
            Some("https://api.openai.com/v1".to_string()),
            "gpt-4o".to_string(),
        ).await.unwrap();
        
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_get_skills_returns_protocol_version() {
        let result = get_skills().await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
        
        // Verify skills data structure
        if let Some(data) = &result.data {
            let skills: Vec<SkillInfo> = serde_json::from_value(data.clone()).unwrap();
            assert!(!skills.is_empty());
        }
    }

    #[tokio::test]
    async fn test_get_skill_details_returns_protocol_version() {
        let result = get_skill_details("skill-001".to_string()).await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_approve_skill_returns_protocol_version() {
        let result = approve_skill(
            "skill-001".to_string(),
            "test-user".to_string(),
        ).await.unwrap();
        
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_reject_skill_returns_protocol_version() {
        let result = reject_skill(
            "skill-001".to_string(),
            "Test reason".to_string(),
        ).await.unwrap();
        
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_archive_skill_returns_protocol_version() {
        let result = archive_skill("skill-001".to_string()).await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_get_system_metrics_returns_protocol_version() {
        let result = get_system_metrics().await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_get_llm_usage_returns_protocol_version() {
        let result = get_llm_usage().await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_get_skill_metrics_returns_protocol_version() {
        let result = get_skill_metrics(None).await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_get_capabilities_returns_protocol_version() {
        let result = get_capabilities(None).await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_get_audit_log_returns_protocol_version() {
        let result = get_audit_log(None, None, None).await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_get_security_settings_returns_protocol_version() {
        let result = get_security_settings().await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[tokio::test]
    async fn test_update_security_settings_returns_protocol_version() {
        let settings = SecuritySettings {
            require_approval_for_risk: 3,
            isolation_policy: "container".to_string(),
            audit_enabled: true,
            trusted_users: vec![],
        };
        
        let result = update_security_settings(settings).await.unwrap();
        assert_eq!(result.base.protocol_version, PROTOCOL_VERSION);
        assert!(result.success);
    }

    #[test]
    fn test_protocol_version_constant() {
        assert_eq!(PROTOCOL_VERSION, "1.0");
    }

    #[test]
    fn test_spec_version_constant() {
        assert_eq!(SPEC_VERSION, "3.1");
    }
}
