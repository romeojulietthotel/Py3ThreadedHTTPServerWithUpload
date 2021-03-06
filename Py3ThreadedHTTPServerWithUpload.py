#!/usr/bin/env python3

"""

Multi-threaded http download/upload server.

BaseHTTPServer that implements the standard GET and HEAD requests.

This is wide open and meant for trusted environments only.
The purpose is to have an easy way to share files on a LAN with people
you trust.


"""
 
__version__ = "1.3"
__me__ = "Py3ThreadedHTTPServerWithUpload"
__home_page__ = "https://github.com/romeojulietthotel/Py3ThreadedHTTPServerWithUpload"


import cgi
import datetime
import http.server
import mimetypes
import os
import posixpath
import re
import ssl
import sys
import threading
import time
import urllib.request, urllib.parse, urllib.error


from io import BytesIO
from shutil import copyfileobj
from socketserver import ForkingMixIn


class ThreadingSimpleServer(ForkingMixIn, http.server.HTTPServer):
    pass

class SimpleHTTPRequestHandler(http.server.BaseHTTPRequestHandler):

    """
    Request handler with GET/HEAD/POST commands.

    Serve the current directory's files and subdirs.
    Clients can upload files as long as the user running this has
    permissions to write to the directory we are run in.


    """
 
    server_version = "Py3HTTPServerWithUpload/" + __version__
 
    def do_GET(self):
        """Serve a GET request."""
        f = self.send_head()
        hkeys = self.headers.keys()
        for k in hkeys:
            print("{}: {}".format(k,self.headers.get(k)))
        if f:
            try:
                self.copyfile(f, self.wfile)
            except:
                raise Exception("Error during copyfile.")
            f.close()
 
    def do_HEAD(self):
        """Serve a HEAD request."""
        f = self.send_head()
        if f:
            f.close()
 
    def do_POST(self):
        """Serve a POST request."""
        r, info = self.deal_post_data()
        print((r, info, " by: ", self.client_address))
        f = BytesIO()
        msg = '<!DOCTYPE html>'
        msg += "<html>\n<title>Upload Result Page</title>\n"
        msg += "<body>\n<h2>Upload Result Page</h2>\n<hr>\n"

        if r:
            msg += "<strong>Success:</strong>"
        else:
            msg += "<strong>Failed:</strong>"
        msg += info
        msg += "<br><a href=\"%s\">back</a>" % self.headers['referer']
        msg += "<hr><small>Python powered"

        msg += "<a href=\"%s/%s\" targe=\"_blank\">" % (__home_page__,__me__)
        msg += __me__ + "</a>.</small></body>\n</html>\n"
        f.write(msg.encode())
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=UTF-8")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        if f:
            self.copyfile(f, self.wfile)
            f.close()
        
    def deal_post_data(self):
        content_type = self.headers['content-type']
        if not content_type:
            return (False, "Content-Type header missing boundary")
        boundary = content_type.split("=")[1].encode()
        remainder = int(self.headers['content-length'])
        line = self.rfile.readline()
        remainder -= len(line)
        if not boundary in line:
            return (False, "Content missing boundary")
        line = self.rfile.readline()
        remainder -= len(line)
        lined = line.decode()
        fn = re.findall(r'Content-Dispo\w+.*name="file";\sfil\w+="(.+)"', lined)
        if not fn:
            return (False, "Unable to determine file name...")
        path = self.translate_path(self.path)
        fn = os.path.join(path, fn[0])
        line = self.rfile.readline()
        remainder -= len(line)
        line = self.rfile.readline()
        remainder -= len(line)
        try:
            out = open(fn, 'wb')
        except IOError:
            return (False, " Unable to create file %s." % fn)

        preline = self.rfile.readline()
        remainder -= len(preline)
        while remainder > 0:
            line = self.rfile.readline()
            remainder -= len(line)
            if boundary in line:
                preline = preline[0:-1]
                if preline.endswith(b'\r'):
                    preline = preline[0:-1]
                out.write(preline)
                out.close()
                return (True, "File '%s' upload success!" % fn)
            else:
                out.write(preline)
                preline = line
        return (False, " Unexpected end of data %s." % str(preline))
 
    def send_head(self):
        """
        Common code for GET and HEAD commands.

        This sends the response code and MIME headers.

        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.

        """
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            if not self.path.endswith('/'):
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.end_headers()
                return None

            index = os.path.join(path, 'index.html')
            if os.path.exists(index) and os.stat(index)[6] > min_index_sz:
                path = index
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        try:
            favicon = faviconrx.search(path)
            if favicon:
                print("favicon request")
                path = faviconpath
            f = open(path, 'rb')
        except IOError:
            msg = "File %s not found" % path
            self.send_error(404, msg)
            return None
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        fs = os.fstat(f.fileno())
        self.send_header("Content-Length", str(fs[6]))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f
 
    def list_directory(self, path):
        """
        Produce a directory listing.

        Return value is a file object, or None.
        Headers are sent like send_head().

        """
        danglers = list()
        fullist = dict()
        mylist = dict()
        
        try:
            mylist = os.listdir(path)
            for f in range(0,len(mylist)):
                if not os.path.exists(os.path.join(path,mylist[f])):
                    danglers.append(f)
            for f in sorted(danglers, reverse=True):
                del mylist[f]

            mylist.sort(key=lambda x: os.stat(os.path.join(path, x)).st_ctime, reverse=True)
            for f in mylist:
                fstat = os.stat(os.path.join(path,f))
                hr_time = mod_date(fstat.st_mtime)
                fullist[f] = (hr_time,fstat.st_size)
        except os.error:
            self.send_error(404, "You have no permission to list: %s see %d" % path, os.error.errno)
            return None
        f = BytesIO()
        displaypath = cgi.escape(urllib.parse.unquote(self.path))
        msg = '<!DOCTYPE html>'
        msg += getstyle()
        msg += "<html>\n<title>Directory listing for %s</title>\n" % displaypath
        msg += "<body>\n<h2>Directory listing for %s</h2>\n" % displaypath
        msg += "<hr>\n"
        msg += "<form ENCTYPE=\"multipart/form-data\" method=\"post\">"
        msg += "<input name=\"file\" type=\"file\"/>"
        msg += "<input type=\"submit\" value=\"upload\"/></form>\n<hr>\n<ol>\n"
        msg += "<table><thead>%s" % displaypath
        msg += '<tr><th class="filename">File/Dir'
        msg += '<th class="timestamp">Date/Time'
        msg += '<th class="filesize">Size(bytes)<tbody>'
        f.write(msg.encode())
        for name in mylist:
            if re.match(r'^\.', name):
                continue
            fullname = os.path.join(path, name)
            displayname = linkname = name
            if os.path.isdir(fullname):
                displayname = name + "/"
                linkname = name + "/"
            if os.path.islink(fullname):
                # symlink to dir displays with @ links with /
                displayname = name + "@"
            msg = '<tr><td class="filesize">'
            msg += '<a href="%s" target="_blank">%s</a>'
            msg += '<td class="timestamp">%s<td class="filesize">   %d  \n'
            msg = msg % (urllib.parse.quote(linkname),
                         cgi.escape(displayname),
                        fullist[name][0], fullist[name][1])
            f.write(msg.encode())
        f.write(b"</table>\n<hr>\n</body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=UTF-8")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return f
 
    def translate_path(self, path):
        """
        Translate forward slash separated paths to the local syntax.

        Components specific to the local file system are ignored.

        """
        # rm query params
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
        path = posixpath.normpath(urllib.parse.unquote(path))
        words = path.split('/')
        words = [f for f in words if f]
        path = os.getcwd()
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path
 
    def copyfile(self, source, dest):
        """
        Copy data between two file objects.

        The source argument is a file object open for reading, the dest
        argument is a file object open for writing.

        """
        try:
            copyfileobj(source, dest)
        except BrokenPipeError:
            print("Unexpected client close.")
 
    def guess_type(self, path):
        """
        Guess the MIME type of a file.

        Argument is a path to a file).

        Return value is a string of type/subtype and used for a MIME
        Content-Type header.

        Look for file's extension in the table self.extensions_map
        Use application/octet-stream as the default.

        """
 
        base, ext = posixpath.splitext(path)
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        ext = ext.lower()
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        return self.extensions_map['']
 
    if not mimetypes.inited:
         # reads system mime.types
        mimetypes.init()
    extensions_map = mimetypes.types_map.copy()
    extensions_map.update(
                          {'': 'application/octet-stream',
                           '.py': 'text/plain',
                           '.c': 'text/plain',
                           '.h': 'text/plain',
                           '.txt': 'text/plain'
                          })

