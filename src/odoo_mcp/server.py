"""Odoo MCP Server - generic CRUD, search, and schema exploration."""

import os
import xmlrpc.client

from fastmcp import FastMCP

from odoo_mcp.client import OdooClient

mcp = FastMCP("Odoo MCP Server")

_client: OdooClient | None = None


def _get_client() -> OdooClient:
    global _client
    if _client is None:
        _client = OdooClient(
            url=os.environ.get("ODOO_URL", "http://localhost:8069"),
            db=os.environ.get("ODOO_DB", "odoo"),
            username=os.environ.get("ODOO_USER", "admin"),
            password=os.environ.get("ODOO_PASSWORD", "admin"),
        )
    return _client


def _handle_error(e: Exception) -> str:
    if isinstance(e, ConnectionRefusedError):
        url = os.environ.get("ODOO_URL", "http://localhost:8069")
        return f"Cannot connect to Odoo at {url}"
    if isinstance(e, PermissionError):
        return str(e)
    if isinstance(e, xmlrpc.client.Fault):
        fault = e.faultString
        if "AccessError" in fault or "AccessDenied" in fault:
            return f"Access denied: {fault}"
        if "MissingError" in fault or "does not exist" in fault.lower():
            return f"Not found: {fault}"
        return f"Odoo error: {fault}"
    if isinstance(e, OSError):
        url = os.environ.get("ODOO_URL", "http://localhost:8069")
        return f"Cannot connect to Odoo at {url}: {e}"
    return f"Error: {e}"


@mcp.tool()
def search_read(
    model: str,
    domain: list | None = None,
    fields: list | None = None,
    limit: int = 80,
    offset: int = 0,
    order: str | None = None,
) -> list[dict] | str:
    """Search and read records from an Odoo model.

    Args:
        model: Model name, e.g. "res.partner"
        domain: Search domain, e.g. [["is_company","=",true]]. Defaults to [].
        fields: Fields to return, e.g. ["name","email"]. Defaults to all fields.
        limit: Max records to return (default 80).
        offset: Number of records to skip.
        order: Sort order, e.g. "name asc".
    """
    try:
        kwargs = {"limit": limit, "offset": offset}
        if fields is not None:
            kwargs["fields"] = fields
        if order is not None:
            kwargs["order"] = order
        return _get_client().execute_kw(
            model, "search_read", [domain or []], kwargs
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def create(model: str, values: dict) -> int | str:
    """Create a new record in an Odoo model.

    Args:
        model: Model name, e.g. "res.partner"
        values: Field values, e.g. {"name": "Test", "email": "test@example.com"}

    Returns:
        The ID of the newly created record.
    """
    try:
        return _get_client().execute_kw(model, "create", [values])
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def write(model: str, ids: list[int], values: dict) -> bool | str:
    """Update existing records in an Odoo model.

    Args:
        model: Model name, e.g. "res.partner"
        ids: List of record IDs to update.
        values: Field values to update, e.g. {"name": "New Name"}
    """
    try:
        return _get_client().execute_kw(model, "write", [ids, values])
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def unlink(model: str, ids: list[int]) -> bool | str:
    """Delete records from an Odoo model.

    Args:
        model: Model name, e.g. "res.partner"
        ids: List of record IDs to delete.
    """
    try:
        return _get_client().execute_kw(model, "unlink", [ids])
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def read(model: str, ids: list[int], fields: list | None = None) -> list[dict] | str:
    """Read records by their IDs from an Odoo model.

    Args:
        model: Model name, e.g. "res.partner"
        ids: List of record IDs to read.
        fields: Fields to return, e.g. ["name","email"]. Defaults to all fields.
    """
    try:
        kwargs = {}
        if fields is not None:
            kwargs["fields"] = fields
        return _get_client().execute_kw(model, "read", [ids], kwargs)
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def list_models(search_term: str | None = None) -> list[dict] | str:
    """List available Odoo models.

    Args:
        search_term: Optional filter for model name or technical name.

    Returns:
        List of dicts with "name" (display name) and "model" (technical name).
    """
    try:
        domain = []
        if search_term:
            domain = [
                "|",
                ["model", "ilike", search_term],
                ["name", "ilike", search_term],
            ]
        return _get_client().execute_kw(
            "ir.model",
            "search_read",
            [domain],
            {"fields": ["name", "model"], "order": "model asc"},
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def list_fields(model: str, attributes: list | None = None) -> dict | str:
    """Get field definitions for an Odoo model.

    Args:
        model: Model name, e.g. "res.partner"
        attributes: Optional list of field attributes to return,
            e.g. ["string","type","required","relation"].
            Defaults to all attributes.
    """
    try:
        kwargs = {}
        if attributes is not None:
            kwargs["attributes"] = attributes
        return _get_client().execute_kw(model, "fields_get", [], kwargs)
    except Exception as e:
        return _handle_error(e)


def main():
    mcp.run()
