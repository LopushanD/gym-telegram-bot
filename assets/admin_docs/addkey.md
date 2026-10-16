*Add key command*

Creates one inactive key owned and held by a registered gym member\.

*Usage*

`/addkey owner_telegram_id [key_name]`

Required input:
\- `owner_telegram_id`: the owner's positive numeric Telegram ID, as used by `/adduser`\.

Optional input:
\- `key_name`: the key's name\. It can contain multiple words and defaults to "Unnamed"\.

*Examples*

`/addkey 123456789`
Creates one inactive key named "Unnamed" for this member\.

`/addkey 123456789 Red`
Creates one inactive key named "Red" for this member\.

>Important:
>\- Only registered admins can use this command\.
>\- The owner must already be registered\. The new key is recorded in their hands\.
>\- The bot replies with the generated key ID\. Every successful call creates one new key\.
>\- Use `/activatekey key_id` when the key is ready to be used\.
