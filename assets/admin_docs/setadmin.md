*Set admin command*

Grant or remove admin rights for a registered user\. Only existing admins can use this command\.

*Usage*

`/setadmin telegram_id True/False`

Required inputs:
\- `telegram_id`: Telegram ID of a registered user\.
\- `True` grants admin rights; `False` removes them\. Letter case does not matter\.

*Examples*

`/setadmin 123456789 True`
Grant admin rights\.

`/setadmin 123456789 false`
Remove admin rights\.

`/setadmin --help`
Show this documentation\.


You can remove your own admin rights\.
If you remove the last admin's rights, restoring access requires a database update outside the bot\.