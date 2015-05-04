# comic scraper
import httplib2
import urllib.request
import urllib.parse
from sys import argv, exit, stderr
import getopt
import json
import pickle
import re # awaking cthulhu
import datetime
import time
import errno
import os

#options
_header_data = [('User-Agent', 'Mozilla/5.0')]
_data_dir = 'data'
_img_dir = 'img'
_cache_dir = '.cache'
_pattern_json = ''
_input_json = ''
_output_json = ''
_meta_json = ''
_no_scrape = False
_rebuild_days = False
_export_days = False
_export_meta = False
_debug = False

def initDay(date, data):
  day = {}
  day['comics'] = {}
  for name in data['dates'][date]:
    day['comics'][name] = {}
    day['comics'][name]['file'] = []
    day['comics'][name]['alttxt'] = {}
    day['comics'][name]['local'] = {}
    day['comics'][name][date] = []
    day['comics'][name][date] = data['comics'][name][date]
    for filename in day['comics'][name][date]:
      day['comics'][name]['alttxt'][filename] = data['comics'][name]['alttxt'][filename]
      try:
        data['comics'][name]['local'][filename]
        day['comics'][name]['local'][filename] = data['comics'][name]['local'][filename]
      except KeyError: # no local file
        pass
    day['comics'][name]['name'] = data['comics'][name]['name']
    day['comics'][name]['url'] = data['comics'][name]['url']
    day['comics'][name]['baseurl'] = data['comics'][name]['baseurl']
  return day

def export_daydata(date, data):
  today_in_seconds = repr(int((time.mktime(datetime.date.today().timetuple()))*1000))
  yesterday_in_seconds = repr(int((time.mktime((datetime.date.today() - datetime.timedelta(1)).timetuple()))*1000))
  # consider reading current json file to detect changes
  day = initDay(date, data)
  daydir = _data_dir + '/days/'
  dayfile = daydir+date+'.json'
  if os.path.isdir(daydir) == False: # create directories if not existing
    try:
      os.makedirs(daydir)
    except IOError as e:
      print('Cannot create day directory', file=stderr)
      if _debug:
        print(e, file=stderr)
  # always update last two dates
  if (_rebuild_days or date == today_in_seconds or date == yesterday_in_seconds):
    with open(dayfile, 'w', encoding='utf-8') as f:
      json.dump(day, f)
  else:
    # create older if not existing
    try:
      with open(dayfile, 'r', encoding='utf-8') as f:
        devnull = f.read()
    except IOError:
      with open(dayfile, 'w', encoding='utf-8') as f:
        json.dump(day, f)

def export_metadata(data):
  names = {};
  names['meta'] = {}
  for name in data:
    names['meta'][name] = {}
    names['meta'][name]['name'] = data[name]['name']
  return names

def sanitize_url(url):
  url = urllib.parse.urlsplit(url)
  url = list(url)
  url[2] = urllib.parse.quote(url[2])
  url = urllib.parse.urlunsplit(url)
  return url

def write_image_file(baseurl, fileurl, name, ret = ''):
  url = sanitize_url(baseurl + fileurl)
  try:
    one = 1
    opener = urllib.request.build_opener()
    header = _header_data
    header.append(('Referer', baseurl))
    opener.addheaders = header
    content = opener.open(url)
    content = content.read()
    decoded = content
    if (type(content) is not str):
      try:
        decoded = content.decode('utf-8')
      except UnicodeDecodeError:
        try:
          decoded = content.decode('windows-1252')
        except UnicodeDecodeError:
          try:
            decoded = content.decode('ascii')
          except UnicodeDecodeError:
            time_right_now = repr(int(time.mktime(time.localtime())))+datetime.datetime.now().strftime('%f')
            directory = _img_dir + '/' + name + '/'
            imagefile = directory + time_right_now
            if os.path.isdir(directory) == False: # create directories if not existing
              try:
                os.makedirs(directory)
              except IOError as e:
                print('Cannot create img directory', file=stderr)
                if _debug:
                  print(e, file=stderr)
            try:
              with open(imagefile, 'wb') as f:
                f.write(content)
                ret = time_right_now
            except IOError as e:
              ret = ''
              print('fwerr: Could not write file to ' + imagefile, file=stderr)
              if (_debug):
                print(e, file=stderr)
            except Exception as e:
              ret = ''
              print('fwerr: Un-identified error while writing file (exists?) ' + imagefile, file=stderr)
              if (_debug):
                print(e, file=stderr)
      except Exception as e:
        ret = ''
        print(name + ': Un-identified error while trying to decode file ' + imagefile, file=stderr)
        if (_debug):
          print(e, file=stderr)
      if (type(decoded) is str):
        ret = ''
        print(name + ': image url returned string', file=stderr)
    if (ret == ''):
      os.remove(imagefile)
  except Exception as e:
    print(e, file=stderr)
    pass
  return ret

