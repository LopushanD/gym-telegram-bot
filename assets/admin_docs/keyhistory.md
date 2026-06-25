*Key history command*

Shows recent holder changes for one key\.

Use this to audit who received a key and when the bot recorded each holder change\.

*Usage*

`/keyhistory key_id [last_n_records]`

Required input:
\- `key_id`: the number of the key\.

Optional input:
\- `last_n_records`: how many recent history records to show\.

If `last_n_records` is not provided, the bot return 5 last records \(default\)\.

*Examples*

`/keyhistory 1`
Shows the default number of recent holder changes for key 1\.

`/keyhistory 1 10`
Shows the 10 most recent holder changes for key 1\.

`/keyhistory 3 1`
Shows only the most recent holder change for key 3\.

>Important:
>\- `key_id` and `last_n_records` must be positive numbers\.
>\- The command only shows records for the selected key\.
>\- If no records exist for the key, the bot reports that no history was found\.
