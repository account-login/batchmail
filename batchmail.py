#!/usr/bin/env python3
# encoding: utf-8

# dependencies: pyzmail python-magic Pillow
# WARNING: python2.x incompatible

# TODO: split large file
# TODO: gui


import pyzmail
from pyzmail import compose_mail
from glob import glob
import os, io, hashlib, functools, html, datetime, base64, json


"""
This module contains utilities to sending photos, files by email.

usage:
images = glob('*.JPG')
# sort and split images into groups
grps = files2groups(images, max_size=10*1024*1024, ordered_by='image.date')
# setup each Email instance
emls = groups2Emails(grps, title='Some photos')
for eml in emls:
    eml.from_ = 'xxx@example.com'
    eml.to = ['yyy@abc.com']
    eml.user_name = 'xxx@example.com'
    eml.password = '*********'
    eml.smtp = 'smtp.example.com'
    # send the email
    eml.send()

"""


class JSONEncoder(json.JSONEncoder):
    """A JSON encoder
    
    try to call __json__() to get a JSON-able object when object is not JSON-able,
    if __json__() is not present, use None instead.
    """
    def default(self, o):
        if hasattr(o, '__json__'):
            return o.__json__()
        else:
            # unsuported object, represented as 'null'
            return None

def json_encode(*args, **kwd):
    return json.dumps(*args, cls=JSONEncoder, ensure_ascii=False, **kwd)


# ref: http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
def sizeof_fmt(num, suffix='B'):
    """human readable file size"""
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return ("%3.1f%s%s" if unit != '' else "%d%s%s") % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


class Email:
    """simple high level interface to send an email
    
    usage:
    setting up appropriate attributes and call send().
    the available attributes are listed in __init__()
    """
    def __init__(self, from_=None, to=[], cc=[], bcc=[],
                 subject='', text=None, html=None, attachments=[],
                 smtp=None, user_name=None, password=None, mode='tls', **kwds):
        self.from_ = from_
        # list of recipients
        self.to = to
        self.cc = cc
        self.bcc = bcc
        
        self.subject = subject
        
        # message body
        self.text = text
        self.html = html
        
        # list of file names
        self.attachments = attachments
        
        # smtp server
        self.smtp = smtp
        # smtp account
        self.user_name = user_name
        # smtp password
        self.password = password
        # 'normal', 'ssl' or 'tls'
        self.mode = mode
    
    def __json__(self):
        """return a dict to be jsonized, used by JSONEncoder"""
        ret = {
            'from': self.from_
        }
        for x in ('to', 'cc', 'bcc', 'subject', 'text', 'html', 'attachments', 'smtp', 'user_name', 'mode'):
            attr = getattr(self, x)
            if attr is not None and attr != []:
                ret[x] = attr
        return ret
    
    def __repr_json__(self):
        """return an approximate JSON string representation
        
        long strings are ellipsised so this is suitable in __repr__()
        """
        dct = self.__json__()
        for x in dct:
            if isinstance(dct[x], str):
                if len(dct[x]) > 80:
                    dct[x] = dct[x][:80] + ' ... '
        return json_encode(dct, indent=4)
    
    @classmethod
    def from_json(cls, js_str):
        """initialize an Email instance from a JSON string"""
        js = json.loads(js_str)
        instance = cls()
        instance.from_ = js['from']
        for x in ('to', 'cc', 'bcc', 'subject', 'text', 'html', 'attachments', 'smtp', 'user_name', 'mode'):
            if x in js:
                setattr(instance, x, js[x])
        return instance
    
    def to_json(self, **kwd):
        """return an almost full JSON string representation"""
        return json_encode(self, **kwd)
    
    def __repr__(self):
        ret = '<%s at 0x%x\n' % (self.__class__.__name__, id(self))
        ret += self.__repr_json__()
        ret += '>\n'
        return ret
    
    # TODO:
