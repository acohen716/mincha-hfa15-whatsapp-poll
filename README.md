# HFA15 Mincha WhatsApp Auto Poll Sender

This repository contains [GitHub Action](https://docs.github.com/en/actions) workflows that sends a Whatsapp poll and reminder message to [Amazon HFA15 Mincha Whatsapp group](https://bit.ly/pray-amazon-hfa) to ensure we have a minyan - 10 participants

Skips sending on holiday and holiday eve per holiday JSON data in the [assets](./assets/) folder.

## Quickstart

### Local Development

1. Create `.env` with the following content:
   ```sh
   # For local development
   WHAPI_TOKEN=<PLACEHOLDER_FOR_WHAPI_TOKEN> # for example get from https://panel.whapi.cloud/channels/ROCKET-CZJYC
   WHATSAPP_GROUP_ID=120363418977916948@g.us # test group = 120363418977916948@g.us, prod group = 972549451336-1559741675@g.us
   ACTION_TYPE=poll # poll or reminder
   ```
2. Install dependencies:
   ```sh
   uv sync
   ```
3. Run the script:
   ```sh
   uv run --no-dev python send_whatsapp.py
   ```

### Linting & Type Checking

```sh
uv run ruff check .
uv run ruff format . --check --diff
uv run pyright .
```

### Running Tests

```sh
uv run pytest .
```

## Environment Variables

| Variable          | Description          |
| ----------------- | -------------------- |
| WHAPI_TOKEN       | Whapi API token      |
| WHATSAPP_GROUP_ID | WhatsApp group ID    |
| ACTION_TYPE       | "poll" or "reminder" |

## Details

1. The workflows are scheduled to run Sunday - Thursday at 07:55 (poll message) and 11:55 (reminder message)
   - Using [cron-job.org](https://console.cron-job.org/jobs) since GitHub Actions scheduled events [_"can be delayed during periods of high loads"_](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule)

2. It uses the [Whapi WhatsApp API for developers](https://whapi.cloud)
   - [Free Plan](https://whapi.cloud/price) - 1k API requests per month

## Future Features

1. Check if there is NOT tachanun and mention that in the message ([API currently broken](https://github.com/yairfax/IsThereTachanunToday/issues/6))

## References

1. [Whapi Help - Chat ID](https://support.whapi.cloud/help-desk/faq/chat-id.-what-is-it-and-how-to-get-it)
2. [Whapi Reference](https://whapi.readme.io/reference)
3. [Send Message Poll](https://whapi.readme.io/reference/sendmessagepoll)
4. [Send Message Text](https://whapi.readme.io/reference/sendmessagetext)
5. [Whapi Getting Started](https://support.whapi.cloud/help-desk/getting-started/getting-started)
6. [Using Polls as Buttons](https://support.whapi.cloud/help-desk/hints/how-to-use-polls-as-buttons)

## Whapi Channel Dashboard (Internal, only visible to owner)

[Whapi Channel Dashboard](https://panel.whapi.cloud/channels/ROCKET-CZJYC) (Shows API usage etc.)
