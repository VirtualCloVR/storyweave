# Workspace / Thread / Session deletion

Implemented deletion controls for all three workspace levels. Select the item, use the trash button in that section heading, then review the confirmation dialog before deleting it.

## Behavior

- Deleting a Workspace also deletes its Threads, Sessions, messages, sources, and adopted content.
- Deleting a Thread also deletes its Sessions and their related content.
- Deleting a Session deletes its messages, sources, and adopted content.
- The dialog shows the selected title and descendant counts before the request is sent.
- Cancel, Escape, backdrop click, focus return, keyboard focus trapping, pending request state, and API failures are handled without removing local state early.
- Deletion is blocked while an affected Session is generating a response.
- Deleting an adopted Session invalidates that Thread's Context digest so later chats cannot reuse stale adopted content.

## Verification

- Frontend: 30 tests passed, including successful cascades, cancellation, API failure, generation blocking, unrelated data preservation, and HTTP 204 handling.
- Backend: 48 tests passed, including Project, Thread, and adopted Session cascades with unrelated records preserved.
- Production frontend build passed.
- Desktop and 390 px mobile layouts were inspected; dialogs fit the viewport and start with Cancel focused.
- The public page at `http://192.168.11.7:18080` exposes all three delete controls. Session and Workspace dialogs were opened and cancelled without deleting user data.
- Backend, frontend, and PostgreSQL are running; `/api/health` reports database and LLM `ok`.
- Pre- and post-deployment data-only PostgreSQL dumps are identical.

## Deployment recovery

Server backup: `/home/bap4/apps/storyweave/backups/20260915-hierarchy-delete`

- `source-before.tar.gz`
- `database-before.dump`
- `data-before.sql`
- Docker tags `storyweave-frontend:before-hierarchy-delete-20260915` and `storyweave-backend:before-hierarchy-delete-20260915`