def getcfg():
    nvars = 0
    myvars = dict()

    file = os.path.join(os.path.dirname(sys.argv[0]),'pyserv.cfg')
    if sys.argv:
        for i in range(1,len(sys.argv)):
            if sys.argv[i] == '-c':
                file = sys.argv[i+1]
    elif not os.path.isfile(file):
        print("Unable to open file ", file)
        print("Re-run {} using the -c /path/to/config/file option".format(sys.argv[0]))
        sys.exit(12)

    try:
        cfg = open(file, 'r')
    except:
        print("Unable to open {}".format(file))
        sys.exit(1)

    for l in cfg:
        """ comment chars allowed and skip blank lines """
        if re.match(r'^\s*#', l) \
        or re.match(r'^\s*$', l) \
        or re.match(r'^\s*!', l) \
        or re.match(r'^\s*%', l):
            continue
        keyval = re.findall(r'^\s*([^\s=]+)\s*=\s*([\S]+)$', l)
        if keyval:
            nvars += 1
            key = keyval[0][0].lower()
            val = keyval[0][1]
            if re.match(r'env\d+', key):
                keyval = re.findall(r'^([^\s=]+)\s*=\s*([\S]+)', val)
                key = keyval[0][0]
                val = keyval[0][1]
                myvars[key] = val
            else:
                myvars[key] = val.lower()
    cfg.close()
    if nvars:
        return myvars
    else:
        print("No config file found, exiting.")
        sys.exit(1)


