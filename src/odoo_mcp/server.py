"""Odoo MCP Server - generic CRUD, search, and schema exploration."""

import json
import os
import xmlrpc.client
from typing import Annotated, Any

from pydantic import BeforeValidator
from fastmcp import FastMCP


def _parse_json_str(v: Any) -> Any:
    """Coerce JSON strings to Python objects (LLMs sometimes pass arrays as strings)."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (json.JSONDecodeError, ValueError):
            return v
    return v


JsonList = Annotated[list, BeforeValidator(_parse_json_str)]
JsonDict = Annotated[dict, BeforeValidator(_parse_json_str)]

from odoo_mcp.client import OdooClient

mcp = FastMCP(
    "Odoo MCP Server",
    instructions="""\
Odoo ERP via XML-RPC. Always specify fields in search_read to reduce payload.

Gotchas:
- create already wraps values in a list internally — pass a plain dict, NOT [dict].
- execute_method args is a list of positional args: e.g. copy([10209]) → args=[[10209]], write([id], vals) → args=[[id], {"name": "X"}].

Domain syntax: [["field", "op", value]] — op: =, !=, like, ilike, in, not in, >, <, >=, <=, =?, child_of
  Logic: "&" (AND, default), "|" (OR), "!" (NOT) as prefix operators.
  OR example: ["|", ["name", "ilike", "gold"], ["name", "ilike", "silver"]]
  AND+OR: ["&", ["active", "=", true], "|", ["name", "ilike", "a"], ["name", "ilike", "b"]]

Common patterns:
  Translate: execute_method model="product.template" method="write" args=[[id], {"name": "中文名"}] kwargs={"context": {"lang": "zh_TW"}}
  Copy: execute_method model="product.template" method="copy" args=[[id]] kwargs={"default": {"name": "New"}}
  Confirm SO: execute_method model="sale.order" method="action_confirm" args=[[id]]
""",
)

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


def _handle_error(e: Exception) -> dict[str, str]:
    if isinstance(e, ConnectionRefusedError):
        url = os.environ.get("ODOO_URL", "http://localhost:8069")
        return {"error": f"Cannot connect to Odoo at {url}"}
    if isinstance(e, PermissionError):
        return {"error": str(e)}
    if isinstance(e, xmlrpc.client.Fault):
        fault = e.faultString
        if "AccessError" in fault or "AccessDenied" in fault:
            return {"error": f"Access denied: {fault}"}
        if "MissingError" in fault or "does not exist" in fault.lower():
            return {"error": f"Not found: {fault}"}
        return {"error": f"Odoo error: {fault}"}
    if isinstance(e, OSError):
        url = os.environ.get("ODOO_URL", "http://localhost:8069")
        return {"error": f"Cannot connect to Odoo at {url}: {e}"}
    return {"error": f"Error: {e}"}


@mcp.tool()
def search_read(
    model: str,
    domain: JsonList | None = None,
    fields: JsonList | None = None,
    limit: int = 80,
    offset: int = 0,
    order: str | None = None,
) -> dict[str, Any]:
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
        result = _get_client().execute_kw(
            model, "search_read", [domain or []], kwargs
        )
        return {"result": result}
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def create(model: str, values: JsonDict) -> dict[str, Any]:
    """Create a new record in an Odoo model.

    Args:
        model: Model name, e.g. "res.partner"
        values: Field values, e.g. {"name": "Test", "email": "test@example.com"}

    Returns:
        A dict with either:
            - "result": the ID of the newly created record on success.
            - "error": an error message string if the operation fails.
    """
    try:
        result = _get_client().execute_kw(model, "create", [values])
        return {"result": result}
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def write(model: str, ids: JsonList, values: JsonDict) -> dict[str, Any]:
    """Update existing records in an Odoo model.

    Args:
        model: Model name, e.g. "res.partner"
        ids: List of record IDs to update.
        values: Field values to update, e.g. {"name": "New Name"}
    """
    try:
        result = _get_client().execute_kw(model, "write", [ids, values])
        return {"result": result}
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def unlink(model: str, ids: JsonList) -> dict[str, Any]:
    """Delete records from an Odoo model.

    Args:
        model: Model name, e.g. "res.partner"
        ids: List of record IDs to delete.
    """
    try:
        result = _get_client().execute_kw(model, "unlink", [ids])
        return {"result": result}
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def read(model: str, ids: JsonList, fields: JsonList | None = None) -> dict[str, Any]:
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
        result = _get_client().execute_kw(model, "read", [ids], kwargs)
        return {"result": result}
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def list_models(search_term: str | None = None) -> dict[str, Any]:
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
        result = _get_client().execute_kw(
            "ir.model",
            "search_read",
            [domain],
            {"fields": ["name", "model"], "order": "model asc"},
        )
        return {"result": result}
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def list_fields(model: str, attributes: JsonList | None = None) -> dict[str, Any]:
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
        result = _get_client().execute_kw(model, "fields_get", [], kwargs)
        return {"result": result}
    except Exception as e:
        return _handle_error(e)


@mcp.tool()
def execute_method(
    model: str,
    method: str,
    args: JsonList | None = None,
    kwargs: JsonDict | None = None,
) -> dict[str, Any]:
    """Execute any public method on an Odoo model via XML-RPC.

    Odoo only allows calling public methods (not starting with '_').
    This tool covers workflow actions, business logic, and any method
    not already provided by the other CRUD tools.

    Args:
        model: Model name, e.g. "sale.order"
        method: Public method name, e.g. "action_confirm"
        args: Positional arguments as a list. Typically [record_ids, ...].
            e.g. [[1, 2]] to call method on records 1 and 2.
        kwargs: Keyword arguments as a dict, e.g. {"force": true}.

    Examples:
        Confirm a sale order:
            model="sale.order", method="action_confirm", args=[[5]]
        Check access rights:
            model="res.partner", method="check_access_rights", args=["write"], kwargs={"raise_exception": false}
        Call onchange:
            model="sale.order", method="onchange", args=[[1], {"partner_id": 3}, ["partner_id"], {"partner_id": ""}]
    """
    try:
        result = _get_client().execute_kw(model, method, args, kwargs)
        return {"result": result if result is not None else True}
    except Exception as e:
        return _handle_error(e)


def main():
    mcp.run()
