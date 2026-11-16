# Release checklist

## Before tagging v7.5.0

- [ ] Review all source/config files for secrets, personal information and site/device identifiers.
- [ ] Commit the actual tested v7.5 source files (console_capture.py, discovery.py, core.py, word_export.py, requirements.txt, START.bat, command_groups.json).
- [ ] Make runtime data paths compatible with packaged executables; writable data must be outside the frozen bundle.
- [ ] Run Python syntax checks, application tests, and serial-port tests on Windows.
- [ ] Build portable EXE with a *Windows* runner using PyInstaller --onedir; test on a clean PC without Python.
- [ ] Verify discovery, repeated response probing, login prompts, command groups, Word export and COM Manager persistence.
- [ ] Produce versioned ZIP, checksum and release notes.
- [ ] Publish GitHub Release v7.5.0 only after these checks succeed.

## Proposed branching

- main: reviewed stable source
- feature/*: isolated changes, submitted by pull request
- tags vX.Y.Z: immutable stable releases

## Rollout

- Release v7.5.0 baseline first.
- Implement the external updater helper and update screen in v7.6.
- Start with opt-in/manual updates; consider automatic checks only after rollback tests.
