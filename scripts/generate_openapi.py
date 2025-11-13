#!/usr/bin/env python3
"""
Generate OpenAPI (JSON) for the running FastAPI app and a Postman collection for PLP v2.
No external dependencies required.
"""
import json
import os
from pathlib import Path
import sys

# Ensure v2 is mounted for generation
os.environ.setdefault("PLP_API_ENABLED", "true")
os.environ.setdefault("PREDICTLOTTOPRO_API_KEY", "DEMO_KEY_CHANGE_ME")

root = Path(__file__).resolve().parents[1]
# Ensure project root is in sys.path for `import src`
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from src.api import app  # noqa: E402

api_dir = root / "docs" / "api"
postman_dir = api_dir / "postman"
api_dir.mkdir(parents=True, exist_ok=True)
postman_dir.mkdir(parents=True, exist_ok=True)

# 1) Dump OpenAPI JSON (includes v2 since flag is true)
openapi_path = api_dir / "openapi_plp_v2.json"
with open(openapi_path, "w", encoding="utf-8") as f:
    json.dump(app.openapi(), f, indent=2, ensure_ascii=False)
print(f"Wrote OpenAPI to {openapi_path}")

# 2) Write a Postman collection for PLP v2
collection = {
    "info": {
        "name": "SHIOL+ PLP v2 API",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        "description": "Collection for PredictLottoPro v2 adapter endpoints"
    },
    "variable": [
        {"key": "baseUrl", "value": "http://localhost:8000"},
        {"key": "apiKey", "value": "REPLACE_WITH_REAL_KEY"},
        {"key": "drawDate", "value": "2025-11-05"}
    ],
    "item": [
        {
            "name": "Predictions Only",
            "request": {
                "method": "GET",
                "header": [{"key": "Authorization", "value": "Bearer {{apiKey}}"}],
                "url": {
                    "raw": "{{baseUrl}}/api/v2/public/predictions-only/{{drawDate}}",
                    "host": ["{{baseUrl}}"],
                    "path": ["api", "v2", "public", "predictions-only", "{{drawDate}}"]
                }
            }
        },
        {
            "name": "By Draw (Grouped)",
            "request": {
                "method": "GET",
                "header": [{"key": "Authorization", "value": "Bearer {{apiKey}}"}],
                "url": {
                    "raw": "{{baseUrl}}/api/v2/public/by-draw/{{drawDate}}",
                    "host": ["{{baseUrl}}"],
                    "path": ["api", "v2", "public", "by-draw", "{{drawDate}}"]
                }
            }
        },
        {
            "name": "Generate Multi-Strategy",
            "request": {
                "method": "POST",
                "header": [
                    {"key": "Authorization", "value": "Bearer {{apiKey}}"},
                    {"key": "Content-Type", "value": "application/json"}
                ],
                "body": {
                    "mode": "raw",
                    "raw": json.dumps({
                        "count": 10,
                        "persist": True,
                        "draw_date": "{{drawDate}}"
                    })
                },
                "url": {
                    "raw": "{{baseUrl}}/api/v2/generate-multi-strategy",
                    "host": ["{{baseUrl}}"],
                    "path": ["api", "v2", "generate-multi-strategy"]
                }
            }
        },
        {
            "name": "Ticket Preview (image)",
            "request": {
                "method": "POST",
                "header": [{"key": "Authorization", "value": "Bearer {{apiKey}}"}],
                "body": {
                    "mode": "formdata",
                    "formdata": [
                        {"key": "file", "type": "file", "src": ["/path/to/ticket.jpg"]}
                    ]
                },
                "url": {
                    "raw": "{{baseUrl}}/api/v2/ticket/preview",
                    "host": ["{{baseUrl}}"],
                    "path": ["api", "v2", "ticket", "preview"]
                }
            }
        },
        {
            "name": "Ticket Verify (image)",
            "request": {
                "method": "POST",
                "header": [{"key": "Authorization", "value": "Bearer {{apiKey}}"}],
                "url": {
                    "raw": "{{baseUrl}}/api/v2/ticket/verify?draw_date={{drawDate}}",
                    "host": ["{{baseUrl}}"],
                    "path": ["api", "v2", "ticket", "verify"],
                    "query": [{"key": "draw_date", "value": "{{drawDate}}"}]
                },
                "body": {
                    "mode": "formdata",
                    "formdata": [
                        {"key": "file", "type": "file", "src": ["/path/to/ticket.jpg"]}
                    ]
                }
            }
        },
        {
            "name": "Ticket Verify (manual)",
            "request": {
                "method": "POST",
                "header": [
                    {"key": "Authorization", "value": "Bearer {{apiKey}}"},
                    {"key": "Content-Type", "value": "application/json"}
                ],
                "url": {
                    "raw": "{{baseUrl}}/api/v2/ticket/verify-manual",
                    "host": ["{{baseUrl}}"],
                    "path": ["api", "v2", "ticket", "verify-manual"]
                },
                "body": {
                    "mode": "raw",
                    "raw": json.dumps({
                        "draw_date": "{{drawDate}}",
                        "plays": [
                            {"line": 1, "numbers": [10, 23, 37, 48, 62], "powerball": 12}
                        ]
                    })
                }
            }
        }
    ]
}

postman_path = postman_dir / "PLP_v2.postman_collection.json"
with open(postman_path, "w", encoding="utf-8") as f:
    json.dump(collection, f, indent=2)
print(f"Wrote Postman collection to {postman_path}")
