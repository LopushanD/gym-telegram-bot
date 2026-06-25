*Give key command*

Records that a registered gym member received a key\.

Use this when an admin needs to correct key possesion\. After the command succeeds, the selected member becomes the recorded current holder regardless of previous holder\.

*Usage*

`/givekey key_id telegram_id`

Required inputs:
\- `key_id`: the number of the key\.
\- `telegram_id`: the numeric Telegram ID of the registered member receiving the key\.

*Examples*

`/givekey 1 123456789`
Records that the member with Telegram ID 123456789 received key 1\.

`/givekey 3 987654321`
Records that the member with Telegram ID 987654321 received key 3\.

>Important:
>\- `key_id` and `telegram_id` must be positive numbers\.
>\- The target member must already be registered\.
>\- The key must exist\.