#     def _repr_html_(self):
#         pass
        
    @staticmethod
    def _get_addr(arg):
        if isinstance(arg, tuple):
            return arg[1]
        else:
            return arg
        
    def from_addr(self):
        return Email._get_addr(self.from_)
        
    def to_addr(self):
        ret=list(map(Email._get_addr, self.to))
        ret.extend(list(map(Email._get_addr, self.cc)))
        ret.extend(list(map(Email._get_addr, self.bcc)))
        return ret
        
    def normalize(self):
        if not isinstance(self.to, list):
            self.to = [self.to]
        # guess smtp server
        if self.smtp is None:
            if self.from_ is not None:
                self.smtp = ('smtp.'+self.from_addr().split('@')[-1], 25)
        # guess smtp port
        elif not isinstance(self.smtp, tuple):
            self.smtp = (self.smtp, 25)
        
        if self.text is not None and not isinstance(self.text, tuple):
            self.text = (self.text, 'UTF-8')
        if self.html is not None and not isinstance(self.html, tuple):
            self.html = (self.html, 'UTF-8')
        
        if self.user_name is None and self.password is not None:
            self.user_name = self.from_addr()
            
    @staticmethod
    def get_mime_type(file_name):
        try:
            import magic
            return magic.from_file(file_name, mime=True).decode('UTF-8')
        except ImportError:
            import mimetypes
            return mimetypes.guess_type(file_name, strict=False)[0]

    def make_attachments(self):
        result = []
        for at in self.attachments:
            with open(at, 'rb') as f:
                content = f.read()
            mime_type = Email.get_mime_type(at)
            m1, m2 = mime_type.split('/')
            file_name = os.path.normpath(at).rsplit(os.sep, 1)[-1]
            result.append((content, m1, m2, file_name, None))
        return result
        
    def generate(self):
        self.normalize()
        got_attachments = self.make_attachments()
        return compose_mail(self.from_, self.to, self.subject, 'UTF-8',
                            self.text, self.html, got_attachments, [], self.cc, self.bcc)[0]
    
    def send(self, to=None):
        if to is not None:
            orig_to = self.to
            self.to = to
            
        payload = self.generate()   # normalize()'ed
        ret = pyzmail.send_mail(
            payload, self.from_addr(), self.to_addr(),
            self.smtp[0], self.smtp[1], self.mode, self.user_name, self.password
        )
        
        if to is not None:
            self.to = orig_to
        return ret


def send_grouped_files(from_, to=None, files=[], ordered_by=None, max_size=50*1000*1000, **kwd):
    if to is None:
        to = [from_]
        
    files = list(files)     # copy
    sort_func = {
        'file_name' : None,
        'size'      : os.path.getsize,
        'date'      : os.path.getmtime,
        'time'      : os.path.getmtime,
        'modified'  : os.path.getmtime,
        'created'   : os.path.getctime,
        'accessed'  : os.path.getatime,
    }
    if ordered_by is not None:
        files.sort(key=sort_func[ordered_by])
    
    files_size = list(map(os.path.getsize, files))
    groups = [[]]
    total_size = 0
    for i, x in enumerate(files_size):
        if x > max_size:
            raise Exception('file "%s", size %d, exceed max_size %d\n' % (files[i], x, max_size))
        else:
            if x + total_size < max_size:
                groups[-1].append(files[i])
                total_size += x
            else:
                groups.append([files[i]])
                total_size = x
    
    eml = Email(from_=from_, to=to, **kwd)
    for i, attachments in enumerate(groups):
        eml.subject = 'batch mailer task %d' % i
        eml.text = '\n'.join(attachments)
        eml.attachments = attachments
        ret = eml.send()
        print('task: %d\n%s\n' % (i, ret))

def get_meta_data(file_name, thumbnail_size=50):
    """return a dict of a file's meta data"""
    meta = {
        'file': {
            'name': os.path.normpath(file_name).rsplit(os.sep, 1)[-1],
            'path': os.path.normpath(file_name),
            'size': os.path.getsize(file_name),
            'date': {
                'modified': os.path.getmtime(file_name),
                'created' : os.path.getctime(file_name),
#                     'accessed': os.path.getatime(file_name),
            },
        },
    }
    with open(file_name, 'rb') as file:
        # temporary var
        meta['file']['data'] = file.read()
        
    def file_magic_from_buffer(data):
        try:
            import magic
            return magic.from_buffer(data, mime=False).decode('UTF-8')
        except ImportError:
            return

    meta['type_description'] = file_magic_from_buffer(meta['file']['data'])
        
    def hash_data(data, method):
        return hashlib.new(method, data).hexdigest()
    
    # hash
    meta['file']['hash'] = {
        method: hash_data(meta['file']['data'], method)
        for method in ('md5', 'sha256')
    }
    
    try:
        import PIL, PIL.Image, PIL.ExifTags
        try:
            file = io.BytesIO(meta['file']['data'])
            with PIL.Image.open(file) as im:
                # basic image info
                meta['image'] = {
                    'format': im.format,
                    'size'  : im.size,
                    'mode'  : im.mode,
                }
                
                # image exif
                if 'exif' in im.info:
                    exif = {
                        PIL.ExifTags.TAGS[k]: v
                        for k, v in im._getexif().items()
                        if k in PIL.ExifTags.TAGS
                    }
                    if 'DateTimeOriginal' in exif:
                        meta['image']['date'] = exif['DateTimeOriginal']
                    if 'Model' in exif:
                        meta['image']['device'] = exif['Model']
                
                # image thumbnail, must be last
                if thumbnail_size is not None and thumbnail_size > 0:
                    max_w_h = max(meta['image']['size'])
                    if max_w_h <= thumbnail_size:
                        resize_size = meta['image']['size']
                    else:
                        ratio = thumbnail_size / max_w_h
                        resize_size = (meta['image']['size'][0] * ratio,
                                       meta['image']['size'][1] * ratio)
                    im.thumbnail(resize_size)
                    buf = io.BytesIO()
                    im.save(buf, format='JPEG', optimize=True)
                    meta['image']['thumbnail'] = buf.getvalue()
        except IOError:
            pass
    except ImportError:
        pass
    
    del meta['file']['data']
    return meta

