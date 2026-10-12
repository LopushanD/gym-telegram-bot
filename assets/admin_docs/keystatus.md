*Key status command*

Shows the current state of one key\.

The reply includes:
\- whether the key is active\.
\- whether the key is in a mailbox or in holder's hands\.
\- the current holder record\.
\- the owner record\.

*Usage*

`/keystatus key_id`

Required input:
\- `key_id`: the number of the key\.


*Example*

Situation: key 1 is named Red and is currently in Ada Lovelace's hands\. Dima Shevchenko owns it\.

`/keystatus 1`

```
Key: 1 (Red)
Active: yes
Location: user's hands
----------
Current holder

Name: Ada Lovelace
Room: 1204
Telegram username: @ada
Telegram ID: 123456789
Gym member ID: 10
is admin: False
Suspended until: None
Deleted at: None
----------
Owner

Name: Dima Shevchenko
Room: 1010
Telegram username: @dima
Telegram ID: 987654321
Gym member ID: 20
is admin: True
Suspended until: None
Deleted at: None
```

>Important:
>\- `key_id` must be a positive number\.
>\- The key must exist\.
