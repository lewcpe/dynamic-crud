I would like to create application platform which allow user to create application easily with no code needed. 

-  The platform allow user to specify table schema, add/remove fields
- allow user to specify relationships
- the application has two roles: admin and user
- admin could edit schema and edit relationships, users could view/edit tables/rows which they have authorized.
- admin could add/remove other admins
- users has groups and authorization could be assign in both way, the autorization always in addition (we need table for user/group)
- authorization could specify at table level or row level, at row level, itwill be specify with pocketbase like rule (see RULES.md)
- user could also attached files in to each row (add file type file/files)
- user also able to comments on each row (authorization is the same as the row itself which the user must have write authorizatio to comment)

