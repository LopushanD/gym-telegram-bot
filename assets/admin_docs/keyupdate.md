*Update key command*

Updates selected fields of an existing key\. Only the fields you specify are changed\.

*Usage*

`/keyupdate key_id option value [option value ...]`

Required input:
\- `key_id`: the positive numeric ID of the key to update\.

Available options:
\- `-c` or `--current-holder`: make a registered user current key holder using their Telegram ID\.
\- `-o` or `--owner`: make a registered user key owner using their Telegram ID\.
\- `-a` or `--activate`: activate or deactivate key with `True` or `False` correspondingly\.
\- `-n` or `--name`: set the key name\.
\- `-m` or `--mailbox`: set key's current location\. `True` \- key is in mailbox, `False` \- key is in current holder's hands\.

Options can be supplied in any order, and short and long options can be mixed\.
Boolean values are case insensitive\.

*Examples*

`/keyupdate 1 --name Red --activate True`

activates key 1 and renames it to "Red"\.

`/keyupdate 1 -c 123456789 --owner 987654321 -m False`

Sets the user with Telegram ID 123456789 as the holder and the user with Telegram ID 987654321 as the owner, and records that the key is in the holder's hands\.

`/keyupdate 1 --mailbox True`

Records that the key is in mailbox\.

>Important:
>\- At least one option and value pair is required\.
>\- Telegram IDs must be positive numbers and refer to existing users\.
>\- Key names must be without spaces\.
>\- changes to key location are recorded in key holder history\.
>\- `-h` or `--help` shows this documentation and ignores all other arguments\.
