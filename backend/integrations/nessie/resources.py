"""Per-resource Nessie paths (live API). Single source of truth for seeding, verification
and (Phase 4) retrieval."""

# Path to fetch / delete one record by id.
ITEM_PATHS = {
    "customer": "/customers/{id}",
    "account": "/accounts/{id}",
    "merchant": "/merchants/{id}",
    "loan": "/loans/{id}",
    "bill": "/bills/{id}",
    "deposit": "/deposits/{id}",
    "withdrawal": "/withdrawal/{id}",
    "purchase": "/purchase/{id}",
    "transfer": "/transfers/{id}",
}

# Path listing records under a parent.
LIST_PATHS = {
    "customer": "/customers",
    "merchant": "/merchants",
    "account": "/customers/{parent}/accounts",
    "loan": "/accounts/{parent}/loans",
    "bill": "/accounts/{parent}/bills",
    "deposit": "/accounts/{parent}/deposits",
    "withdrawal": "/accounts/{parent}/withdrawals",
    "purchase": "/accounts/{parent}/purchases",
    "transfer": "/accounts/{parent}/transfers",
}

# Field holding the [wp:...] marker, per resource.
MARKER_FIELDS = {"account": "nickname", "bill": "nickname", "loan": "description", "deposit": "description",
                 "withdrawal": "description", "purchase": "description", "transfer": "description"}

ACCOUNT_CHILDREN = ("loan", "bill", "deposit", "withdrawal", "purchase", "transfer")
DELETABLE = ("deposit", "withdrawal", "purchase", "transfer", "bill", "loan", "account")
