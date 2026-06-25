*Update user command*

Updates selected fields of an existing gym member record\.

Use this when a member changes room, contact details, or name data\. Only the fields you specify are changed\.

*Usage*

`/updateuser telegram_id option value [option value ...]`

Required input:
\- `telegram_id`: the numeric Telegram ID of the member to update\.

Available options:
\- `-n` or `--name`: update the first name\.
\- `-s` or `--surname`: update the surname\.
\- `-r` or `--room`: update the room number\.
\- `-t` or `--telegram-name`: update the Telegram username\.
\- `-p` or `--phone-number`: update the phone number\.

Options can be supplied in any order\.

*Examples*

`/updateuser 123456789 --room 1302`

Updates only the member's room number\.

`/updateuser 123456789 -t @ada -p +49123456789`

Updates Telegram username and phone number\.

`/updateuser 123456789 --surname Byron --name Ada --room 1302`

Updates surname, name, and room in one command\.

*Short and long options can be mixed*

`/updateuser 123456789 -n Ada --telegram-name @ada`

>Important:
>\- At least one option and value pair is required\.
>\- Each field can be supplied only once per command\.
>\- `telegram_id` and `room` must be positive numbers\.
>\- Field values are expected as single command arguments without spaces\.
