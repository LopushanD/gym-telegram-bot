*Deactivate key command*

Marks a key as inactive\.

Use this when a key should no longer be available for normal tracking or use, for example because it is lost or blocked due to transfer between old and new AG member\.

*Usage*

`/deactivatekey key_id`

Required input:
\- `key_id`: the number of the key\.

*Examples*

`/deactivatekey 1`
Deactivates key 1\.

>Important:
>\- `key_id` must be a positive number\.
>\- The key must exist\.
>\- This changes the active status only; it does not change the current holder or history\.