def files2meta_data_list(files, thumbnail_size=80, **kwd):
    return [ get_meta_data(x, thumbnail_size) for x in files ]

def sort_meta_data_list(metas, ordered_by, reverse=False, **kwd):
    """sort a list of meta data
    
    eg:
    st_list = sort_meta_data_list(metas, 'image.date', reverse=True)
    st_list = sort_meta_data_list(metas, 'file.name')
    """
    metas = metas[:]
    def key_cmp(a, b):
        def cmp(a, b):
            if a < b:
                return -1
            elif a > b:
                return 1
            else:
                return 0
            
        for x in ordered_by.split('.'):
            if isinstance(a, dict) and x in a:
                a = a[x]
            else:
                return -1
            if isinstance(b, dict) and x in b:
                b = b[x]
            else:
                return 1
        return cmp(a, b)
    
    metas.sort(key=functools.cmp_to_key(key_cmp), reverse=reverse)
    return metas

def meta_data2groups(meta_data=[], max_size=45*1024*1024):
    """split a list a meta data into groups(list),
    each group is smaller than max_size.
    
    return a list of groups
    """
    
    groups = [[]]
    total_size = 0
    for x in meta_data:
        if x['file']['size'] > max_size:
            raise Exception('file "%s", size %d, exceed max_size %d\n' %
                            (x['file']['name'], x['file']['size'], max_size))
        else:
            if x['file']['size'] + total_size < max_size:
                # append to last group
                groups[-1].append(x)
                total_size += x['file']['size']
            else:
                # new group
                groups.append([x])
                total_size = x['file']['size']
    return groups

def files2groups(files=[], max_size=45*1024*1024, ordered_by=None, **kwd):
    """
    eg:
    # reverse sort photos by the date taken, group them into groups small than 10MB.
    # control the size of thumbnails included in html.
    files2groups(glob('*.JPG'), max_size=10*1000*1000, ordered_by='image.date', reverse=True, thumbnail_size=100)
    """
    metas = files2meta_data_list(files, **kwd)
    if ordered_by is not None:
        metas = sort_meta_data_list(metas, ordered_by, **kwd)
    return meta_data2groups(metas, max_size)

