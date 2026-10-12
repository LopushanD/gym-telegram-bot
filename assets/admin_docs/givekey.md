*Give key command*

Records that a registered gym member received a key\.

Use this when an admin needs to correct key possesion\. After the command succeeds, the selected member becomes the recorded current holder regardless of the previous holder\.

*Usage*

`/givekey key_id telegram_id [-m/--mailbox True/False]`

Required inputs:
\- `key_id`: the number of the key\.
\- `telegram_id`: the numeric Telegram ID of the registered member receiving the key\.

Optional input:
\- `-m` or `--mailbox`: `True` records the key in the selected member's mailbox; `False` records the key in their hands\. Defaults to `False` when omitted\.
\- `True` and `False` are case insensitive\.

*Examples*

`/givekey 1 123456789`
Records that the member with Telegram ID 123456789 received key 1 in their hands\.

`/givekey 3 987654321 --mailbox False`
Records that the member with Telegram ID 987654321 received key 3 in their hands\.
Very similar to previous example\.

`/givekey 3 987654321 -m True`
Records key 3 in the mailbox of the member with Telegram ID 987654321\.

>Important:
>\- `key_id` and `telegram_id` must be positive numbers\.
>\- The target member must already be registered\.
>\- The key must exist\.