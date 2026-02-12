"""Odoo XML-RPC client with connection caching and error handling."""

import xmlrpc.client


class OdooClient:
    """Wraps Odoo XML-RPC endpoints with lazy authentication and caching."""

    def __init__(self, url: str, db: str, username: str, password: str):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password
        self._uid: int | None = None
        self._models: xmlrpc.client.ServerProxy | None = None

    def _authenticate(self) -> int:
        """Authenticate via /xmlrpc/2/common and cache uid."""
        if self._uid is not None:
            return self._uid
        common = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/common", allow_none=True
        )
        uid = common.authenticate(self.db, self.username, self.password, {})
        if not uid:
            raise PermissionError(
                f"Authentication failed for user '{self.username}' on database '{self.db}'"
            )
        self._uid = uid
        return uid

    def _get_models_proxy(self) -> xmlrpc.client.ServerProxy:
        """Get /xmlrpc/2/object ServerProxy, cached."""
        if self._models is None:
            self._models = xmlrpc.client.ServerProxy(
                f"{self.url}/xmlrpc/2/object", allow_none=True
            )
        return self._models

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list | None = None,
        kwargs: dict | None = None,
    ):
        """Core method: maps to Odoo's execute_kw dispatch.

        Calls: models.execute_kw(db, uid, password, model, method, args, kwargs)
        """
        uid = self._authenticate()
        models = self._get_models_proxy()
        return models.execute_kw(
            self.db,
            uid,
            self.password,
            model,
            method,
            args if args is not None else [],
            kwargs if kwargs is not None else {},
        )
