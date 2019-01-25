#!/usr/bin/python3
from pathlib import Path
from shutil import copy, copytree, rmtree
from datetime import datetime
from dateutil.parser import parse
from mako.template import Template
from feedgen.feed import FeedGenerator
import re
import markdown2
import sys
import os
import pytz

# locations of everything (relative to the location of the build script)
BUILD_DIR = Path('../blog-build')
POST_DIR = Path('posts')
BASE_DIR = Path('base')
POST_TEMPLATE = Path('templates/post.html')
HOMEPAGE_TEMPLATE = Path('templates/homepage.html')

# special files in the post directory
ARTICLE_FILENAME = 'post.md'
DATE_FILENAME = 'date'

# extensions to categorize files by
IMG_EXT = ('png', 'jpg', 'jpeg', 'gif')
VID_EXT = ('mp4', 'avi')
AUDIO_EXT = ('mp3', 'wav', 'ogg')

# hardcoded rss fields
fg = FeedGenerator()
fg.title("Stephan's Blog")
fg.id('http://blog.slensky.com')
fg.subtitle('Sharing obscure workarounds and interesting programming stories')
fg.author({'name': 'Stephan Lensky', 'email': 'mail@slensky.com'})
fg.link({'href': 'http://blog.slensky.com'})
fg.language('en')
fg.updated(datetime.now(pytz.timezone('America/New_York')).isoformat())

def copy_base(base, build):
    for f in base.iterdir():
        if build.joinpath(f.relative_to('base')).exists():
            if os.path.isdir(str(f)):
                rmtree(str(build.joinpath(f.relative_to('base'))))
            else:
                os.remove(str(build.joinpath(f.relative_to('base'))))
        if os.path.isdir(str(f)):
            copytree(str(f), str(build.joinpath(f.relative_to('base'))))
        else:
            copy(str(f), str(build.joinpath(f.relative_to('base'))))

def get_post(dir):
    modified = 0
    post = None
    date = None
    img = []
    vid = []
    audio = []
    other = []
    for f in dir.iterdir():
        if f.is_dir():
            raise OSError('subdirectories are not allowed for posts')
        if f.stat().st_mtime > modified:
            modified = f.stat().st_mtime

        if f.name == ARTICLE_FILENAME:
            post = f
        elif f.name == DATE_FILENAME:
            date = f
        elif f.name.endswith(IMG_EXT):
            img.append(f)
        elif f.name.endswith(VID_EXT):
            vid.append(f)
        elif f.name.endswith(AUDIO_EXT):
            audio.append(f)
        else:
            other.append(f)

    if post is None:
        raise OSError('post.md not found in ' + dir.name)

    d = {
        'name': dir.name,
        'md': post.read_text(),
        'img': img,
        'vid': vid,
        'audio': audio,
        'other': other,
        'modified': datetime.fromtimestamp(modified)
    }
    d['date'] = parse(date.read_text()) if date else d['modified']

    return d


def get_posts(dir):
    posts = []
    for p in dir.iterdir():
        posts.append(get_post(p))
    return posts


def fix_links(md, salt, filenames):
    for f in filenames:
        if f.endswith(IMG_EXT):
            md = md.replace(f, '../../img/' + salt + f)
        elif f.endswith(VID_EXT):
            md = md.replace(f, '../../vid/' + salt + f)
        elif f.endswith(AUDIO_EXT):
            md = md.replace(f, '../../audio/' + salt + f)
        else:
            md = md.replace(f, '../../other/' + salt + f)
    return md

def make_post(post, template):

    parsed = markdown2.markdown(post['md'], extras=['fenced-code-blocks', 'header-ids'])
    
    if 'date' in post:
        date = post['date'].strftime('%d %B, %Y')
    else:
        date = post['modified'].strftime('%d %B, %Y')

    t = Template(template)
    out = t.render(name=post['name'], date=date, content=parsed)
    return out

