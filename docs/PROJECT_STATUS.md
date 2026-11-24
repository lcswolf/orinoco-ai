# Project Status

**Overall status: early implementation — custom interface, local model runtime, authentication, private chat, personal memory and document-library milestones committed.**

This page separates confirmed project decisions from implementation work. A planned feature is not considered implemented until code, tests and documentation exist.

## Implemented in the repository

- Public project repository and project documentation.
- Custom responsive Orinoco interface, served directly by FastAPI.
- Sign-in, secure signed sessions, CSRF-protected authentication and password changes.
- Administrator account management: create standard users, list users, suspend and reactivate accounts.
- Authenticated chat with local Ollama, saved per-user conversations and conversation switching.
- Single-generation queue, bounded model output and a short conversation context window.
- Per-user personal memories with automatic extraction, review, correction and deletion.
- Memory and document reference context is supplied separately from system instructions and treated as untrusted data.
- Private document uploads with per-account storage, bounded text extraction, download and deletion.
- Administrator-managed shared document library, read-only to standard users.
- Supported document formats: TXT, Markdown, PDF, DOCX, XLSX and PPTX, up to 10 MiB per file.
- SQLite FTS5 keyword retrieval from the current user's private documents and authorised shared documents.
- Explicit authenticated web-search workspace and SearXNG client, when an administrator configures and enables SearXNG.
- Liveness endpoint /healthz and local-model readiness endpoint /readyz.
- Non-root Pterodactyl runtime foundation, pinned Ollama CPU runtime, process supervision and automatic model download.
- Preview Pterodactyl 1.x Egg definition for Panel 1.13.0.
- Automated Python tests and frontend JavaScript syntax validation.

The latest completed GitHub Actions Python test run passed all 62 tests before the new SearXNG route tests were added. The container image build and runtime smoke test are still being validated. The image has not yet been published to GHCR or tested on a live Pterodactyl node.

## Confirmed direction

- Self-hosted assistant named Orinoco.
- Fully custom Orinoco web interface; Open WebUI will not be used as the main frontend.
- Local model inference; no external AI inference API is intended.
- Ollama is the inference runtime, currently pinned to version 0.40.18 in the image.
- Initial target is a modest Ubuntu 24.04 LTS VPS.
- Pterodactyl Panel 1.13.0 is the target deployment manager.
- Stable releases are preferred for updates.
- Curated model list: Qwen 2.5 0.5B, 1.5B and 3B; 1.5B is the default.
- Initial context target is 2048 tokens and one model request at a time.
- Discord text integration is planned; voice listening must require explicit activation.
- Private chats, memories and documents must be isolated per account.
- Public registration should be disabled by default.

## Not implemented yet

- Safe user-provided URL fetching and webpage summarisation.
- Search results automatically incorporated into chat answers.
- Conversation deletion/editing, pagination and streaming responses.
- Advanced semantic/vector document search and OCR for scanned PDFs.
- Discord integration and voice features.
- Production-ready image publication, live Egg import and Pterodactyl node deployment.
- Backup, restore, update and rollback tooling.
- Production security review, MFA, account recovery and server-side session revocation across all devices.

## Next implementation sequence

1. Finish the container image build and runtime smoke test.
2. Add safe URL opening and summarisation, with strict SSRF protections.
3. Add optional search-result context to chat.
4. Add backups, restore and update/rollback tooling.
5. Add Discord text integration; consider voice only after the core is stable.
6. Publish the stable image and import/test the finished Egg on the user's Panel.

## Resource assumptions

The previously discussed target VPS has 4 vCPU and 6 GiB RAM. The proposed initial container allowance is approximately 4 GiB RAM, with one model generation at a time. These are planning values, not validated minimum requirements. Automatic memory extraction uses a second local model request after a chat reply, so it increases response time and can be disabled with AUTO_SAVE_MEMORIES=false.

## Release policy

The intended update channel is stable. Releases should be versioned, documented and tested. Database migrations must be backed up and have a documented recovery path.
