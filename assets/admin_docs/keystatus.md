*Key status command*

Shows the current state of one key\.

*Usage*

`/keystatus key_id`

Required input:
\- `key_id`: the number of the key\.

*Examples*

`/keystatus 1`

Shows the status of key 1\.

`/keystatus 3`

Shows the status of key 3\.

The reply includes:
\- whether the key is active\.
\- the current holder record\.
\- the owner record\.

>Important:
>\- `key_id` must be a positive number\.
>\- The key must exist\.
