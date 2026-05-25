---
name: Release Checklist
about: Template for creating new releases
title: "Release v[VERSION]"
labels: ["release"]
assignees: []
---

## Release Checklist

### Pre-Release
- [ ] Update version in `pyproject.toml`
- [ ] Update version in `docker/Dockerfile`
- [ ] Update `CHANGELOG.md` with release notes
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Verify code coverage >= 90%
- [ ] Run security scans: `bandit`, `safety`, `semgrep`
- [ ] Build and test Docker image locally
- [ ] Generate SBOM for release

### Documentation
- [ ] Update API documentation
- [ ] Update installation guide
- [ ] Update quickstart guide
- [ ] Review and update README if needed

### CI/CD Verification
- [ ] All GitHub Actions workflows pass
- [ ] Docker build and push successful
- [ ] Security scan results reviewed
- [ ] Performance benchmarks acceptable

### Release Steps
- [ ] Create git tag: `git tag -a v[VERSION] -m "Release v[VERSION]"`
- [ ] Push tag: `git push origin v[VERSION]`
- [ ] Create GitHub Release with changelog
- [ ] Verify PyPI package published
- [ ] Verify Docker image pushed to registry

### Post-Release
- [ ] Announce release on communication channels
- [ ] Update documentation website
- [ ] Monitor for issues/bugs
- [ ] Plan next release cycle

### Rollback Plan (if needed)
- [ ] Identify issues requiring rollback
- [ ] Revert git tag and release
- [ ] Remove problematic packages from PyPI
- [ ] Communicate rollback to users

---
**Release Manager:** @[username]
**Target Date:** YYYY-MM-DD
**Actual Date:** YYYY-MM-DD
