# Release Template

## Release Checklist

### Pre-Release
- [ ] Run full test suite: `pytest tests/ -v --cov=synapse`
- [ ] Verify code coverage >= 90%
- [ ] Run security scans: `bandit -r synapse/`, `safety check`
- [ ] Run type checking: `mypy synapse/`
- [ ] Run linter: `ruff check synapse/`
- [ ] Update CHANGELOG.md with release notes
- [ ] Update version in pyproject.toml
- [ ] Update version in docker/Dockerfile labels
- [ ] Update Helm Chart version in helm/synapse/Chart.yaml
- [ ] Generate SBOM: `syft packages . -o spdx-json=sbom.spdx.json`

### Release Process
1. Create release branch: `git checkout -b release/v3.4.2`
2. Update version numbers across all files
3. Run final CI/CD pipeline
4. Merge to main: `git checkout main && git merge release/v3.4.2`
5. Tag release: `git tag -a v3.4.2 -m "Release version 3.4.2"`
6. Push tags: `git push origin v3.4.2`
7. Create GitHub Release with:
   - Release notes from CHANGELOG
   - Attached SBOM file
   - Docker image auto-built via workflow

### Post-Release
- [ ] Verify Docker images published to GHCR
- [ ] Verify Helm chart published
- [ ] Update documentation site
- [ ] Announce release on communication channels
- [ ] Monitor for issues in first 24 hours

## Release Notes Template

```markdown
## [Version] - YYYY-MM-DD

### Added
- New features and capabilities

### Changed
- Changes to existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security improvements and fixes

### Dependencies
- Updated dependencies:
  - package-name: old-version → new-version
```

## Version Numbering

Synapse follows [Semantic Versioning](https://semver.org/):
- **MAJOR**: Incompatible API changes
- **MINOR**: Backward-compatible functionality additions
- **PATCH**: Backward-compatible bug fixes

Example: `3.4.1` → MAJOR=3, MINOR=4, PATCH=1
