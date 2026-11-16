# Google Drive in / out (Claude Code on the user's computer only)

For a user who drives nve from their phone with Remote Control: phone attachments are capped (~30 MB), so
big videos come in and go out through Google Drive. Not available on claude.ai: `nve drive` does not exist
there; never mention Drive transfer there.

| Drive | On this computer (workspace) |
|---|---|
| `nve/google-raw-input/` | `google-drive/google-raw-input/` |
| `nve/google-edited-output/` | `google-drive/google-edited-output/` |

Every `nve drive` command prints JSON with `ok`; `reason` says why not. Pulls and pushes of big videos can
take minutes: run them in the background (Bash `run_in_background`) and wait for the result; never cut them
short with a timeout.

## `/nve setup-gg-drive`

One time, **only while the user is at this computer**: Google sign-in opens a browser here.
1. If the request came from the phone (Remote Control) or you are not sure the user is at the computer, ask
   in one line: "Bạn đang ngồi ở máy tính chứ? Cần đăng nhập Google trên máy này." Do not run setup until they
   say yes; if they are away, tell them to type `/nve setup-gg-drive` next time they are at the computer.
2. Tell the user in one line: a browser window will open on this computer, sign in to Google and click
   **Allow**; nve gets access to their Google Drive (to read the videos they upload and save the finished
   ones), the access stays on this computer.
3. Run `nve drive setup` (it installs the transfer tool by itself, no admin rights; waits up to 5 minutes for
   the sign-in).
4. On `ok`: tell them to upload videos from the phone to **Drive › nve › google-raw-input**, and that the
   finished videos will appear in **Drive › nve › google-edited-output**. Suggest (do not change it yourself)
   keeping the computer awake so Remote Control stays reachable.

## Each edit that uses Drive

Use Drive when the user says the video is on Drive, pastes a Drive link, or asks for the result on Drive.
1. `nve drive status`. When `ready` is false, stop the Drive part and tell the user (table below). **Never**
   run `setup` for a remote request: it would wait for a browser nobody sees.
2. Input:
   - a Drive link → `nve drive pull --link "<url>"`
   - named file(s) → `nve drive pull --file "<name>"` (repeat `--file` for several)
   - otherwise `nve drive pull`:
     - one file in the folder → downloaded.
     - `reason: "choose"` → show `files` as a short numbered list (name · size MB · date, newest first; say
       which are already on the computer) and ask which to edit (one or several), then `pull --file` those
       names. Never download everything.
     - `reason: "empty"` → ask the user to upload the video to Drive › nve › google-raw-input.
   - `pulled` lists the local files; give them to `nve new` as usual (`--move` is not needed; keep them).
3. Edit as usual.
4. After the final render: `nve drive push <the final video> [<its cover>]`: only the files of this job.
5. Reply with the Drive path(s) from `pushed`, e.g. "Xong: Drive › nve › google-edited-output › promo.mp4".
   Never create share links.

Nothing is ever deleted, on Drive or on the computer.

## When it fails

| `reason` | Tell the user |
|---|---|
| `rclone_missing`, `not_logged_in` | Drive is not connected yet: type `/nve setup-gg-drive` when at the computer |
| `drive_unreachable` | Google access expired or was removed, or no network: run `/nve setup-gg-drive` again at the computer |
| `login_timeout`, `login_failed_or_cancelled` | sign-in did not finish; try `/nve setup-gg-drive` again |
| `rclone_install_failed` | the transfer tool could not be installed (network); try again later |
| `bad_link` | that is not a link to a Drive file: ask for the file's share link |
| `bad_name`, `file_not_found` | check the name against the list and try again |
| `choose`, `empty` | not errors: step 2 |
| `pull_failed`, `push_failed`, `list_failed` | retry once; if it fails again, say so and keep the local file |