def getstyle():
    head = '<head><style type="text/css">'
    head += '''.filesize{
                 font-family: "Lucida Sans Unicode", "Lucida Grande", sans-serif;
                 font-size: 1.2em;
                 text-shadow: 2px 2px 2px #0f49d4;
             }
             .timestamp{                 
                 font-family: "Lucida Sans Unicode", "Lucida Grande", sans-serif;
                 font-size: 1.0em;
                 color: #bd6004;
                 text-shadow: 2px 2px 2px #e48e14;
             }
             .filename{
                 font-family: "Lucida Sans Unicode", "Lucida Grande", sans-serif;
                 font-size: 1.4em;
                 color: #340ef4;
                 text-shadow: 2px 2px 2px #9d8eea;
             }
             a:link    {text-decoration:none;}
             a:hover   {text-decoration:underline;}
             a:active  {text-decoration:underline;}
             a:visited {text-decoration:none;}
             </style></head>'''
    return head


def mod_date(file_mtime):
    return datetime.datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d/%H:%M:%S')


def myrequest(myserver):
    """
    Start a thread with the server -- that thread will then fork
    for each request. The forking model is cleaner with regards
    to memory use. Some memory growth was observed using the
    ThreadingMixin and the ForkingMixin does not show that memory
    use.
    """
    
    server_thread = threading.Thread(target=myserver.serve_forever())

    try:
        server_thread.daemon = True
        server_thread.start()
        server_thread.join(timeout=180)
    except:
        print("Exiting.")
    try:
        myserver.handle_request()
        print("What the ?")
        for k,v in myserver.headers():
            print("{}: {}".format(k,v))
    except KeyboardInterrupt:
        exit()
    except:
        raise Exception("Something unexpected happened.")


if __name__ == '__main__':
    myvars = getcfg()
    mydir = os.path.dirname(sys.argv[0])
    certfile = str(os.path.join(mydir,myvars['certfile']))
    keyfile = str(os.path.join(mydir,myvars['keyfile']))
    if not os.path.isfile(certfile) or not os.path.isfile(keyfile):
        print("Missing cert/key file, exiting.")
        sys.exit(1)
    ip = myvars['ipaddress']
    port = int(myvars['port'])
    faviconpath = myvars['faviconpath']
    faviconrx = re.compile(r'[^/]?/favicon.ico$', re.I)
    """ 20 bytes minimum size or do not use index.html """
    min_index_sz = 20
    try:
        server = ThreadingSimpleServer((ip, port), SimpleHTTPRequestHandler)
        if server:
            server.socket = ssl.wrap_socket(server.socket, 
                certfile=certfile,
                keyfile=keyfile,
                ssl_version=ssl.PROTOCOL_TLSv1_2,
                server_side=True,
                do_handshake_on_connect=False)
    except:
        raise Exception("Error at ignition.")
    print("Starting and listening on host {} port {}".format(ip,port))
    timestamp = "{0}".format(time.strftime('%Y/%m/%dT%H:%M:%S', time.localtime()))
    print("Date/Time: %s" % timestamp)
    
    while True:
        myrequest(server)

    print("Exiting.")
