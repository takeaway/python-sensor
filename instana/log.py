import logging as l

logger = l.getLogger('instana')

def init(level):
    ch = l.StreamHandler()
    f = l.Formatter('%(asctime)s: %(levelname)s: %(name)s: %(message)s')
    ch.setFormatter(f)
    logger.addHandler(ch)
    logger.setLevel(level)

def debug(s, *args):
    logger.debug("%s %s" % (s, ' '.join(args)))

def info(s, *args):
    logger.info("%s %s" % (s, ' '.join(args)))

def warn(s, *args):
    logger.warn("%s %s" % (s, ' '.join(args)))

def error(s, *args):
    logger.error("%s %s" % (s, ' '.join(args)))