*Users command*

Lists registered gym members\.

Use this to find member records and check details such as Telegram ID, room, Telegram username, and admin status\.

*Usage*

`/users [-n or --name Value] [-s or --surname Value] [-n or --room Value]`

Optional filters:
\- `-n` or `--name`: filter by first name\.
\- `-s` or `--surname`: filter by surname\.
\- `-r` or `--room`: filter by room number\.

*Examples*

`/users`

Lists all registered gym members\.

`/users -n Ada`

Lists members with the name Ada\.

`/users -s Lovelace`

Lists members with the surname Lovelace\.

`/users -n Ada -r 1204`

Lists members named Ada who live in room 1204\.

>Important:
>\- `room` must be a positive number when supplied\.
>\- Large result sets may be split across multiple bot messages\.