def parser(comicdata, h, data):
  try:
    for date in data['dates']: # remove duplicates
      data['dates'][date] = set(data['dates'][date])
  except KeyError:
    data['dates'] = {}
    try:
      data['comics']
    except KeyError:
      data['comics'] = {}
  for name in comicdata:
    try:
      baseurl = comicdata[name]['baseurl']
    except KeyError:
      baseurl = ""
    comic = name
    url = comicdata[name]['url']
    pattern = comicdata[name]['pattern']
    comicname = comicdata[name]['name']
    try:
      url_to_parse = comicdata[name]['feed']
    except KeyError:
      url_to_parse = url
    try:
      data['comics'][name]
    except KeyError:
      data['comics'][name] = {}
      data['comics'][name]['file'] = []
      data['comics'][name]['alttxt'] = {}
    try:
      data['comics'][name]['local']
    except KeyError:
      data['comics'][name]['local'] = {}
    data['comics'][name]['name'] = comicname
    data['comics'][name]['url'] = url
    data['comics'][name]['baseurl'] = baseurl
    try:
      response, content = h.request(url_to_parse, headers=dict(_header_data))
    except httplib2.ServerNotFoundError:
      print(name + " ServerNotFound: " + url_to_parse, file=stderr)
      continue
    except BaseException as e:
      print(e, file=stderr)
      try:
        errno_ = e.errno
        if errno_ == errno.ECONNRESET:
          print(name + ': reset connection', file=stderr)
          continue
      except Exception as e:
        print(e, file=stderr)
        continue
    try:
      content_type = type(content)
    except UnboundLocalError:
      print(name + ': has no content', file=stderr)
      continue
    if (type(content) is not str):
      try:
        content = content.decode('utf-8')
      except UnicodeDecodeError:
        try:
          content = content.decode('windows-1252')
        except UnicodeDecodeError:
          try:
            content = content.decode('ascii')
          except UnicodeDecodeError:
            continue
    if (response.status == 200):
      match = re.search(pattern, content, re.DOTALL)
      try:
        match = match.groupdict()
      except AttributeError:
        print(name + ': No match, check regexp', file=stderr)
        continue
      try:
        fileurl = match['file'].rstrip('"');
      except TypeError:
        fileurl = None
      try:
        alt = match['title']
      except KeyError:
        alt = ""
      alt = re.sub("['\"]", "&#39", alt);
      if (fileurl != None):
        today_in_seconds = repr(int((time.mktime(datetime.date.today().timetuple()))*1000))
        if (fileurl not in data['comics'][name]['file']):
          data['comics'][name]['file'].append(fileurl)
          data['comics'][name]['alttxt'][fileurl] = alt
          try:
            data['comics'][name][today_in_seconds] = set(data['comics'][name][today_in_seconds])
          except:
            data['comics'][name][today_in_seconds] = set()
          data['comics'][name][today_in_seconds].add(fileurl)
          data['comics'][name][today_in_seconds] = list(data['comics'][name][today_in_seconds])
        if today_in_seconds in data['comics'][name]:
          try:
            data['dates']
          except KeyError:
            data['dates'] = {}
          try:
            data['dates'][today_in_seconds]
          except KeyError:
            data['dates'][today_in_seconds] = set()
          data['dates'][today_in_seconds].add(comic)
        if (fileurl not in data['comics'][name]['local']):
          local_file_name = ''
          local_file_name = write_image_file(data['comics'][name]['baseurl'], fileurl, name, local_file_name)
          if (local_file_name != ''):
            data['comics'][name]['local'][fileurl] = local_file_name
    else:
        print(name + ': Error response ' + str(response.status))
  try:
    data['dates']
    for date in data['dates']: # set -> list as set is not serializable
      data['dates'][date] = list(data['dates'][date])
  except KeyError as e: # no dates
    pass
  if _export_days:
    export_daydata(date, data)
  return data;

def usage():
  print( 'usage: rescrape.py [options] ... '
      '[-p pattern-file | -i input-file | -o output-file]\n'
      '-h, --help               : print this message\n'
      '-p, --pattern-file=file  : specify pattern file\n'
      '-i, --input=file         : specify input file\n'
      '-o, --output=file        : specify output file\n'
      '--io file                : specify input-output file\n'
      '--img-dir=path           : specify directory to write image files to\n'
      '--data-dir=path          : specify directory to write json files to\n'
      '--cache-dir=path         : specify directory to write caches to\n'
      '-d, --export-days        : export days to separate json files\n'
      '--rebuild-days           : rebuild all day files\n'
      '-m, --export-meta        : export meta data\n'
      '--meta-file file         : specify output meta data file\n'
      '--no-scrape              : do not scrape\n'
      '--no-cache               : ignore cache\n'
      )

