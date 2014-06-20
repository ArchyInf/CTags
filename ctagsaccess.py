import os

try:
    import sublime
    import sublime_plugin
    from sublime import status_message, error_message
except ImportError:  # running tests
    import sys

    from tests.sublime_fake import sublime
    from tests.sublime_fake import sublime_plugin

    sys.modules['sublime'] = sublime
    sys.modules['sublime_plugin'] = sublime_plugin

if sublime.version().startswith('2'):
    import ctags
    from ctags import (FILENAME, parse_tag_lines, PATH_ORDER, SYMBOL,
                       TagElements, TagFile)
    from helpers.edit import Edit
else:  # safe to assume if not ST2 then ST3
    from CTags import ctags
    from CTags.ctags import (FILENAME, parse_tag_lines, PATH_ORDER, SYMBOL,
                             TagElements, TagFile)
    from CTags.helpers.edit import Edit


def get_settings():
    """Load settings.

    :returns: dictionary containing settings
    """
    return sublime.load_settings("CTags.sublime-settings")


def get_setting(key, default=None):
    """Load individual setting.

    :param key: setting key to get value for
    :param default: default value to return if no value found

    :returns: value for ``key`` if ``key`` exists, else ``default``
    """
    return get_settings().get(key, default)

setting = get_setting


class ctags_access_test(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        view = self.view
        tag_files = collect_project_tag_files(view)
        print("Found", len(tag_files), "tag files")
        for path in tag_files:
            print(path)

class ctags_access_merge(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        # todo: use mmap
        tags = []

        view = self.view
        tag_files = collect_project_tag_files(view)
        print("Found", len(tag_files), "tag files")
        for path in tag_files:
            folder = os.sep.join(path.split(os.sep)[:-1])
            # column not important; merge creates a new file that is sorted
            with TagFile(path, SYMBOL) as f:
                for tag in f.search():
                    if not tag[SYMBOL].startswith("!"):
                        tag[FILENAME] = self.make_absolute(tag[FILENAME], folder)
                        tags.append(tag)

        outfile = os.path.join(view.window().folders()[0], ".tagsmaster")
        self.create_ctags_file(tags, outfile)

    def create_ctags_file(self, tags, path):
        print("Creating new tags file", path, "containing", len(tags), "tags")

        target_folder = os.sep.join(path.split(os.sep)[:-1])
        # update entry paths to be relative to the new tag file
        for tag in tags:
            tag[FILENAME] = self.make_relative_if_possible(tag[FILENAME], target_folder)

        tags = sorted(tags)
        with open(path, "w+") as f:
            # write header
            # write entries
            f.writelines([tag.line + "\n" for tag in tags])

    def make_absolute(self, path, root):
        return os.path.abspath(os.path.join(root, path))

    def make_relative_if_possible(self, path, topath):
        if os.path.splitdrive(path)[0] == os.path.splitdrive(topath)[0]:
            return os.path.relpath(path, topath)
        return path
        
def collect_project_tag_files(view):
    tag_files = []

    for folder in view.window().folders():
        for dirName, subdirList, fileList in os.walk(folder):
            search_path = os.path.join(folder, dirName)
            tag_files = tag_files + collect_tag_files_in_folder(search_path)

    # read all tag files in project
    for folder in view.window().folders():
        tag_files = tag_files + collect_tag_files_in_folder(folder)

    # read and add additional tag file paths from 'extra_tag_paths' setting
    try:
        for (selector, platform), path in setting('extra_tag_paths'):
            if view.match_selector(view.sel()[0].begin(), selector):
                if sublime.platform() == platform:
                    tag_files = tag_files + collect_tag_files_in_folder(path)
    except Exception as e:
        print(e)

    return list(set(tag_files))


def collect_tag_files_in_folder(folder):
    search_paths = []
    search_paths.append(
        os.path.normpath(
            os.path.join(folder, setting('tag_file'))))
    for extrafile in setting('extra_tag_files'):
        search_paths.append(
            os.path.normpath(
                os.path.join(folder, extrafile)))
    return check_search_paths(search_paths)


def check_search_paths(paths):
    ret = []
    for p in paths:
        if p and (p not in ret) and os.path.exists(p) and os.path.isfile(p):
            ret.append(p)
    return ret


def find_tags_relative_to(path, tag_file):
    """Find the tagfile relative to a file path.

    :param path: path to a file
    :param tag_file: name of tag file

    :returns: path of deepest tag file with name of ``tag_file``
    """
    if not path:
        return None

    dirs = os.path.dirname(os.path.normpath(path)).split(os.path.sep)

    while dirs:
        joined = os.path.sep.join(dirs + [tag_file])

        if os.path.exists(joined) and not os.path.isdir(joined):
            return joined
        else:
            dirs.pop()

    return None
