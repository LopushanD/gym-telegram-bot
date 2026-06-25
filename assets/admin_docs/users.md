*Users command*

Lists registered gym members\.

Use this to find member records and check details such as Telegram ID, room, Telegram username, phone number, and admin status\.

*Usage*

`/users [name] [surname] [room]`

Optional filters:
\- `name`: filter by first name\.
\- `surname`: filter by surname\.
\- `room`: filter by room number\.

Filters are positional\. To filter by room, provide name and surname before the room number\.

*Examples*

`/users`

Lists all registered gym members\.

`/users Ada`

Lists members with the name Ada\.

`/users Ada Lovelace`

Lists members with the name Ada and surname Lovelace\.

`/users Ada Lovelace 1204`

Lists members named Ada Lovelace in room 1204\.

>Important:
>\- `room` must be a positive number when supplied\.
>\- You cannot filter by surname or room alone with this command format\.
>\- Large result sets may be split across multiple bot messages\.
