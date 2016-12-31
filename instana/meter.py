import threading as t
import thread
import instana.log as l
import resource
import os
import gc
import sys
import instana.agent_const as a

class Snapshot(object):
    name = None
    version = None
    rlimit_core=(0, 0)
    rlimit_cpu=(0, 0)
    rlimit_fsize=(0, 0)
    rlimit_data=(0, 0)
    rlimit_stack=(0, 0)
    rlimit_rss=(0, 0)
    rlimit_nproc=(0, 0)
    rlimit_nofile=(0, 0)
    rlimit_memlock=(0, 0)
    rlimit_as=(0, 0)
    versions = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

class GC(object):
    collect0 = 0
    collect1 = 0
    collect2 = 0
    threshold0 = 0
    threshold1 = 0
    threshold2 = 0

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

class Metrics(object):
    ru_utime = .0
    ru_stime = .0
    ru_maxrss = 0
    ru_ixrss = 0
    ru_idrss = 0
    ru_isrss = 0
    ru_minflt = 0
    ru_majflt = 0
    ru_nswap = 0
    ru_inblock = 0
    ru_oublock = 0
    ru_msgsnd = 0
    ru_msgrcv = 0
    ru_nsignals	= 0
    ru_nvcs = 0
    ru_nivcsw = 0
    dead_threads = 0
    alive_threads = 0
    daemon_threads = 0
    gc = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

class EntityData(object):
    pid = 0
    snapshot = None
    metrics = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

class Meter(object):
    SNAPSHOT_PERIOD = 600
    snapshot_countdown = 1
    sensor = None
    last_usage = None
    last_collect = None

    def __init__(self, sensor):
        self.sensor = sensor
        self.tick()

    def tick(self):
        t.Timer(1, self.process).start()

    def process(self):
        if self.sensor.agent.can_send():
            self.snapshot_countdown = self.snapshot_countdown - 1
            s = None
            if self.snapshot_countdown == 0:
                self.snapshot_countdown = self.SNAPSHOT_PERIOD
                s = self.collect_snapshot()

            m = self.collect_metrics()
            d = EntityData(pid=os.getpid(), snapshot=s, metrics=m)

            thread.start_new_thread(self.sensor.agent.request,
                                    (self.sensor.agent.make_url(a.AGENT_DATA_URL), "POST", d))

        self.tick()

    def collect_snapshot(self):
        s = Snapshot(name=self.sensor.service_name,
                     version=sys.version,
                     rlimit_core=resource.getrlimit(resource.RLIMIT_CORE),
                     rlimit_cpu=resource.getrlimit(resource.RLIMIT_CPU),
                     rlimit_fsize=resource.getrlimit(resource.RLIMIT_FSIZE),
                     rlimit_data=resource.getrlimit(resource.RLIMIT_DATA),
                     rlimit_stack=resource.getrlimit(resource.RLIMIT_STACK),
                     rlimit_rss=resource.getrlimit(resource.RLIMIT_RSS),
                     rlimit_nproc=resource.getrlimit(resource.RLIMIT_NPROC),
                     rlimit_nofile=resource.getrlimit(resource.RLIMIT_NOFILE),
                     rlimit_memlock=resource.getrlimit(resource.RLIMIT_MEMLOCK),
                     rlimit_as=resource.getrlimit(resource.RLIMIT_AS),
                     versions=self.collect_modules())

        return s

    def collect_modules(self):
        m = sys.modules
        r = {}
        for k in m:
            if m[k]:
                d = m[k].__dict__
                if "version" in d and d["version"]:
                    r[k] = d["version"]
                elif "__version__" in d and d["__version__"]:
                    r[k] = d["__version__"]
                else:
                    r[k] = "builtin"

        return r

    def collect_metrics(self):
        u = resource.getrusage(resource.RUSAGE_SELF)
        if gc.isenabled():
            c = list(gc.get_count())
            th = list(gc.get_threshold())
            g = GC(collect0=c[0] if not self.last_collect else c[0] - self.last_collect[0],
                   collect1=c[1] if not self.last_collect else c[1] - self.last_collect[1],
                   collect2=c[2] if not self.last_collect else c[2] - self.last_collect[2],
                   threshold0=th[0],
                   threshold1=th[1],
                   threshold2=th[2])

        thr = t.enumerate()
        daemon_threads = len(map(lambda tr: tr.daemon and tr.is_alive(), thr))
        alive_threads = len(map(lambda tr: not tr.daemon and tr.is_alive(), thr))
        dead_threads = len(map(lambda tr: not tr.is_alive(), thr))

        m = Metrics(ru_utime=u[0] if not self.last_usage else u[0] - self.last_usage[0],
                    ru_stime=u[1] if not self.last_usage else u[1] - self.last_usage[1],
                    ru_maxrss=u[2],
                    ru_ixrss=u[3],
                    ru_idrss=u[4],
                    ru_isrss=u[5],
                    ru_minflt=u[6] if not self.last_usage else u[6] - self.last_usage[6],
                    ru_majflt=u[7] if not self.last_usage else u[7] - self.last_usage[7],
                    ru_nswap=u[8] if not self.last_usage else u[8] - self.last_usage[8],
                    ru_inblock=u[9] if not self.last_usage else u[9] - self.last_usage[9],
                    ru_oublock=u[10] if not self.last_usage else u[10] - self.last_usage[10],
                    ru_msgsnd=u[11] if not self.last_usage else u[11] - self.last_usage[11],
                    ru_msgrcv=u[12] if not self.last_usage else u[12] - self.last_usage[12],
                    ru_nsignals=u[13] if not self.last_usage else u[13] - self.last_usage[13],
                    ru_nvcs=u[14] if not self.last_usage else u[14] - self.last_usage[14],
                    ru_nivcsw=u[15] if not self.last_usage else u[15] - self.last_usage[15],
                    alive_threads=alive_threads,
                    dead_threads=dead_threads,
                    daemon_threads=daemon_threads,
                    gc=g)

        self.last_usage = u
        if gc.isenabled():
            self.last_collect = c

        return m