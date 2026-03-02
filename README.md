# suncombo-odoo-mcp

MCP Server for Odoo ERP - generic CRUD, search, and schema exploration.

## Publish to PyPI

1. Update `version` in `pyproject.toml`
2. Build and publish:

```bash
rm -rf dist && uv build
uv publish
```

Credentials are configured in `~/.pypirc`.
