# Orinoco documentation

This page is the documentation starting point. If you are new to Orinoco, begin with the User and Setup Guide; if you are changing the project, read the Development and Contributing guides first.

## Choose your path

| I want to… | Read |
| --- | --- |
| Understand what works today and what is still planned | [Project Status](PROJECT_STATUS.md) |
| Install or use Orinoco (preview/staging only) | [User and Setup Guide](USER_GUIDE.md) |
| Install with standalone Docker Compose | [Docker Compose installation](DOCKER_COMPOSE.md) |
| Import and configure the Pterodactyl Egg | [Pterodactyl Egg](PTERODACTYL_EGG.md) |
| Run the controlled first Pterodactyl deployment test | [Test VPS Runbook](TEST_VPS_RUNBOOK.md) |
| Understand the application and deployment design | [Architecture](ARCHITECTURE.md) |
| Understand Panel-first management and its limits | [Panel Management](PANEL_MANAGEMENT.md) |
| Configure public/private network access | [Network Deployment](NETWORK_DEPLOYMENT.md) |
| Evaluate Welsh and English model quality | [Language Support](LANGUAGE_SUPPORT.md) |
| Develop and test locally | [Development](DEVELOPMENT.md) |
| Update an image or recover/roll back | [Updating and Rollback](UPDATING.md) |
| Review release blockers | [Pre-release Audit](PRE_RELEASE_AUDIT.md) |

For security reporting and handling sensitive information, see the repository's [Security Policy](../SECURITY.md). For contribution workflow and required documentation updates, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Deployment options

Orinoco uses the same Docker image in both supported deployment approaches:

- **Standalone Docker Compose:** Docker Engine and Compose manage the container directly. The operator is responsible for host networking, persistent storage, secrets, monitoring and backups.
- **Pterodactyl Panel:** Pterodactyl manages the Docker container through an Egg, server allocation, resource limits, console and Panel backup features. Wings and the Panel are not required for standalone Compose.

These are two ways to manage the same application, not separate editions. Keep the detailed steps in the deployment-specific guides and update both whenever shared image requirements change.

## Documentation conventions

Documentation must describe the repository as it exists, not as the roadmap hopes it will become.

- **Implemented** means code exists; it does not automatically mean production-ready.
- **Automated-test verified** means the named automated tests passed on the stated commit.
- **Staging tested** means the feature was exercised in a disposable environment representative of the deployment target.
- **Production verified** means the exact production configuration was tested and accepted.
- **Planned / design requirement** means the behaviour is agreed or documented but is not implemented.

When describing a release or test, record the exact image tag/digest, commit, environment and result where available. Never treat a green CI build as proof of a successful public image pull or live deployment.

Keep one canonical source for detailed instructions and link to it from other pages. When a setting changes, update its code/Egg definition, Compose template, user-facing guide, operator instructions and status notes together. Keep commands, variable names, defaults, paths, ports and supported versions synchronized.

Use British English spelling in user-facing documentation. Prefer short task-oriented headings, explain prerequisites before commands, and include a recovery or rollback note for operations that can affect persistent data. Clearly distinguish host/infrastructure administration from normal Panel-based Orinoco operation.

Do not include credentials, tokens, private data, real user logs or unredacted support bundles in examples. Use obvious placeholders such as YOUR_DOMAIN and explain which values an operator must replace.