def make_homepage(posts, template):
    d = {}
    for p in posts:
        if 'date' in p:
            date = p['date']
        else:
            date = p['modified']
        d[date.strftime('%Y%m%d')] = p

    items = []
    for i, k in enumerate(sorted(d.keys())):
        s = hex(i + 1)
        s = s[0:2] + '0' * (6 - len(s)) + s[2:]
        if 'date' in d:
            date = d[k]['date']
        else:
            date = d[k]['modified']
        r = re.compile('[^a-zA-Z ]')
        sanitized_name = r.sub('', d[k]['name']).replace(' ', '-').lower()
        l = k[:4] + '/' + k[4:6] + '/' + sanitized_name + '.html'
        items.append((s, d[k]['name'], l))

    items = reversed(items)

    t = Template(template)
    out = t.render(items=items)
    return out

# fix working directory
os.chdir(str(Path(__file__).parent))

# rebuild the whole tree if the user types 'clean' as an argument
if len(sys.argv) > 1 and sys.argv[1] == 'clean':
    for f in BUILD_DIR.iterdir():
        if f.is_dir():
            rmtree(str(f))
        else:
            os.remove(str(f))

# copies everything in BASE_DIR over to BUILD_DIR without further processing
copy_base(BASE_DIR, BUILD_DIR)

posts = get_posts(POST_DIR)
for p in posts:
    
    # salt any media filenames with the date of the post they're linked to
    # avoids filename conflicts in the future
    if 'date' in p:
        date = p['date']
    else:
        date = p['modified']
    salt = date.strftime('%Y%m%d_')
    filenames = [i.name for i in p['img']] \
                + [v.name for v in p['vid']] \
                + [a.name for a in p['audio']] \
                + [o.name for o in p['other']]
    p['md'] = fix_links(p['md'], salt, filenames)
    
    # convert markdown to html and copy it into the template
    html = make_post(p, POST_TEMPLATE.read_text())
    
    # directory for posts is YEAR/MONTH/post-name.html
    if 'date' in p:
        date = p['date']
    else:
        date = p['modified']
    new_post_dir = BUILD_DIR.joinpath(date.strftime('%Y/%m'))
    
    # make paths for media directories
    img_dir = BUILD_DIR.joinpath('img')
    vid_dir = BUILD_DIR.joinpath('vid')
    audio_dir = BUILD_DIR.joinpath('audio')
    other_dir = BUILD_DIR.joinpath('other')
    
    # make sure all of the directories exist
    new_post_dir.mkdir(exist_ok=True, parents=True)
    img_dir.mkdir(exist_ok=True, parents=True)
    vid_dir.mkdir(exist_ok=True, parents=True)
    audio_dir.mkdir(exist_ok=True, parents=True)
    other_dir.mkdir(exist_ok=True, parents=True)
    
    # sanitize post name (lowercase, spaces converted to hyphens, special chars removed)
    r = re.compile('[^a-zA-Z ]')
    sanitized_name = r.sub('', p['name']).replace(' ', '-').lower()
    # create html file in the newly made post directory using the sanitized name
    new_post_dir.joinpath(sanitized_name + '.html').write_text(html)
    
    # copy media over
    for i in p['img']:
        new_name = salt + i.name
        copy(str(i), str(BUILD_DIR.joinpath('img/' + new_name)))
    for v in p['vid']:
        new_name = salt + v.name
        copy(str(v), str(BUILD_DIR.joinpath('vid/' + new_name)))
    for a in p['audio']:
        new_name = salt + a.name
        copy(str(a), str(BUILD_DIR.joinpath('audio/' + new_name)))
    for o in p['other']:
        new_name = salt + o.name
        copy(str(o), str(BUILD_DIR.joinpath('other/' + new_name)))

    # rss item gen
    url = 'http://blog.slensky.com/{}/{}/{}.html'\
        .format(p['date'].year, p['date'].month, sanitized_name)
    fe = fg.add_entry()
    fe.id(url)
    fe.title(p['name'])
    fe.updated(pytz.timezone('America/New_York').localize(p['modified']).isoformat())
    fe.link({'href': url})

fg.atom_file(str(BUILD_DIR) + '/feed.xml')
fg.rss_file(str(BUILD_DIR) + '/rss.xml')
homepage = make_homepage(posts, HOMEPAGE_TEMPLATE.read_text())
Path(BUILD_DIR).joinpath('index.html').write_text(homepage)
