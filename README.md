# Background
This repository contains an action that sends a Whatsapp poll and message reminder to Amazon HFA15 mincha Whatsapp group (https://bit.ly/pray-amazon-hfa) to ensure we have a minyan - 10 participants

# Details
1. The action runs every Sunday - Thursday at 07:30 (poll) and 11:30 (reminder message)
2. It uses the [Whapi WhatsApp API for developers](https://whapi.cloud)

# Future Features
1. Check if it's an Israeli public holiday or holiday eve since we won't be at the office and thus we shouldn't send poll/reminder - consider using https://holidayapi.com
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