def group2html(grp):
    """generate a html for a group"""
    def fmt_time(time):
        fmt = '%Y-%m-%d %H:%M:%S'
        if isinstance(time, str):
            # exif time format
            return datetime.datetime.strptime(time, '%Y:%m:%d %H:%M:%S').strftime(fmt)
        else:
            # unix timestamp
            return datetime.datetime.fromtimestamp(time).strftime(fmt)
    def datauri(data):
        return 'data:image/jpeg;base64,'+base64.encodebytes(data).decode(encoding='utf_8')
    
    ret = '''<!DOCTYPE html>
    <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
    <style>
        html {
            font-family: monospace;
        }
        
        table, th, td {
            border: 1px solid black;
            border-collapse: collapse;
        }
        
        .detail {
            height: 20px;
            width: 510px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            cursor: pointer;
        }
        
        //.detail:hover {
        //    height: auto;
        //    overflow: visible;
        //    white-space: normal;
        //}
    
        input[type='checkbox'] {
            visibility: hidden;
            position: absolute;
        }
        input[type='checkbox']:checked + .detail {
            height: auto;
            overflow: visible;
            white-space: normal;
        }
        
    </style>
'''
    for i, x in enumerate(grp):
        table = '''
    # '''+str(i)+'''
    <table cellspacing="0" cellpadding="0">
        <tr>
            <td>
                <table width="1">
                    <tr>
                        <th colspan="4">File</th>
                    </tr>
                    <tr>
                        <th>Name</th>       <td>'''+html.escape(x['file']['name'])+'''</td>
                        <th>Size</th>       <td>'''+(('%d (%s)'
                                                      % (x['file']['size'], sizeof_fmt(x['file']['size'])))
                                                      if x['file']['size'] > 1024
                                                      else str(x['file']['size']))+'''</td>
                    </tr>
                    <tr>
                        <th>Created</th>    <td>'''+fmt_time(x['file']['date']['created'])+'''</td>
                        <th>Modified</th>   <td>'''+fmt_time(x['file']['date']['modified'])+'''</td>
                    </tr>
                    <tr>
                        <th>md5</th>        <td colspan="3">'''+x['file']['hash']['md5']+'''</td>
                    </tr>
                    <tr>
                        <th>sha256</th>     <td colspan="3">'''+x['file']['hash']['sha256']+'''</td>
                    </tr>
                    <tr>
                        <th>Type</th>       <td colspan="3"><label><input type="checkbox" />
                                                <div class="detail">'''+(html.escape(x['type_description'])
                                                                         if x['type_description'] is not None
                                                                         else 'N/A')+'''
                                                </div></lable>
                                            </td>
                    </tr>
                </table>
            </td>
'''
        if 'image' in x:
            table +='''
            <td valign="top">
                <table>
                    <tr>
                        <!-- data:image/jpeg;base64,AAABAA... -->
                        '''+(('<td rowspan="4"><img src="'+datauri(x['image']['thumbnail'])+'" /></td>')
                             if 'thumbnail' in x['image']
                             else '')+'''
                        <th colspan="4">Image</th>
                    </tr>
                    <tr>
                        <th>Date</th>      <td>'''+(fmt_time(x['image']['date'])
                                                    if 'date' in x['image']
                                                    else 'N/A')+'''</td>
                        <th>Size</th>      <td>'''+('%dx%d' % x['image']['size'])+'''</td>
                    </tr>
                    <tr>
                        <th>Format</th>    <td>'''+html.escape(x['image']['format'])+'''</td>
                        <th>Mode</th>      <td>'''+html.escape(x['image']['mode'])+'''</td>
                    </tr>
                    <tr>
                        <th>Device</th>    <td>'''+(html.escape(x['image']['device'])
                                                    if 'device' in x['image']
                                                    else 'N/A')+'''</td>
                    </tr>
                </table>
            </td>
'''
        table += '''
        </tr>
    </table>
    <br />
'''
        ret += table
        
    ret += '''
    <hr />
    '''+('%d files, %s.' % (len(grp), sizeof_fmt(sum(x['file']['size'] for x in grp))))+'''
</html>'''
    return ret

def group2text(grp):
    return json_encode([x for x in grp], indent=4)
#     return 'See html part of this email.'

def group2Email(grp, subject=None, **kwd):
    eml = Email(**kwd)
    eml.subject = subject
    eml.text = group2text(grp)
    eml.html = group2html(grp)
    eml.attachments = [ x['file']['path'] for x in grp ]
    
    return eml

def groups2subjects(groups, title='batch mailer',
                    subject_fmt='{title} #{num} ({progress}/{total}) {size}', **kwd):
    """return a list of sujects for each group
    
    eg:
    [
        'batch mailer #1 (1-4/23) 45MiB',
        'batch mailer #2 (5-11/23) 47MiB',
        ......
    ]
    
    usage:
    subjects = groups2subjects(groups)
    for i, grp in enumerate(groups):
        eml = group2Email(grp, subjects[i])
        # setting up eml
        ......
        eml.send()
    """
    total = sum(len(x) for x in groups)
    subjects = []
    
    progress_tup = (0, 0)
    for i, grp in enumerate(groups):
        progress_tup = (progress_tup[1]+1, progress_tup[1]+len(grp))
        att_size = sum(x['file']['size'] for x in grp)
        this_subject = subject_fmt.format(title=title, num=i+1, total=total, size=sizeof_fmt(att_size),
                                      progress=('%d-%d' % progress_tup))
        subjects.append(this_subject)
        
    return subjects

def groups2Emails(groups, **kwd):
    """return a list of Email instances from a list of groups
    
    eg:
    emails = groups2Emails(groups, title='hahaha', from_='xxx@abc.com', to=['yyy@ddd.com'], smtp='mail.abc.com')
    passwd = input('your password')
    for eml in emails:
        eml.password = passwd
        # setting up eml
        ......
        eml.send()
    """
    subjects = groups2subjects(groups, **kwd)
    emails = []
    for i, grp in enumerate(groups):
        eml = group2Email(grp, subject=subjects[i], **kwd)
        emails.append(eml)
    return emails
        

if __name__ == '__main__':
    # sort and split images into groups
    grps = files2groups(glob('*.JPG')+['batchmail.py'], max_size=10*1024*1024, ordered_by='image.date')
    # setup each Email instance
    emls = groups2Emails(grps, title='Some photos')
    for eml in emls:
        eml.from_ = 'xxx@example.com'
        eml.to = ['yyy@abc.com']
        eml.user_name = 'xxx@example.com'
        eml.password = '*********'
        eml.smtp = 'smtp.example.com'
        
#         eml.send()
         
        eml.normalize()
        print(eml)
