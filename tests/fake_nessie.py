"""In-memory fake of the live Nessie API, reproducing behaviors verified in Phase 1."""
import json
import re
import uuid

import httpx

CHILD = {"deposits": "deposit", "withdrawals": "withdrawal", "purchases": "purchase",
         "transfers": "transfer", "bills": "bill", "loans": "loan"}
ITEM = {"deposits": "deposit", "withdrawal": "withdrawal", "purchase": "purchase", "transfers": "transfer",
        "bills": "bill", "loans": "loan", "accounts": "account", "customers": "customer", "merchants": "merchant"}


class FakeNessie:
    def __init__(self):
        self.store: dict[str, dict[str, dict]] = {k: {} for k in set(ITEM.values())}
        self.parent: dict[str, str] = {}  # child id -> parent id
        self.fail_queue: list[tuple[str, str, int, bool]] = []  # (method, regex, status, apply_effect)
        self.requests: list[tuple[str, str]] = []

    def transport(self):
        return httpx.MockTransport(self.handle)

    def fail(self, method, pattern, status, apply_effect=False):
        """Make the next matching request fail; apply_effect=True means the write still happened."""
        self.fail_queue.append((method, pattern, status, apply_effect))

    def count(self, kind):
        return len(self.store[kind])

    # ------------------------------------------------------------------
    def handle(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        self.requests.append((method, path))
        if request.url.params.get("key") != "test-key":
            return httpx.Response(401, json="Invalid API key.")
        body = json.loads(request.content) if request.content else None
        for i, (m, pat, status, effect) in enumerate(self.fail_queue):
            if m == method and re.search(pat, path):
                del self.fail_queue[i]
                if effect:
                    self.route(method, path, body)
                return httpx.Response(status, json="injected failure")
        return self.route(method, path, body)

    def _create(self, kind, body, parent=None):
        obj = {**body, "_id": str(uuid.uuid4())}
        for k in ("balance", "amount", "rewards", "monthly_payment"):
            if k in obj:
                obj[k] = int(obj[k])  # live API truncates decimals
        if kind == "account":
            obj.update(customer_id=parent, account_number="1" * 16)
        if kind == "bill":
            obj.update(account_id=parent, upcoming_payment_date=obj.get("payment_date"), creation_date="2026-11-08")
        self.store[kind][obj["_id"]] = obj
        if parent:
            self.parent[obj["_id"]] = parent
        return httpx.Response(201, json={"code": 201, "message": f"{kind} created", "objectCreated": obj})

    def _children(self, kind, parent):
        return [o for i, o in self.store[kind].items() if self.parent.get(i) == parent]

    def route(self, method, path, body):
        parts = path.strip("/").split("/")
        if parts == ["customers"]:
            return (httpx.Response(200, json=list(self.store["customer"].values())) if method == "GET"
                    else self._create("customer", body))
        if parts == ["merchants"]:
            return (httpx.Response(200, json=list(self.store["merchant"].values())) if method == "GET"
                    else self._create("merchant", body))
        if len(parts) == 3 and parts[0] == "customers" and parts[2] == "accounts":
            if parts[1] not in self.store["customer"]:
                return httpx.Response(404, json="Customer not found")
            if method == "GET":
                return httpx.Response(200, json=self._children("account", parts[1]))
            return self._create("account", body, parts[1])
        if len(parts) == 3 and parts[0] == "accounts" and parts[2] in CHILD:
            kind = CHILD[parts[2]]
            if method == "GET":
                rows = self._children(kind, parts[1])
                if kind == "transfer":
                    if not rows:
                        return httpx.Response(404, json="No transfers found for this account")
                    rows = [{("id" if k == "_id" else k): v for k, v in r.items()} for r in rows]
                return httpx.Response(200, json=rows)
            if parts[1] not in self.store["account"]:
                return httpx.Response(404, json="Account not found")
            if kind == "transfer" and ({"medium", "payee_id"} & set(body)):
                return httpx.Response(400, json="extra fields not permitted")
            return self._create(kind, body, parts[1])
        if len(parts) == 2 and parts[0] in ITEM:
            kind = ITEM[parts[0]]
            obj = self.store[kind].get(parts[1])
            if method == "GET":
                return httpx.Response(200, json=obj) if obj else httpx.Response(404, json="not found")
            if method == "DELETE":
                self.store[kind].pop(parts[1], None)  # never cascades, like the live API
                return httpx.Response(200)
        return httpx.Response(403, json={"message": "Missing Authentication Token"})
