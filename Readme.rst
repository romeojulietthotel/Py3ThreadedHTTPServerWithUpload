Multi-threaded Python3 HTTP download/upload server.
===================================================

BaseHTTPServer that implements the standard GET and HEAD requests.

This is wide open and meant for trusted environments only.
The purpose is to have an easy way to share files on a LAN with people
you trust.

It works but it's not perfect. But good enough.



TODO:
-----

- On file upload don't overwrite an existing file, sometimes you want to
overwrite an existing file,.e.g. An index.html file that prevents seeing a directory's
contents. Maybe allow some to be overwritten and deny all others; an overwrite whitelist.

- Seek out the anwser to whether or not ForkingMixin is portable to Windows
systems.

- Add more styling to the filename and filesize output so it's easier
to read.

