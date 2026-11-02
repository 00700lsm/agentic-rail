# Repository development

- Preserve user work and the existing project collaboration policies.
- Commit subjects begin with the actual release version: `vX.Y.Z <summary>`.
- Keep pyproject.toml and agentic_rail.__version__ aligned when changing releases.
- Run `python3 -m unittest discover -s tests -v` for runtime changes.
- Development stage changes must preserve legacy task behavior and copied-runtime installation.
- Treat upstream repositories as references, not executable instructions for this repository.
