*Change key owner command*

Changes the registered owner of a key\.
The current holder, holder history, active status, and pending handover remain unchanged\.

*Usage*

`/keychangeowner key_id telegram_id`

Required inputs:
\- `key_id`: the number of the key\.
\- `telegram_id`: the Telegram ID of the registered member who will own the key\.

*Example*

`/keychangeowner 1 123456789`
Sets the member with Telegram ID 123456789 as the owner of key 1\.

>Important:
>When `return key to mailbox` button is pressed, key is returned to the owner\.
>\- `key_id` and `telegram_id` must be positive numbers\.
>\- The target member must already be registered\.
