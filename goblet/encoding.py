# Goblet - Web based git repository browser
# Copyright (C) 2012-2014 Dennis Kaarsemaker
# See the LICENSE file for licensing details

import chardet

def decode(data, encoding=None):
    if isinstance(data, unicode):
        return data
    if encoding:
        return data.decode(encoding)
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        encoding = chardet.detect(data)['encoding']
        if not encoding:
            return "(Binary data)"
        return data.decode(encoding)
