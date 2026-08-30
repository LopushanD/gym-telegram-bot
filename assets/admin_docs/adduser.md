*Add user command*

Registers a new gym member\.

*Usage*

`/adduser telegram_id name surname room telegram_name`

Required inputs:
\- `telegram_id`: the member's numeric Telegram ID\.
\- `name`: the member's first name\.
\- `surname`: the member's surname\.
\- `room`: the member's room number\.
\- `telegram_name`: the member's Telegram username\.

*Example*

`/adduser 123456789 Ada Lovelace 1204 @ada`
Registers Ada Lovelace who lives in room 1204 and has Telegram username @ada\.

>Important:
>\- `telegram_id` and `room` must be positive integer numbers\.
>\- The member must not already be registered with the same Telegram ID\.
