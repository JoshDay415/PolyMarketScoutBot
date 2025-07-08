# Polymarket Price Alert 🚀

Monitors Polymarket’s daily **“up or down”** markets (ETH, BTC, more), compares
them against real-time Binance prices, and emails an alert when a value bet
appears.

| Stack | Why |
|-------|-----|
| **AWS EventBridge** | fires every 5 minutes |
| **AWS Lambda** | hits the GitHub Actions API (`workflow_dispatch`) |
| **GitHub Actions** | runs `polymarket_price.py`, sends email via Gmail SMTP |

## Quick start

1. **Fork or clone** the repo.  
2. Add the required secrets in **Settings → Secrets → Actions**  
   * `GITHUB_TOKEN` – PAT with `workflow` scope  
   * `EMAIL_FROM`, `EMAIL_APP_PASSWORD`, `TO_EMAIL`  
3. Deploy the Lambda function (see `infra/terraform/` if you prefer IaC).

## Configuration

| Variable | Where | Example |
|----------|-------|---------|
| `GITHUB_REPO` | Lambda env | `youruser/polymarket-alert` |
| `WORKFLOW_FILE_NAME` | Lambda env | `price_alert.yml` |
| `ALERT_THRESHOLD` | `alert_state.json` | `0.05` (5 % edge) |

## Adding assets

Edit `ASSETS` in `polymarket_price.py`:

```python
ASSETS = {
    "ETH": {...},
    "BTC": {...},
    "SOL": {...},
}
