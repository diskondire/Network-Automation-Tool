# Console Capture v7.6 — updater design (proposal)

## Distribution decision

- Build a Windows portable **one-folder** executable with PyInstaller on a Windows GitHub Actions runner.
- Publish **stable** versions as immutable GitHub Releases with a versioned ZIP and SHA-256 checksum file.
- Do **not** update by pulling branch HEAD, individual .py files or unverified archives.
- Development branches and pull requests are not release channels.
- This document is a design, not an implemented updater.

## Application UI

- Help > Check for Updates runs an explicit check.
- Optional startup check: show a passive notification; never install automatically.
- Show installed version, available version, release notes, and download size.
- Require user approval before applying updates.

## Safe update procedure

1. Query the configured release feed over HTTPS. Validate that release is from the expected repository and is not a draft/prerelease.
2. Compare semantic versions. Never downgrade without deliberate user action.
3. Download an exact versioned release asset to a temporary directory, imposing size/time limits.
4. Verify SHA-256 and the trust of the release metadata. A checksum **hosted next to the archive alone does not prevent repository compromise**. Consider code signing for stronger publisher identity.
5. Ensure all console capture jobs are idle and close serial ports gracefully. Prompt if there is unsaved output.
6. Start a separate updater helper (main executable cannot replace its own running files).
7. Stage the new release; retain one previous complete version for rollback.
8. Atomically switch the install directory (where possible), launch the new version and confirm a successful startup.
9. On failure, restore the previous version and preserve application data.

## User data rules

- Put preferences, command sets, captures and reports under an appropriate per-user data location, not alongside packaged executable binaries.
- Migrate data schemas explicitly and keep backups. Never overwrite user-authored command sets.
- Exclude passwords and captured console output from release artifacts and logs.
- Warn users before migrating from source-folder settings.

## Public vs private releases

- Current repository visibility is **public**. No personal network inventories, credentials or customer data may be committed.
- If the repository becomes private, anonymous GitHub release checks/downloads will not work. Do not embed a GitHub personal access token in a distributed EXE; use an approved authenticated delivery method.

## Acceptance criteria

- Upgrade from 7.5.0 to a test 7.6.0 on a clean Windows PC without Python installed.
- In-use capture blocks installation; cancellation leaves app unchanged.
- Download interruption, corrupt checksum, and failed launch cause no data loss.
- Rollback restores executable, while preserving user captures and command sets.
- No security prompts are bypassed and no passwords appear in debug logs.
