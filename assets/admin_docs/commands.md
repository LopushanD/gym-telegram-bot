*Available commands*

Command input format:
Required inputs are written without brackets\.
Optional inputs are written inside square brackets\.

Each command has `-h` or `--help` option, which will show detailed description and usage of the corresponding command\.

If you enter a command that requires at least one input with no inputs, you will get a message with a short usage hint\.
\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=

`/adduser telegram_id name surname room telegram_name`
Register a new gym member\.

`/updateuser telegram_id option value [option value ...]`
Update specific gym member fields\. Options can be supplied in any order\.
Available options: `-n` or `--name`, `-s` or `--surname`, `-r` or `--room`, `-t` or `--telegram-name`\.

`/givekey key_id telegram_id`
Record that a registered gym member received a key\.

`/users [name] [surname] [room]`
List gym members matching the optional filters\.

`/keyhistory key_id [last_n_records]`
List recent _n_ holder changes for a key\. _n_ defaults to 5\.

`/keystatus key_id`
Show a key's current holder, owner, and active status\.

`/keychangeowner key_id telegram_id`
Change a key's owner\.

`/activatekey key_id`
Activate a key\.

`/deactivatekey key_id`
Deactivate a key\.
