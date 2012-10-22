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
        return data.decode(encoding)
