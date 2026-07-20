# Plane Upstream Workflow

The `plane/` directory is maintained as a squashed git subtree of Plane
Community Edition.

```bash
git fetch plane-upstream
git subtree pull --prefix=plane plane-upstream <release-tag> --squash
```

After every update, run the Plane Django, MCP contract, web typecheck, web
build, and Mesh integration test suites before publishing a Mesh release.

Do not replace Plane CE files with Commercial Edition sources. Preserve Plane
copyright, SPDX, license, warranty, and modification notices.
