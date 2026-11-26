# Contributing

Thanks for your interest in Orinoco. The project is under active development, so careful bug reports, tests, documentation improvements and design feedback are all useful.

## Before making a change

1. Check existing issues and pull requests to avoid duplicating work.
2. For substantial changes, open an issue first to discuss the approach.
3. Keep changes focused and explain the problem they solve.
4. Do not include secrets, private user data, model files or generated runtime data.
5. Read the relevant architecture and feature documentation before changing security, persistence, deployment or account-isolation behaviour.

## Pull requests

A useful pull request should include:

- A clear summary of the change and its motivation.
- Any relevant issue number.
- Tests or verification steps performed, including commands and results.
- Documentation updates wherever behaviour, configuration, installation, operations or limitations change.
- Any migration, compatibility, rollback or resource-impact notes that an operator needs.

Do not describe planned, partially implemented or untested functionality as complete. Distinguish automated tests from live Panel, browser, hardware and model-quality testing.

## Documentation requirements

Documentation is part of the feature, not a follow-up task.

- Update the README or documentation index when navigation, project scope or the recommended entry point changes.
- Update the User Guide when a user-visible workflow or setting changes.
- Update the Pterodactyl Egg and Panel runbooks when an Egg variable, startup behaviour, image, allocation, persistence or operator procedure changes.
- Update Architecture and Project Status when component boundaries, security assumptions, feature status or release gates change.
- Update troubleshooting guidance when a new failure mode or recovery step is introduced.
- Keep commands, environment-variable names, defaults, ports, paths, model tags and version references aligned with the code and Egg.
- Link to one canonical detailed explanation rather than maintaining multiple conflicting copies.
- Mark host commands and infrastructure-only tasks clearly; routine Orinoco operation should remain Panel-first where supported.
- Label each capability accurately as implemented, automated-test verified, staging tested, production verified or planned.

## Code and design expectations

- Prefer secure defaults and least-privilege operation.
- Preserve strict separation between users' conversations, documents and memories.
- Enforce permissions in backend routes and persistence queries; hiding a UI control is not access control.
- Treat webpages, uploaded files, retrieved passages and model output as untrusted data.
- Keep optional integrations disabled unless explicitly configured.
- Avoid exposing internal model, database or administration ports.
- Preserve user data and administrator settings across upgrades; document migrations and rollback.
- Document resource requirements and behaviour on small VPS/container limits.
- Keep comments useful: explain why a security check, limit or non-obvious decision exists rather than restating the code.

## Verification

Run the relevant automated checks before requesting review. At minimum, run the focused tests for the changed area. For changes affecting the container or Egg, also run the repository's container smoke/validation workflow. Do not claim live Pterodactyl, public image pull, browser, Welsh/English model quality or hardware performance verification unless that exact test was performed.

## Licence

By contributing, you agree that your contributions are provided under the repository's MIT Licence.
