# Background

This repository contains [GitHub Action](https://docs.github.com/en/actions) workflows that sends a Whatsapp poll and reminder message to Amazon HFA15 Mincha Whatsapp group (https://bit.ly/pray-amazon-hfa) to ensure we have a minyan - 10 participants

# Quickstart

## Local Development

1. Create `.env` with the following content:
   ```sh
   # For local development
   WHAPI_TOKEN=<PLACEHOLDER_FOR_WHAPI_TOKEN> # for example get from https://panel.whapi.cloud/channels/NEBULA-LJ56F
   WHATSAPP_GROUP_ID=120363418977916948@g.us # test group = 120363418977916948@g.us, prod group = 972549451336-1559741675@g.us
   ACTION_TYPE=poll # poll or reminder
   ```
2. Install dependencies:
   ```sh
   uv sync
   ```
3. Run the script:
   ```sh
   uv run python send_whatsapp.py
   ```

## Linting & Type Checking

```sh
uv run ruff check .
uv run pyright .
```

## Running Tests

```sh
uv run pytest .
```

# Environment Variables

| Variable          | Description          |
| ----------------- | -------------------- |
| WHAPI_TOKEN       | Whapi API token      |
| WHATSAPP_GROUP_ID | WhatsApp group ID    |
| ACTION_TYPE       | "poll" or "reminder" |

# Details

1. The workflows are scheduled to run Sunday - Thursday at 07:55 (poll message) and 11:55 (reminder message)

   - Using https://console.cron-job.org/jobs since GitHub Actions scheduled events [_"can be delayed during periods of high loads"_](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule)

2. It uses the [Whapi WhatsApp API for developers](https://whapi.cloud)

   - [Free Plan](https://whapi.cloud/price) - 1k API requests per month

# Future Features

1. Avoid sending if it's an Israeli public holiday or holiday eve since we won't be at the office and thus we shouldn't send poll/reminder - consider using https://docs.abstractapi.com/holidays (for example: `https://holidays.abstractapi.com/v1/?api_key={API_KEY}$&country=IL&year=2025&month=06&day=02` - 1K requests per month, should be enough) or https://www.api-ninjas.com/api/holidays (for example: `https://api.api-ninjas.com/v1/holidays?country=IL&type=NATIONAL_HOLIDAY_HEBREW` - requires API Key in header - Free Plan 10K requests per month, MORE than enough) or simply create a static dictionary with the holiday data to avoid more API calls
2. Check if there is NOT tachanun and mention that in the message - https://github.com/yairfax/IsThereTachanunToday/issues/6 (API currently broken)

# References

1. https://support.whapi.cloud/help-desk/faq/chat-id.-what-is-it-and-how-to-get-it
2. https://whapi.readme.io/reference
3. https://whapi.readme.io/reference/sendmessagepoll
4. https://whapi.readme.io/reference/sendmessagetext
5. https://support.whapi.cloud/help-desk/getting-started/getting-started
6. https://support.whapi.cloud/help-desk/hints/how-to-use-polls-as-buttons

# My Whapi Channel Dashboard (Internal, only visible to owner)

Shows API usage etc. - https://panel.whapi.cloud/channels/NEBULA-LJ56F
