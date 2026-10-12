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

`/keystatus 1`
Show status for key with ID 1\.

>Important:
>\- `key_id` must be a positive number\.
>\- The key must exist\.
