# SHIOL-PLUS Documentation Index

Welcome to the SHIOL-PLUS docs. This project is a production-grade yet educational platform showcasing full-stack engineering, ML/statistics, AI integration, Stripe payments, and cost-optimized deployment.

- Purpose: Educational/portfolio (not a commercial lottery service)
- Version: v6.3 / Pipeline v3.1-smart-polling (November 2025)

## Quick Start
- Main README: ../README.md
- Live demo (if available): see main README

## Contents

### Setup & Configuration
- API Keys & .env: API_KEYS_SETUP.md

### Deployment
- Nginx reverse proxy: DEPLOYMENT_NGINX.md

### Technical Deep Dive
- Technical architecture & pipeline: TECHNICAL.md

### Admin & Users
- Admin user management (endpoints + UI): USER_MANAGEMENT_IMPLEMENTATION.md

### Payments (Stripe)
- Payment flow diagrams (overview): STRIPE_PAYMENT_FLOW_DIAGRAMS.md
- Technical reference: See section "Payments & Billing (Stripe)" in TECHNICAL.md

## Notes
- Scheduler: APScheduler is used in-app; cron is optional for backups.
- Premium: Admin toggle grants a 1-year premium period from activation.
- Security: HttpOnly cookies, role-based admin protection, secure password hashing.
- Sandbox: Stripe runs in test mode for demos.

## Contributing
Small doc improvements are welcome. Keep the modern, concise tone and prioritize clarity for educational purposes.
