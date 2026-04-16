# AI Governance for This Repository
 
## 1. Scope
This repository permits cursor for engineering assistance within defined guardrails.
The goal is to improve review, understanding, testing, and documentation without allowing uncontrolled execution or operational change.
 
## 2. Approved use cases
The following uses are approved by default:
 
- Code review
- Refactoring suggestions
- Unit test generation
- Documentation generation
- Architecture explanation
- Dependency review
- Repo-wide analysis, if it does not require reading secrets or performing external actions
 
## 3. Controlled use cases
The following are allowed only as analysis, not as execution:
 
- Terraform review
- CI/CD config review
- Kubernetes manifest review
- Cost/configuration review
- Log/config analysis
 
For these cases, cursor may explain findings and suggest changes, but must not perform apply/deploy/admin operations.
 
## 4. Forbidden use cases
The following are prohibited in this repository:
 
- Deployment to any environment
- Database migration execution
- Cloud admin actions
- Kubernetes admin actions
- Reading secrets or credentials
- Downloading or executing remote content
- Automatic Git write operations such as push, merge, or rebase
 
## 5. Permissions posture
This repository uses a project-level cursor policy with the following posture:
 
- Read access is broadly allowed for repo contents
- File edits require explicit approval
- Sensitive files and destructive/admin commands are denied
 
## 6. Local overrides
Developers may have local cursor settings on their machines.
Those local settings are not authoritative for project governance and must not be relied on as a control.
The repository policy is the shared team baseline, but stronger enforcement requires managed settings and/or network controls.
 
## 7. Approved project files
The following files define the shared project baseline:
 
- `.cursor/settings.json`
- `cursor.md`
- `docs/ai-governance.md`
 
Changes to these files require owner approval.
 
## 8. Change control
Any pull request that changes cursor policy or governance files must be reviewed by:
 
- Platform owner
- Security owner, if available
 
Recommended controls:
- CODEOWNERS protection
- Required pull request approvals
- CI validation of forbidden patterns
 
## 9. Incident handling
If cursor is observed attempting forbidden behavior:
1. Stop the session.
2. Preserve the prompt/output evidence.
3. Open a security or platform incident ticket.
4. Tighten repo policy and CI checks as needed.
 
## 10. Minimum standard for contributors
Contributors using cursor in this repository must:
- follow the shared project policy
- avoid adding unapproved skills or hooks
- avoid committing local override files
- avoid bypassing review or approval gates
 
 
 