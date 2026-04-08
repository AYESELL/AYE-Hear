---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-04-08
---

# AYE Hear Agent Roles

| Role              | Focus                                          |
| ----------------- | ---------------------------------------------- |
| AYEHEAR_ARCHITECT | Architecture, ADRs, design review, governance  |
| AYEHEAR_DEVELOPER | Implementation, testing (≥75%), code quality   |
| AYEHEAR_DEVOPS    | CI/CD, Windows installer, build pipeline       |
| AYEHEAR_QA        | Test strategy, quality gates, hardware testing |
| AYEHEAR_SECURITY  | Privacy, offline-first, credentials, GDPR      |

### Task Routing

- Architecture? → AYEHEAR_ARCHITECT
- Security/privacy? → AYEHEAR_ARCHITECT + AYEHEAR_SECURITY
- Implementation? → AYEHEAR_DEVELOPER
- Installer/CI-CD? → AYEHEAR_DEVOPS
- Test strategy? → AYEHEAR_QA

## Local Agent Files

Repository-local individual agents are stored under:

- .github/agents/ayehear-architect.agent.md
- .github/agents/ayehear-developer.agent.md
- .github/agents/ayehear-devops.agent.md
- .github/agents/ayehear-qa.agent.md
- .github/agents/ayehear-security.agent.md

---

**Owner:** AYEHEAR_ARCHITECT