def readArgs(args):
  try:
    opts, args = getopt.getopt(args, "hp:i:o:md", ["help", "pattern-file=", "input=", "output=", "io=", "export-days", "rebuild-days", "img-dir=", "data-dir=", "cache-dir=", "debug", "export-meta", "meta-file=", "no-scrape", "no-cache"])
  except getopt.GetoptError:
    usage()
    exit(2)
  global _input_json
  global _output_json
  global _pattern_json
  global _export_days
  global _export_meta
  global _meta_json
  global _rebuild_days
  global _img_dir
  global _data_dir 
  global _cache_dir 
  global _debug
  global _no_scrape
  global _header_data
  for opt, arg in opts:
    if opt in ("-h", "--help"):
      usage()
      exit(2)
    elif opt == "--io":
      _input_json = arg
      _output_json = arg
    elif opt in ("-i", "--input"):
      _input_json = arg
    elif opt in ("-o", "--output"):
      _output_json = arg
    elif opt in ("-p", "--pattern-file"):
      _pattern_json = arg
    elif opt in ("-d", "--export-days"):
      _export_days = True
    elif opt in ("-m", "--export-meta"):
      _export_meta = True
    elif opt == "--meta-file":
      _export_meta = True
      _meta_json = arg
    elif opt == "--rebuild-days":
      _rebuild_days = True
    elif opt == "--img-dir":
      _img_dir = arg
    elif opt == "--data-dir":
      _data_dir = arg
    elif opt == "--cache-dir":
      _cache_dir = arg
    elif opt == "--debug":
      _debug = True
    elif opt == "--no-scrape":
      _no_scrape = True
    elif opt == "--no-cache":
      _header_data.append(('cache-control', 'no-cache'))
  if _debug:
    print('Options:\n'
        '_input_json : "'   + _input_json + '"\n'
        '_output_json : "'  + _output_json + '"\n'
        '_pattern_json : "' + _pattern_json + '"\n'
        '_export_days : '   + str(_export_days) + '\n'
        '_rebuild_days : '  + str(_rebuild_days) + '\n'
        '_img_dir : "'      + _img_dir + '"\n'
        '_data_dir : "'     + _data_dir + '"\n'
        '_cache_dir : "'    + _cache_dir + '"\n'
        '_no_scrape : "'    + str(_no_scrape) + '"\n'
        '_export_meta : "'  + str(_export_meta) + '"\n'
        '_meta_json : "'    + _meta_json + '"\n'
        '_no_cache : "'     + str(_no_cache) + '"\n'
        '_debug : "'        + str(_debug) + '"\n')

def main():
  readArgs(argv[1:])
  try:
    with open(_pattern_json, 'r', encoding='utf-8') as f:
      try:
        comicdata = json.load(f)
      except Exception as e:
        print("Malformed pattern file, exiting...", file=stderr)
        if (_debug):
          print(e, file=stderr)
        exit(2)
  except IOError as e:
    if _no_scrape: # no need for patterns if not scraping
      pass
    else:
      print("Pattern file not found, exiting...", file=stderr)
      if (_debug):
        print(e, file=stderr)
      exit(2)
  data = {}
  if _input_json != '':
    try:
      with open(_input_json, 'r', encoding='utf-8') as f:
        jsonstr = f.read()
        if (jsonstr):
          try:
            data = json.loads(jsonstr)
          except Exception as e:
            print("Malformed input file, exiting...", file=stderr)
            if (_debug):
              print(e, file=stderr)
            exit(2)
    except IOError as e:
      print("Input file not found, exiting...", file=stderr)
      if (_debug):
        print(e, file=stderr)
      exit(2)
  h = httplib2.Http(_cache_dir)
  if _no_scrape == False:
    data = parser(comicdata, h, data)
  if _export_meta:
    meta = export_metadata(data['comics'])
    if _meta_json != '':
      try:
        with open(_meta_json, 'w', encoding='utf-8') as f:
          json.dump(meta, f)
      except IOError as e:
        print("Cannot write to meta file", file=stderr)
        if (_debug):
          print(e, file=stderr)
        exit(1)
    else: #default to stdout
      print(json.dumps(meta))
  if _no_scrape == False: # only write data out if scraped
    if _output_json != '':
      try:
        with open(_output_json, 'w', encoding='utf-8') as f:
          json.dump(data, f)
      except IOError as e:
        print("Cannot write to output file", file=stderr)
        if (_debug):
          print(e, file=stderr)
        exit(1)
    else:
      print(json.dumps(data))

if __name__ == '__main__':
  main()