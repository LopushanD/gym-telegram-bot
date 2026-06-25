*Add user command*

Registers a new gym member\.

*Usage*

`/adduser telegram_id name surname room [telegram_name] [phone_number]`

Required inputs:
\- `telegram_id`: the member's numeric Telegram ID\.
\- `name`: the member's first name\.
\- `surname`: the member's surname\.
\- `room`: the member's room number\.

Optional inputs:
\- `telegram_name`: the member's Telegram username\.
\- `phone_number`: the member's phone number\.

*Examples*

`/adduser 123456789 Ada Lovelace 1204`
Registers Ada Lovelace in room 1204 without contact details\.

`/adduser 123456789 Ada Lovelace 1204 @ada`
Registers Ada Lovelace with a Telegram username\.

`/adduser 123456789 Ada Lovelace 1204 @ada +49123456789`
Registers Ada Lovelace with both Telegram username and phone number\.

>Important:
>\- `telegram_id` and `room` must be positive numbers\.
>\- The member must not already be registered with the same Telegram ID\.
>\- Names, Telegram usernames, and phone numbers are expected as single command arguments without spaces\.
