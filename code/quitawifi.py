###############################
#     !/usr/bin/env python    #
#   using Speedtest.net API   #
#                             #
#           Joan Bono         #
#    joan.bono@soyteleco.net  #
###############################

#Modify the e-mail and password
#QuitaWifiMeter
#Add changes
#Lines 579-586-588-590-610


__version__ = 'QuitaWifiMeter v1.5'

shutdown_event = None

import smtplib
import urllib
import urllib2
import os
import re
import string
import sys
import math
import signal
import socket
import timeit
import threading
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage

socket_socket = socket.socket

try:
    import xml.etree.cElementTree as ET
except ImportError:
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        from xml.dom import minidom as DOM
        ET = None

try:
    from urllib2 import urlopen, Request, HTTPError, URLError
except ImportError:
    from urllib.request import urlopen, Request, HTTPError, URLError

try:
    from httplib import HTTPConnection, HTTPSConnection
except ImportError:
    from http.client import HTTPConnection, HTTPSConnection

try:
    from Queue import Queue
except ImportError:
    from queue import Queue

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

try:
    from urlparse import parse_qs
except ImportError:
    try:
        from urllib.parse import parse_qs
    except ImportError:
        from cgi import parse_qs

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

try:
    from argparse import ArgumentParser as ArgParser
except ImportError:
    from optparse import OptionParser as ArgParser

try:
    import builtins
except ImportError:
    def print_(*args, **kwargs):
        fp = kwargs.pop("file", sys.stdout)
        if fp is None:
            return

        def write(data):
            if not isinstance(data, basestring):
                data = str(data)
            fp.write(data)

        want_unicode = False
        sep = kwargs.pop("sep", None)
        if sep is not None:
            if isinstance(sep, unicode):
                want_unicode = True
            elif not isinstance(sep, str):
                raise TypeError("sep must be None or a string")
        end = kwargs.pop("end", None)
        if end is not None:
            if isinstance(end, unicode):
                want_unicode = True
            elif not isinstance(end, str):
                raise TypeError("end must be None or a string")
        if kwargs:
            raise TypeError("invalid keyword arguments to print()")
        if not want_unicode:
            for arg in args:
                if isinstance(arg, unicode):
                    want_unicode = True
                    break

else:
    print_ = getattr(builtins, 'print')
    del builtins

def distance(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371  # km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2)) * math.sin(dlon / 2)
         * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = radius * c

    return d


class FileGetter(threading.Thread):


    def __init__(self, url, start):
        self.url = url
        self.result = None
        self.starttime = start
        threading.Thread.__init__(self)

    def run(self):
        self.result = [0]
        try:
            if (timeit.default_timer() - self.starttime) <= 10:
                f = urlopen(self.url)
                while 1 and not shutdown_event.isSet():
                    self.result.append(len(f.read(10240)))
                    if self.result[-1] == 0:
                        break
                f.close()
        except IOError:
            pass


def downloadSpeed(files, quiet=False):
    start = timeit.default_timer()

    def producer(q, files):
        for file in files:
            thread = FileGetter(file, start)
            thread.start()
            q.put(thread, True)
            if not quiet and not shutdown_event.isSet():

                sys.stdout.flush()

    finished = []

    def consumer(q, total_files):
        while len(finished) < total_files:
            thread = q.get(True)
            while thread.isAlive():
                thread.join(timeout=0.1)
            finished.append(sum(thread.result))
            del thread

    q = Queue(6)
    prod_thread = threading.Thread(target=producer, args=(q, files))
    cons_thread = threading.Thread(target=consumer, args=(q, len(files)))
    start = timeit.default_timer()
    prod_thread.start()
    cons_thread.start()
    while prod_thread.isAlive():
        prod_thread.join(timeout=0.1)
    while cons_thread.isAlive():
        cons_thread.join(timeout=0.1)
    return (sum(finished) / (timeit.default_timer() - start))


class FilePutter(threading.Thread):
    def __init__(self, url, start, size):
        self.url = url
        chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        data = chars * (int(round(int(size) / 36.0)))
        self.data = ('content1=%s' % data[0:int(size) - 9]).encode()
        del data
        self.result = None
        self.starttime = start
        threading.Thread.__init__(self)

    def run(self):
        try:
            if ((timeit.default_timer() - self.starttime) <= 10 and
                    not shutdown_event.isSet()):
                f = urlopen(self.url, self.data)
                f.read(11)
                f.close()
                self.result = len(self.data)
            else:
                self.result = 0
        except IOError:
            self.result = 0


def uploadSpeed(url, sizes, quiet=False):
    start = timeit.default_timer()

    def producer(q, sizes):
        for size in sizes:
            thread = FilePutter(url, start, size)
            thread.start()
            q.put(thread, True)
            if not quiet and not shutdown_event.isSet():

                sys.stdout.flush()

    finished = []

    def consumer(q, total_sizes):
        while len(finished) < total_sizes:
            thread = q.get(True)
            while thread.isAlive():
                thread.join(timeout=0.1)
            finished.append(thread.result)
            del thread

    q = Queue(6)
    prod_thread = threading.Thread(target=producer, args=(q, sizes))
    cons_thread = threading.Thread(target=consumer, args=(q, len(sizes)))
    start = timeit.default_timer()
    prod_thread.start()
    cons_thread.start()
    while prod_thread.isAlive():
        prod_thread.join(timeout=0.1)
    while cons_thread.isAlive():
        cons_thread.join(timeout=0.1)
    return (sum(finished) / (timeit.default_timer() - start))


def getAttributesByTagName(dom, tagName):
    elem = dom.getElementsByTagName(tagName)[0]
    return dict(list(elem.attributes.items()))


def getConfig():
    uh = urlopen('http://www.speedtest.net/speedtest-config.php')
    configxml = []
    while 1:
        configxml.append(uh.read(10240))
        if len(configxml[-1]) == 0:
            break
    if int(uh.code) != 200:
        return None
    uh.close()
    try:
        try:
            root = ET.fromstring(''.encode().join(configxml))
            config = {
                'client': root.find('client').attrib,
                'times': root.find('times').attrib,
                'download': root.find('download').attrib,
                'upload': root.find('upload').attrib}
        except AttributeError:
            root = DOM.parseString(''.join(configxml))
            config = {
                'client': getAttributesByTagName(root, 'client'),
                'times': getAttributesByTagName(root, 'times'),
                'download': getAttributesByTagName(root, 'download'),
                'upload': getAttributesByTagName(root, 'upload')}
    except SyntaxError:
        print_('Failed to parse speedtest.net configuration')
        sys.exit(1)
    del root
    del configxml
    return config


def closestServers(client, all=False):
    uh = urlopen('http://www.speedtest.net/speedtest-servers-static.php')
    serversxml = []
    while 1:
        serversxml.append(uh.read(10240))
        if len(serversxml[-1]) == 0:
            break
    if int(uh.code) != 200:
        return None
    uh.close()
    try:
        try:
            root = ET.fromstring(''.encode().join(serversxml))
            elements = root.getiterator('server')
        except AttributeError:
            root = DOM.parseString(''.join(serversxml))
            elements = root.getElementsByTagName('server')
    except SyntaxError:
        print_(' ')
        sys.exit(1)
    servers = {}
    for server in elements:
        try:
            attrib = server.attrib
        except AttributeError:
            attrib = dict(list(server.attributes.items()))
        d = distance([float(client['lat']), float(client['lon'])],
                     [float(attrib.get('lat')), float(attrib.get('lon'))])
        attrib['d'] = d
        if d not in servers:
            servers[d] = [attrib]
        else:
            servers[d].append(attrib)
    del root
    del serversxml
    del elements

    closest = []
    for d in sorted(servers.keys()):
        for s in servers[d]:
            closest.append(s)
            if len(closest) == 5 and not all:
                break
        else:
            continue
        break

    del servers
    return closest


def getBestServer(servers):
    results = {}
    for server in servers:
        cum = []
        url = '%s/latency.txt' % os.path.dirname(server['url'])
        urlparts = urlparse(url)
        for i in range(0, 3):
            try:
                if urlparts[0] == 'https':
                    h = HTTPSConnection(urlparts[1])
                else:
                    h = HTTPConnection(urlparts[1])
                start = timeit.default_timer()
                h.request("GET", urlparts[2])
                r = h.getresponse()
                total = (timeit.default_timer() - start)
            except (HTTPError, URLError, socket.error):
                cum.append(3600)
                continue
            text = r.read(9)
            if int(r.status) == 200 and text == 'test=test'.encode():
                cum.append(total)
            else:
                cum.append(3600)
            h.close()
        avg = round((sum(cum) / 6) * 1000, 3)
        results[avg] = server
    fastest = sorted(results.keys())[0]
    best = results[fastest]
    best['latency'] = fastest

    return best


def ctrl_c(signum, frame):

    global shutdown_event
    shutdown_event.set()
    raise SystemExit('\nCancelando...')


def version():
    raise SystemExit(__version__)


def speedtest():

    global shutdown_event
    shutdown_event = threading.Event()

    signal.signal(signal.SIGINT, ctrl_c)

    description = ('')


    parser = ArgParser(description=description)
    try:
        parser.add_argument = parser.add_option
    except AttributeError:
        pass
    parser.add_argument('--bytes', dest='units', action='store_const',
                        const=('bytes', 1), default=('bits', 8),
                        help='Muestra valor en bytes')
    parser.add_argument('--simple', action='store_true',
                        help='Muestra informacion basica.')
    parser.add_argument('--list', action='store_true',
                         help='Deshabilitado')
    parser.add_argument('--server', help='Especificar Servidor de prueba')
    parser.add_argument('--mini', help='URL del Speedtest Mini server. Ni idea para que')
    parser.add_argument('--version', action='store_true',
                        help='Mostrar version de script y salir')

    options = parser.parse_args()
    if isinstance(options, tuple):
        args = options[0]
    else:
        args = options
    del options

    if args.version:
        version()

    if not args.simple:
        print_('')
    try:
        config = getConfig()
    except URLError:
        print_('')
        sys.exit(1)

    if not args.simple:
        print_('')
    if args.list or args.server:
        servers = closestServers(config['client'], True)
        if args.list:
            serverList = []
            for server in servers:
                line = ('%(id)4s) %(sponsor)s (%(name)s, %(country)s) '
                        '[%(d)0.2f km]' % server)
                serverList.append(line)
            try:
                unicode()
                print_('\n'.join(serverList).encode('utf-8', 'ignore'))
            except NameError:
                print_('\n'.join(serverList))
            except IOError:
                pass
            sys.exit(0)
    else:
        servers = closestServers(config['client'])


    if args.server:
        try:
            best = getBestServer(filter(lambda x: x['id'] == args.server,
                                        servers))
        except IndexError:
            print_('')
            sys.exit(1)
    elif args.mini:
        name, ext = os.path.splitext(args.mini)
        if ext:
            url = os.path.dirname(args.mini)
        else:
            url = args.mini
        urlparts = urlparse(url)
        try:
            f = urlopen(args.mini)
        except:
            print_(' ')
            sys.exit(1)
        else:
            text = f.read()
            f.close()
        extension = re.findall('upload_extension: "([^"]+)"', text.decode())
        if not extension:
            for ext in ['php', 'asp', 'aspx', 'jsp']:
                try:
                    f = urlopen('%s/speedtest/upload.%s' % (args.mini, ext))
                except:
                    pass
                else:
                    data = f.read().strip()
                    if (f.code == 200 and
                            len(data.splitlines()) == 1 and
                            re.match('size=[0-9]', data)):
                        extension = [ext]
                        break
        if not urlparts or not extension:
            print_('')
            sys.exit(1)
        servers = [{
            'sponsor': 'Speedtest Mini',
            'name': urlparts[1],
            'd': 0,
            'url': '%s/speedtest/upload.%s' % (url.rstrip('/'), extension[0]),
            'latency': 0,
            'id': 0
        }]
        try:
            best = getBestServer(servers)
        except:
            best = servers[0]
    else:
        if not args.simple:
            print_(' ')
        best = getBestServer(servers)

    sizes = [350, 500, 750, 1000, 1500, 2000, 2500, 3000, 3500, 4000]
    urls = []
    for size in sizes:
        for i in range(0, 4):
            urls.append('%s/random%sx%s.jpg' %
                        (os.path.dirname(best['url']), size, size))
   
    dlspeed = downloadSpeed(urls, args.simple)
    if not args.simple:
        print_()

    sizesizes = [int(.25 * 1000 * 1000), int(.5 * 1000 * 1000)]
    sizes = []
    for size in sizesizes:
        for i in range(0, 25):
            sizes.append(size)
    
    ulspeed = uploadSpeed(best['url'], sizes, args.simple)
    if not args.simple:
        print_()

    bajada=dlspeed / 1000 / 1000* args.units[1], args.units[0]
    subida=ulspeed / 1000 / 1000* args.units[1], args.units[0]

    bajada2=dlspeed / 1000 / 1000* args.units[1]
    subida2=ulspeed / 1000 / 1000* args.units[1]


    string='Velocidad de Internet:\n  Bajada: %0.2f'%(bajada2)+'\n  Subida:   %0.2f\n\n'%(subida2)
    cuerpo=string
    
    dlspeedk = int(round((dlspeed / 1000) * 8, 0))
    ping = int(round(best['latency'], 0))
    ulspeedk = int(round((ulspeed / 1000) * 8, 0))

    apiData = [
            'download=%s' % dlspeedk,
            'ping=%s' % ping,
            'upload=%s' % ulspeedk,
            'promo=',
            'startmode=%s' % 'pingselect',
            'recommendedserverid=%s' % best['id'],
            'accuracy=%s' % 1,
            'serverid=%s' % best['id'],
            'hash=%s' % md5(('%s-%s-%s-%s' %
                             (ping, ulspeedk, dlspeedk, '297aae72'))
                            .encode()).hexdigest()]


    req = Request('http://www.speedtest.net/api/api.php',data='&'.join(apiData).encode())
    req.add_header('Referer', 'http://c.speedtest.net/flash/speedtest.swf')
    f = urlopen(req)
    response = f.read()
    code = f.code
    f.close()

    if int(code) != 200:
        sys.exit(1)

    qsargs = parse_qs(response.decode())
    resultid = qsargs.get('resultid')
    if not resultid or len(resultid) != 1:
        sys.exit(1)

    enlace="http://www.speedtest.net/result/%s.png"%resultid[0]

    directorio = '/path/to/script'

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.ehlo()
    #USERNAME WITHOUT @gmail.com, PASSWORD
    server.login("username", "password")
    #FROM MAIL with @gmail.com
    fromaddr = "username@gmail.com"
    #TO MAIL with @gmail.com
    toaddr = "receiver@gmail.com"
    msg = MIMEMultipart()
    msg['From'] = fromaddr
    msg['To'] = toaddr
    msg['Subject'] = "Alerta Internet"
    cuerpo="%s"%string
    body=cuerpo
    msg.attach(MIMEText(body, 'plain'))    
    
    #DESCARGA
    urllib.urlretrieve(enlace, "imagen.png") 

    fp = open('%s/imagen.png' % directorio, 'rb')
    msgImagen = MIMEImage(fp.read())
    fp.close()

    msg.attach(msgImagen)
    text = msg.as_string()
    
    #Internet Velocity. 200.0 as default
    if bajada2<200.0:
        server.sendmail(fromaddr, toaddr, text)   

def main():
    try:
        speedtest()
    except KeyboardInterrupt:
        print_(' ')


if __name__ == '__main__':
    main()

